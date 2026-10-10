"""FAII Agent — runs on your PC.

- Every draft queued from the site ("📤 للموافقة") arrives on your Telegram with ✅ / ✏️ / ❌.
- ✅ on an email → sent from your Gmail and logged in the site. ✅ on WhatsApp → you get a one-tap link.
- ✏️ → reply with the new text, it comes back for approval.
- Morning report every day + /report /queue /pause /resume commands.
Config: agent.env (see agent.env.example).
"""
import json, os, random, re, smtplib, sys, threading, time, traceback
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid
from pathlib import Path
from urllib.parse import quote
import httpx

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
STATE_FILE = HERE / "state.json"


def load_env():
    env = {}
    for line in (HERE / "agent.env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


E = load_env()
for _k in ("NVIDIA_API_KEY", "OLLAMA_MODEL", "EXA_API_KEY"):  # local_ai reads these from the environment
    if E.get(_k):
        os.environ[_k] = E[_k]
_state_lock = threading.RLock()


def _load_state():
    """A half-written state.json (power cut) must not stop the agent: fall back to the backup, then to empty."""
    for f in (STATE_FILE, STATE_FILE.with_suffix(".bak")):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return {}


STATE = _load_state()


def save_state():
    """Write a temp file and swap it in, so a crash mid-write never leaves a broken state.json. Several threads save."""
    with _state_lock:
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(STATE), encoding="utf-8")
        if STATE_FILE.exists():
            os.replace(STATE_FILE, STATE_FILE.with_suffix(".bak"))
        os.replace(tmp, STATE_FILE)


def log(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


# ---------------- Supabase (signed in as the agent's own team account) ----------------
class DB:
    def __init__(self):
        self.url, self.key = E["SUPABASE_URL"].rstrip("/"), E["SUPABASE_KEY"]
        self.token, self.refresh, self.exp = None, None, 0

    def _auth(self):
        if self.token and time.time() < self.exp - 60:
            return
        body = ({"grant_type": "refresh_token", "refresh_token": self.refresh} if self.refresh
                else {"email": E["AGENT_EMAIL"], "password": E["AGENT_PASSWORD"]})
        grant = "refresh_token" if self.refresh else "password"
        r = httpx.post(f"{self.url}/auth/v1/token?grant_type={grant}", json=body, headers={"apikey": self.key}, timeout=30)
        if r.status_code != 200:
            self.refresh = None
            raise RuntimeError(f"Supabase login failed: {r.text[:200]}")
        j = r.json()
        self.token, self.refresh, self.exp = j["access_token"], j["refresh_token"], time.time() + j["expires_in"]

    def req(self, method, table, params=None, body=None, prefer=None):
        self._auth()
        body = clean(body)
        h = {"apikey": self.key, "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        if prefer:
            h["Prefer"] = prefer
        r = httpx.request(method, f"{self.url}/rest/v1/{table}", params=params, json=body, headers=h, timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"{method} {table}: {r.text[:300]}")
        return r.json() if r.text else None

    def get(self, table, **params):
        return self.req("GET", table, params)

    def patch(self, table, match: dict, body):
        return self.req("PATCH", table, {k: f"eq.{v}" for k, v in match.items()}, body)


CTRL = re.compile("[" + "".join(chr(c) for c in list(range(0, 9)) + [11, 12] + list(range(14, 32))) + "]")


def clean(v):
    """Postgres text can't hold NUL (\u0000) — some websites contain it. Strip it (and other control chars) everywhere."""
    if isinstance(v, str):
        return CTRL.sub("", v)
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    return v


db = DB()


# ---------------- Telegram ----------------
TG = f"https://api.telegram.org/bot{E['TELEGRAM_TOKEN']}/"


def tg(method, **p):
    r = httpx.post(TG + method, json=p, timeout=70)
    j = r.json()
    if not j.get("ok"):
        log("telegram error", method, j.get("description"))
    return j.get("result")


def say(text, **kw):
    if STATE.get("chat"):
        return tg("sendMessage", chat_id=STATE["chat"], text=text[:4096], disable_web_page_preview=True, **kw)


# ---------------- Gmail ----------------
def build_mime(body):
    """Plain text for English. Arabic gets an HTML part with dir=rtl (Gmail shows plain text left-to-right) plus the plain-text fallback."""
    if len(re.findall(r"[؀-ۿ]", body)) < len(re.findall(r"[A-Za-z]", body)):
        return MIMEText(body, "plain", "utf-8")
    from email.mime.multipart import MIMEMultipart
    import html as _html
    esc = _html.escape(body)
    esc = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" dir="ltr">\1</a>', esc)
    paras = "".join(f'<p dir="rtl" style="margin:0 0 14px">{p.replace(chr(10), "<br>")}</p>' for p in esc.split("\n\n"))
    html_body = (f'<div dir="rtl" lang="ar" style="direction:rtl;text-align:right;font-family:Tahoma,Arial,sans-serif;'
                 f'font-size:15px;line-height:1.8;color:#222">{paras}</div>')
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(body, "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    return alt


def current_cap():
    """Daily limit that grows only while mail stays healthy: DAILY_CAP, +RAMP_STEP every RAMP_DAYS sending days, up to DAILY_MAX.
    Bounces (read from the inbox) freeze the growth, and a high rate sends the limit back to DAILY_CAP."""
    base, top = int(E.get("DAILY_CAP", "20")), int(E.get("DAILY_MAX", "40"))
    step, every = int(E.get("RAMP_STEP", "5")), int(E.get("RAMP_DAYS", "3"))
    log_ = STATE.get("sent_log", {})
    days_sent = sum(1 for v in log_.values() if v > 0)
    cap = min(top, base + step * (days_sent // every))
    week = [(date.today() - timedelta(days=i)).isoformat() for i in range(7)]
    sent7, bad7 = sum(log_.get(d, 0) for d in week), sum(1 for d in STATE.get("bounces", {}).values() if d in week)
    rate = bad7 / sent7 if sent7 >= 20 else 0
    if rate > 0.08:
        return base, rate
    if rate > 0.04:
        return min(cap, int(STATE.get("held_cap") or cap)), rate
    STATE["held_cap"] = cap
    return cap, rate


def check_bounces():
    """Read bounce notices (MAILER-DAEMON) from Gmail over IMAP, remember the failed addresses, mark those leads' email as bad."""
    import imaplib, email as _email
    since = (date.today() - timedelta(days=7)).strftime("%d-%b-%Y")
    found = {}
    box = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    try:
        box.login(E["GMAIL_USER"], E["GMAIL_APP_PASSWORD"].replace(" ", ""))
        box.select("INBOX", readonly=True)
        _, ids = box.search(None, f'(SINCE {since} OR OR FROM "mailer-daemon" FROM "postmaster" SUBJECT "Undeliverable")')
        for i in ids[0].split()[-100:]:
            _, data = box.fetch(i, "(RFC822)")
            msg = _email.message_from_bytes(data[0][1])
            text = ""
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    text += (part.get_payload(decode=True) or b"").decode("utf-8", "ignore") + "\n"
                elif part.get_content_type() == "message/delivery-status":  # payload = list of header blocks, not text
                    pl = part.get_payload()
                    text += "\n".join(str(x) for x in (pl if isinstance(pl, list) else [pl])) + "\n"
            for addr in set(re.findall(r"(?:Final-Recipient:\s*rfc822;|wasn['’]t delivered to|to the following address[^\n]*\n+)\s*<?([\w.+-]+@[\w.-]+\.\w+)", text, re.I)):
                found[addr.lower()] = date.today().isoformat()
    finally:
        try:
            box.logout()
        except Exception:
            pass
    new = {a: d for a, d in found.items() if a not in STATE.setdefault("bounces", {}) and a != E["GMAIL_USER"].lower()}
    for addr, d in new.items():
        STATE["bounces"][addr] = d
        for L in db.get("leads", select="id,profile", **{"profile->contact->>email": f"eq.{addr}"}):
            prof = {k: v for k, v in (L.get("profile") or {}).items() if k != "contact"}  # their address bounced: back to info@
            db.patch("leads", {"id": L["id"]}, {"profile": prof})
        for L in db.get("leads", select="id,profile", email=f"ilike.{addr}"):
            prof = {**(L.get("profile") or {}), "email_check": {"ok": False, "role": False, "reason": "ارتدّ البريد (bounce)"}}
            db.patch("leads", {"id": L["id"]}, {"profile": prof})
    if new:
        log(f"bounces: {list(new)}")
        cap, rate = current_cap()
        if rate > 0.04:
            say(f"⚠️ ارتدادات البريد {rate:.0%} آخر 7 أيام — جمّدت رفع الحد (الحد اليوم {cap}). راجع قائمة الإيميلات.")
    save_state()


FREE_MAIL = {"gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com"}
AUTO_SUBJ = re.compile(r"automatic reply|auto.?reply|out of (the )?office|autoreply|away from|on leave|رد تلقائي|ردّ تلقائي|إجابة تلقائية|خارج المكتب", re.I)
SYSTEM_SENDER = re.compile(r"^(postmaster|mailer-daemon|no-?reply|do-?not-?reply|notifications?|newsletters?|bounces?)@", re.I)
BOUNCE_SUBJ = re.compile(r"undeliverable|delivery (status|has failed|failure)|mail delivery failed|returned mail|not delivered", re.I)
QUOTE_START = re.compile(r"^(on .{5,200} wrote:|في .{5,200} كتب.{0,20}:|-{2,}\s*original message|from:\s|sent from my|من:\s)", re.I | re.M)


def _plain_body(msg):
    """The reply text only: first text/plain part (HTML stripped as a fallback), quoted thread and '>' lines removed."""
    import html as _html
    text = ""
    for ctype in ("text/plain", "text/html"):
        for part in msg.walk():
            if part.get_content_type() == ctype and not part.get_filename():
                raw = part.get_payload(decode=True) or b""
                text = raw.decode(part.get_content_charset() or "utf-8", "ignore")
                if ctype == "text/html":
                    text = _html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", text)))
                break
        if text.strip():
            break
    m = QUOTE_START.search(text)
    if m:
        text = text[:m.start()]
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith(">"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()[:4000]


def _lead_for(addr, is_reply):
    """The lead this sender belongs to: exact email first, else same company domain (never for gmail/hotmail…) among leads we
    wrote to, and only when the mail really answers something (Re: / In-Reply-To) — a newsletter from their domain is not a reply."""
    rows = db.get("leads", select="id,name,status,email,followups", email=f"ilike.{addr}", deleted_at="is.null", limit="2") \
        or db.get("leads", select="id,name,status,email,followups", deleted_at="is.null", limit="2", **{"profile->contact->>email": f"eq.{addr}"})
    if rows:
        return rows[0]
    dom = addr.split("@")[-1]
    if dom in FREE_MAIL or not is_reply:
        return None
    rows = db.get("leads", select="id,name,status,email,followups", email=f"ilike.*@{dom}", deleted_at="is.null",
                  status="in.(contacted,replied,meeting,won)", limit="2")
    return rows[0] if len(rows) == 1 else None  # two contacted leads on one domain → ambiguous, skip


def check_inbox():
    """Every few minutes: read new mail over IMAP (read-only, nothing is marked read). Bounces → bad email.
    A reply from a lead → logged in the site, follow-ups stopped, queued drafts cancelled, Telegram alert + a reply draft written."""
    import imaplib, email as _email
    from email.header import decode_header, make_header
    from email.utils import parseaddr, parsedate_to_datetime
    seen = STATE.setdefault("inbox_seen", [])
    since = (date.today() - timedelta(days=3)).strftime("%d-%b-%Y")
    me = E["GMAIL_USER"].lower()
    box = imaplib.IMAP4_SSL("imap.gmail.com", timeout=30)
    replies = []
    try:
        box.login(E["GMAIL_USER"], E["GMAIL_APP_PASSWORD"].replace(" ", ""))
        box.select("INBOX", readonly=True)
        _, ids = box.search(None, f'(SINCE {since} NOT FROM "{me}" NOT FROM "mailer-daemon")')
        ids = ids[0].split()[-200:]
        heads = []
        if ids:  # all headers in ONE round trip (the Telegram buttons wait while this runs)
            _, data = box.fetch(b",".join(ids), "(BODY.PEEK[HEADER.FIELDS (FROM MESSAGE-ID SUBJECT IN-REPLY-TO REFERENCES LIST-UNSUBSCRIBE PRECEDENCE)])")
            heads = [(re.match(rb"(\d+)", d[0]).group(1), _email.message_from_bytes(d[1])) for d in data if isinstance(d, tuple)]
        for i, head in heads:
            mid = (head.get("Message-ID") or f"{i.decode()}-{head.get('From')}").strip()
            if mid in seen:
                continue
            addr = parseaddr(head.get("From") or "")[1].lower()
            subj0 = str(make_header(decode_header(head.get("Subject") or "")))
            bulk = bool(head.get("List-Unsubscribe")) or (head.get("Precedence") or "").lower() in ("bulk", "list", "junk")
            if "@" not in addr or bulk or SYSTEM_SENDER.match(addr) or BOUNCE_SUBJ.search(subj0):
                seen.append(mid)  # newsletters, bounces, system mail: never a conversation
                continue
            is_reply = bool(head.get("In-Reply-To") or head.get("References") or re.match(r"\s*(re|aw|sv|رد)\s*:", subj0, re.I))
            L = _lead_for(addr, is_reply)
            if not L:
                seen.append(mid)
                continue
            _, data = box.fetch(i, "(BODY.PEEK[])")
            msg = _email.message_from_bytes(data[0][1])
            subject = str(make_header(decode_header(msg.get("Subject") or "")))
            auto = bool(msg.get("Auto-Submitted", "no").lower() != "no" or msg.get("X-Autoreply") or AUTO_SUBJ.search(subject))
            try:
                when = parsedate_to_datetime(msg.get("Date")).astimezone().isoformat()
            except Exception:
                when = datetime.now().astimezone().isoformat()
            replies.append((mid, L, addr, subject, _plain_body(msg), when, auto))
    finally:
        try:
            box.logout()
        except Exception:
            pass
    STATE["inbox_seen"] = seen[-3000:]
    save_state()
    for mid, L, addr, subject, body, when, auto in replies:
        process_reply(L, addr, subject, body, when, auto)
        STATE["inbox_seen"].append(mid)  # only once it is saved: a database hiccup means we try again next round
        save_state()


REFUSAL = re.compile(r"\b(unsubscribe|remove (me|us|our)|take (me|us) off|stop (e-?mailing|contacting|writing)|do not (contact|email|write)|don['’]?t (contact|email|write)|"
                     r"not interested|no,? thank(s| you)|we (are|['’]re) not looking|please stop)\b|"
                     r"إلغاء الاشتراك|أزيلو|احذفو|لا (نرغب|نحتاج|حاجة)|غير مهتم|لا تراسل|توقفوا عن|نعتذر عن عدم|شكرا[ًا]?،? لا", re.I)


def is_refusal(body):
    """A clear "no" or "remove me". Code decides, no model: a refusal must always be honoured, an unclear reply gets a human answer."""
    first = (body or "")[:600]  # their words, not the quoted thread
    return bool(REFUSAL.search(first))


def process_reply(L, addr, subject, body, when, auto):
    if not body:
        body = "(رسالة بلا نص — افتحها في Gmail)"
    db.req("POST", "lead_messages", body={"lead_id": L["id"], "channel": "email", "direction": "in", "subject": subject or None,
                                          "body": body, "created_at": when})
    if auto:  # out-of-office: keep it in the history, but it is not a conversation
        log(f"auto-reply from {L['name']}")
        return
    if is_refusal(body):
        STATE.setdefault("do_not_contact", {})[addr] = date.today().isoformat()
        save_state()
        db.patch("leads", {"id": L["id"]}, {"status": "lost", "needs_reply": False, "next_action_at": None})
        db.req("PATCH", "lead_messages", {"lead_id": f"eq.{L['id']}", "draft": "eq.true", "review": "in.(pending,approved,write,failed)"},
               {"review": "rejected", "review_note": "أُلغيت: طلبوا عدم المراسلة"})
        log(f"🚫 {L['name']} declined — closed, never contacted again")
        say(f"🚫 {L['name']} ({addr}) ردّوا بالرفض أو طلبوا عدم المراسلة:\n────────\n{body[:800]}\n────────\n"
            "صنّفتهم «لم تنجح» ولن يكتب لهم النظام مرة أخرى. إن رأيت أن الرد يستحق جواباً شخصياً، اكتبه بنفسك.")
        return
    db.patch("leads", {"id": L["id"]}, {"status": "meeting" if L["status"] in ("meeting", "won") else "replied",
                                        "needs_reply": True, "next_action_at": date.today().isoformat()})
    # A follow-up written before they answered must never go out now.
    db.req("PATCH", "lead_messages", {"lead_id": f"eq.{L['id']}", "draft": "eq.true", "review": "in.(pending,approved,write,failed)"},
           {"review": "rejected", "review_note": "أُلغيت تلقائياً: العميل ردّ"})
    db.req("POST", "lead_messages", body={"lead_id": L["id"], "channel": "email", "direction": "out", "draft": True,
                                          "review": "write", "body": ""})
    log(f"📩 reply from {L['name']} <{addr}>")
    say(f"📩 ردّ من {L['name']} ({addr})\nالموضوع: {subject or '—'}\n────────\n{body[:1500]}\n────────\n"
        "أوقفت المتابعات لهذا العميل، وأكتب لك مسودة ردّ تصلك هنا للموافقة.")


class Capped(RuntimeError):
    """Daily limit reached: the message stays approved and goes out by itself the next day."""


def send_email(to, subject, body, cc=None, rush=False):
    import emailcheck
    cap, _rate = current_cap()
    if rush:
        cap += int(E.get("RUSH_EXTRA", "5"))  # an opportunity closing soon may go a little over the day's limit, never far
    today = date.today().isoformat()
    if STATE.get("sent_day") != today:
        STATE.update(sent_day=today, sent_count=0)
    if STATE["sent_count"] >= cap:
        raise Capped(f"مؤجلة: وصلت للحد اليومي ({cap}) — تُرسل تلقائياً غداً")
    m = re.fullmatch(r"\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})[\s\\/.,;]*", to or "")
    if not m:
        raise RuntimeError(f"عنوان الإيميل غير صالح: {to!r} — صحّحه في صفحة العميل")
    to = m.group(1)
    chk = emailcheck.check(to)
    if chk["ok"] is False:
        raise RuntimeError(f"الإيميل لن يصل ({chk['reason']}): {to} — صحّحه أو استخدم واتساب")
    if to.lower() in STATE.get("bounces", {}):
        raise RuntimeError(f"هذا الإيميل ارتدّ سابقاً: {to}")
    msg = build_mime(body)
    msg["Subject"] = subject or E.get("SENDER_NAME", "")
    msg["From"] = formataddr((E.get("SENDER_NAME", ""), E["GMAIL_USER"]))
    msg["To"] = to
    if cc and cc.lower() != to.lower():
        msg["Cc"] = cc
    msg["Message-ID"] = make_msgid(domain=E["GMAIL_USER"].split("@")[-1])
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(E["GMAIL_USER"], E["GMAIL_APP_PASSWORD"].replace(" ", ""))
        s.send_message(msg)
    STATE["sent_count"] += 1
    log_ = STATE.setdefault("sent_log", {})  # per-day counts drive the gradual cap and the bounce rate
    log_[today] = log_.get(today, 0) + 1
    STATE["sent_log"] = {d: n for d, n in log_.items() if d >= (date.today() - timedelta(days=60)).isoformat()}
    save_state()


def recipients(L):
    """(to, cc). The decision maker's own public address goes in To and the general one (info@…) in Cc, so the message reaches
    the person who decides while the organisation sees it too. Falls back to the general address alone."""
    c = (L.get("profile") or {}).get("contact") or {}
    pe, ge = (c.get("email") or "").strip().lower(), (L.get("email") or "").strip()
    if pe and pe not in STATE.get("bounces", {}) and pe != ge.lower():
        return pe, ge or None
    return ge, None


def is_rush(m, L):
    """Sent at once, outside working hours and the spacing: ⚡ chosen by Ahmad, a tender/opportunity closing within 7 days,
    or an answer to someone who replied (a quick answer is what a human does)."""
    soon = (date.today() + timedelta(days=int(E.get("RUSH_DAYS", "7")))).isoformat()
    return ((m.get("review_note") or "").startswith("⚡")
            or bool(L.get("signal") and L.get("signal_until") and L["signal_until"] <= soon)
            or L.get("status") in ("replied", "meeting") or bool(L.get("needs_reply")))


def in_send_window():
    """Working hours on working days (local PC time): mail arrives when people read it."""
    h0, h1 = (int(x) for x in E.get("SEND_HOURS", "9-17").split("-"))
    off = {int(x) for x in E.get("OFF_DAYS", "4,5").split(",") if x.strip()}  # Monday=0 … Friday=4, Saturday=5
    now = datetime.now()
    return now.weekday() not in off and h0 <= now.hour < h1


def wa_link(phone, text):
    d = "".join(c for c in phone or "" if c.isdigit())
    if d.startswith("00"):
        d = d[2:]
    if d.startswith("0"):
        d = "962" + d[1:]
    return f"https://wa.me/{d}?text={quote(text)}"


# ---------------- Safety gate (deterministic, fails closed) ----------------
BANNED = ["i hope this", "i wanted to reach out", "just following up", "just checking in", "leverage", "elevate",
          "next level", "unlock", "best price", "discount", "limited time", "عرض خاص", "أسعار منافسة", "خصم",
          "يسعدنا أن نضع بين أيديكم", "نقلة نوعية", "حلول متكاملة", "لا تتردد"]
PRICE = re.compile(r"(\d[\d,.]*\s*(د\.?أ|دينار|jod|jd|usd|\$|€))|((\$|€)\s*\d)", re.I)
URL = re.compile(r"(https?://[^\s)>\]]+|(?:www\.)?[a-z0-9-]+\.(?:com|net|org|app|io|jo|be)/[^\s)>\]]*)", re.I)
_allowed = {"t": 0, "urls": set()}


def allowed_urls():
    """Only Ahmad's full bodies of work may be linked (his choice): personal site, team site, Behance profile."""
    if not _allowed["urls"]:
        links = E.get("ALLOWED_LINKS") or "ahmadhaddad.lovable.app,behance.net/gallery/243985595/_,behance.net/gallery/242646259/duroub-with-alma,behance.net/gallery/242646259,behance.net/gallery/237148893/duroub-school,behance.net/gallery/237148893,behance.net/gallery/243985595,behance.net/ahmad00haddad,behance.com/ahmad00haddad"
        _allowed["urls"] = {u.strip().lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/") for u in links.split(",") if u.strip()}
    return _allowed["urls"]


PLACE_OR_YEAR = re.compile(
    r"\b(19|20)\d{2}\b|[٠-٩]{4}|\b(in|at)\s+(amman|irbid|zarqa|ramtha|mafraq|aqaba|salt|madaba|jerash|karak|ajloun|azraq|zaatari|petra|tafileh|ma'?an|jordan valley)\b"
    r"|في\s+(عمّ?ان|إ?اربد|الزرقاء|الرمثا|المفرق|العقبة|السلط|مادبا|جرش|الكرك|عجلون|الأزرق|الزعتري|البتراء|الطفيلة|معان|الأغوار|منطقة)", re.I)
_clients = {"t": 0, "names": []}


def past_client_names():
    """Names from the PAST CLIENTS list in team settings (refreshed every 10 min)."""
    if time.time() - _clients["t"] > 600:
        st = (db.get("app_settings", select="data", id="eq.1") or [{}])[0].get("data") or {}
        names = [l.split("|")[0].strip() for l in (st.get("pastClients") or "").splitlines() if l.strip()]
        names += [re.sub(r"\s*\(.*?\)", "", n) for n in names] + re.findall(r"\(([A-Z]{2,8})\)", st.get("pastClients") or "")
        _clients.update(t=time.time(), names=[n for n in set(names) if len(n) >= 3])
    return _clients["names"]


def email_site_mismatch(L):
    """True when the email clearly belongs to another organisation: its domain and the website's share no name
    (mercycorps.org vs prosperglobal.org). Free mail (gmail…) and leads without a website are not judged."""
    em, site = (L.get("email") or "").lower(), (L.get("website") or "").lower()
    if "@" not in em or not site:
        return False
    ed = em.split("@")[-1]
    if ed in FREE_MAIL:
        return False
    host = re.sub(r"^https?://", "", site.split("%20")[0].split()[0]).split("/")[0].removeprefix("www.")
    if not host or "." not in host:
        return False
    stop = {"com", "org", "net", "jo", "gov", "edu", "int", "co", "ac", "info", "www"}
    names = lambda d: {w for w in re.split(r"[.\-]", d) if len(w) > 2 and w not in stop}
    a, b = names(ed), names(host)
    words = re.findall(r"[a-z]+", (L.get("name") or "").lower())
    inits = ("".join(w[0] for w in words), "".join(w[0] for w in words if w not in {"of", "for", "the", "and", "to"}))
    if any(len(x) >= 2 and x in i for x in a for i in inits):
        return False  # gfp.ngo = Generations For Peace
    return bool(a and b) and not any(x in y or y in x for x in a for y in b)


def gate(m, L):
    """Returns a list of reasons to block. Empty list = safe to send. Any doubt → block."""
    body, subj = m.get("body") or "", m.get("subject") or ""
    text = (subj + "\n" + body).lower()
    why = []
    if len(body.strip()) < 40:
        why.append("الرسالة قصيرة جداً أو فارغة")
    if re.search(r"\{\{?[^}]*\}\}?|\[(name|اسم|company|link)[^\]]*\]|<[A-Z_]+>|xxx", body, re.I):
        why.append("فيها خانة لم تُعبّأ مثل {name}")
    for b in BANNED:
        if b in text:
            why.append(f"عبارة ممنوعة: «{b}»")
    if PRICE.search(body) and L.get("status") in ("new", "contacted", None):
        why.append("تذكر سعراً في رسالة تعريف — الأسعار فقط بعد أن يردّوا")
    ok = allowed_urls()
    for u in URL.findall(body):
        n = u.rstrip("/.,").lower().replace("https://", "").replace("http://", "").replace("www.", "")
        if not any(n == a or n.startswith(a + "/") and a.count("/") >= n.count("/") - 1 and "gallery" not in n for a in ok):
            why.append(f"رابط غير مسموح (المسموح: موقعك، موقع الفريق، Behance فقط): {u}")
    try:
        import local_ai
        wrong = local_ai.wrong_proof(L, body) if L.get("kind") else []
    except Exception:
        wrong = []
    if wrong:
        why.append(f"يذكر أسماء عملاء سابقين (قاعدتك: لا أسماء، الموقع يعرضهم): {', '.join(wrong)}")
    if L.get("status") in ("new", None) and not re.search(r"فيلم|أفلام|نصوّر|نصور|صوّرت|صورت|ريل|film|shoot|video|reel|documentary", body, re.I):
        why.append("لا توضح أنها عرض تصوير/فيلم — قد تُفهم كتعليق أو شكوى")
    if re.search(r"(بعنوان|تحت عنوان|titled|entitled|called)\s*[«\"“'‘]", body, re.I):
        why.append("يقترح اسماً/عنواناً لفيلم — ممنوع")
    for sent in re.split(r"(?<=[.؟?!\n])", body):
        if any(c and c.lower() in sent.lower() for c in past_client_names()) and PLACE_OR_YEAR.search(sent):
            why.append(f"تفصيل غير موثّق عن عمل سابق (مكان/سنة): «{sent.strip()[:90]}»")
    if m["channel"] == "email" and len(body) > 1600 and not (L.get("status") in ("replied", "meeting")):
        why.append("أطول من اللازم لرسالة أولى")
    if L.get("status") in ("lost", "skip"):
        why.append("العميل مغلق (رفض أو تجاهل)")
    try:
        import local_ai
        for t in local_ai.ai_tells(body):
            why.append(f"تبدو مكتوبة بالذكاء الاصطناعي: {t}")
    except Exception:
        pass
    dnc = STATE.get("do_not_contact", {})
    if m["channel"] == "email" and any((a or "").strip().lower() in dnc for a in recipients(L)):
        why.append("طلبوا عدم مراسلتهم — لن نراسلهم أبداً")
    if m["channel"] == "email" and L.get("status") in ("new", "skip", None) and L.get("email"):
        addr = L["email"].strip().lower()
        other = db.get("leads", select="name,status", email=f"ilike.{addr}", id=f"neq.{L['id']}", status="in.(contacted,replied,meeting,won,lost)", limit="1")
        sent = db.get("lead_messages", select="id", lead_id=f"eq.{L['id']}", direction="eq.out", draft="eq.false", limit="1")
        if other or sent:
            why.append(f"راسلنا هذا الإيميل سابقاً ({other[0]['name'] if other else 'نفس العميل'}) — لا رسالة أولى ثانية")
    return why


# ---------------- Approval flow ----------------
KIND = {"ngo": "منظمة", "org": "مؤسسة", "restaurant": "مطعم", "pharmacy": "صيدلية", "school": "مدرسة", "brand": "براند", "hotel": "فندق", "event": "فعاليات", "other": "أخرى"}
CH = {"email": "✉️ إيميل", "whatsapp": "💬 واتساب", "instagram": "📷 إنستغرام"}


def card(m):
    L = m["leads"]
    to = L.get("email") if m["channel"] == "email" else L.get("phone") if m["channel"] == "whatsapp" else L.get("instagram")
    head = f"{CH.get(m['channel'], m['channel'])} → {L['name']} ({KIND.get(L['kind'], L['kind'])})\nإلى: {to or '— غير متوفر'}"
    if m["channel"] == "email":
        pto, pcc = recipients(L)
        if pcc:
            c = (L.get("profile") or {}).get("contact") or {}
            head = head.replace(f"إلى: {to}", f"إلى: {pto} ({c.get('name', '')} — {c.get('role', '')})\nنسخة: {pcc}")
    if L.get("score") is not None:
        head += f" · تقييم {L['score']}"
    if L.get("signal"):
        head += f"\n🔔 {L['signal']}"
    if m["channel"] == "email" and email_site_mismatch(L):
        head += f"\n⚠️ انتبه: الإيميل لا يشبه موقعهم ({L.get('website')}) — قد يكون لجهة أخرى. تأكد قبل الموافقة."
    subj = f"\nالموضوع: {m['subject']}" if m.get("subject") else ""
    return f"{head}{subj}\n────────\n{m['body']}"


def buttons(mid):
    return {"inline_keyboard": [[{"text": "✅ أرسل", "callback_data": f"ok:{mid}"},
                                 {"text": "⚡ الآن", "callback_data": f"now:{mid}"},
                                 {"text": "✏️ عدّل", "callback_data": f"ed:{mid}"},
                                 {"text": "❌ ارفض", "callback_data": f"no:{mid}"}]]}


_push_lock = threading.Lock()


def push_pending():
    if STATE.get("paused"):
        return
    with _push_lock:
        _push_pending()


def _push_pending():
    rows = db.get("lead_messages", select="*,leads(*)", review="eq.pending", tg_message_id="is.null", order="created_at", limit="10")
    for m in rows:
        text = card(m)
        body = m.get("body") or ""
        if len(re.findall(r"[A-Za-z]", body)) > 3 * len(re.findall(r"[؀-ۿ]", body)) + 20:  # mostly English
            try:
                import local_ai
                model = _local.get("model") or local_model()
                if model:
                    ar = local_ai.translate_ar(body, model)
                    if ar:  # empty when the translation came out in the wrong script — better nothing than garbage
                        text += "\n\n🔤 الترجمة لك فقط (لا تُرسل):\n" + ar
            except Exception as e:
                log("translation failed:", e)
        r = say(text, reply_markup=buttons(m["id"]))
        if r:
            db.patch("lead_messages", {"id": m["id"]}, {"tg_message_id": r["message_id"]})


def after_send(L):
    if L["status"] in ("new", "skip"):
        patch = {"status": "contacted", "next_action_at": (date.today() + timedelta(days=7)).isoformat(), "needs_reply": False}
    elif L["status"] == "contacted":
        patch = {"followups": L["followups"] + 1, "next_action_at": None, "needs_reply": False}
    else:
        patch = {"needs_reply": False}
    db.patch("leads", {"id": L["id"]}, patch)


def approve(mid, tg_mid):
    rows = db.get("lead_messages", select="*,leads(*)", id=f"eq.{mid}")
    if not rows or not rows[0].get("leads"):
        return "🚫 هذه المسودة لم تعد موجودة (استُبدلت أو حُذفت)"
    m, L = rows[0], rows[0]["leads"]
    import local_ai
    if local_ai.is_blocked(L):  # last gate before anything is sent
        return "⛔ هذا العميل على قائمة الاستبعاد (tools/harvester/blocklist.txt): لم يُرسل شيء"
    if mid in STATE.get("sent_mids", []) and m["review"] != "sent":
        mark_sent(mid, L)  # it went out earlier but the database never heard: record it, never send again
        return "أُرسلت مسبقاً"
    if m["review"] == "sent":
        return "أُرسلت مسبقاً"
    if m["review"] == "rejected":
        return f"🚫 لم تُرسل — {m.get('review_note') or 'المسودة مرفوضة'}"
    problems = gate(m, L)
    if problems:
        db.patch("lead_messages", {"id": mid}, {"review": "failed", "review_note": " · ".join(problems)[:300]})
        return "🛑 لم تُرسل — الفحص أوقفها:\n• " + "\n• ".join(problems) + "\nعدّلها (✏️ من الموقع) ثم أعد إرسالها للموافقة."
    if m["channel"] == "email":
        to, cc = recipients(L)
        if not to:
            return "لا يوجد إيميل لهذا العميل"
        send_email(to, m.get("subject"), m["body"], cc=cc, rush=is_rush(m, L))
        STATE["sent_mids"] = (STATE.get("sent_mids", []) + [mid])[-500:]  # remembered before the database is told
        STATE["next_send_at"] = time.time() + random.randint(int(E.get("GAP_MIN", "8")), int(E.get("GAP_MAX", "20"))) * 60
        save_state()
        done = f"✅ أُرسلت إلى {to}" + (f" (نسخة: {cc})" if cc else "")
    elif m["channel"] == "whatsapp":
        if not L.get("phone"):
            return "لا يوجد رقم لهذا العميل"
        say(f"اضغط لإرسالها من واتسابك إلى {L['name']}:", reply_markup={"inline_keyboard": [[{"text": "💬 افتح واتساب", "url": wa_link(L["phone"], m["body"])}]]})
        done = "✅ جاهزة في واتساب"
    else:
        say(m["body"])
        done = f"✅ انسخ الرسالة أعلاه وأرسلها في الدايركت: {L.get('instagram') or ''}"
    mark_sent(mid, L)
    return done


def mark_sent(mid, L):
    now = datetime.utcnow().isoformat()
    db.patch("lead_messages", {"id": mid}, {"review": "sent", "review_note": None, "draft": False, "sent_at": now, "created_at": now})
    after_send(L)


def enqueue(mid, rush=False):
    """✅: emails are checked now and wait in the queue (one every 8–20 min in working hours); WhatsApp/Instagram and ⚡ go at once."""
    rows = db.get("lead_messages", select="*,leads(*)", id=f"eq.{mid}")
    if not rows or not rows[0].get("leads"):
        return "🚫 هذه المسودة لم تعد موجودة (استُبدلت أو حُذفت)"
    m, L = rows[0], rows[0]["leads"]
    if rush:
        db.patch("lead_messages", {"id": mid}, {"review_note": "⚡ عاجل"})
        m["review_note"] = "⚡ عاجل"
    if m["channel"] != "email" or is_rush(m, L) or m["review"] in ("sent", "rejected"):
        return approve(mid, None)
    problems = gate(m, L)
    if problems:
        db.patch("lead_messages", {"id": mid}, {"review": "failed", "review_note": " · ".join(problems)[:300]})
        return "🛑 لم تُرسل — الفحص أوقفها:\n• " + "\n• ".join(problems) + "\nعدّلها (✏️ من الموقع) ثم أعد إرسالها للموافقة."
    db.patch("lead_messages", {"id": mid}, {"review": "approved", "review_note": "⏳ في طابور الإرسال"})
    n = len(db.get("lead_messages", select="id", review="eq.approved", channel="eq.email"))
    return (f"⏳ في الطابور (رقم {n}). تُرسل وقت الدوام، رسالة كل {E.get('GAP_MIN', '8')}–{E.get('GAP_MAX', '20')} دقيقة."
            " للإرسال فوراً اضغط ⚡ على البطاقة أو من الموقع.")


def hold_capped(mid, e):
    db.patch("lead_messages", {"id": mid}, {"review": "approved", "review_note": str(e)[:300]})
    if STATE.get("capped_day") != date.today().isoformat():
        STATE["capped_day"] = date.today().isoformat()
        save_state()
        say(f"⏸ {e}")


def send_site_approved():
    """The sending queue (approved on Telegram or the site). Urgent ones and WhatsApp/Instagram go at once. Other emails go ONE
    at a time, 8–20 random minutes apart, in working hours only: a burst of identical-looking mail is what spam filters catch."""
    rows = db.get("lead_messages", select="id,tg_message_id,channel,review_note,leads(status,signal,signal_until,needs_reply)",
                  review="eq.approved", order="created_at", limit="50")
    capped = STATE.get("capped_day") == date.today().isoformat()
    urgent = [m for m in rows if m["channel"] != "email" or is_rush(m, m.get("leads") or {})]
    normal = [m for m in rows if m not in urgent]
    paced_ok = in_send_window() and time.time() >= STATE.get("next_send_at", 0) and not capped
    for m in urgent + (normal[:1] if paced_ok else []):
        try:
            say(approve(m["id"], m["tg_message_id"]))
        except Capped as e:
            hold_capped(m["id"], e)
            if m in normal:
                break
        except Exception as e:
            db.patch("lead_messages", {"id": m["id"]}, {"review": "failed", "review_note": str(e)[:300]})
            say(f"⚠️ {e}")


def on_callback(q):
    if str(q["message"]["chat"]["id"]) != str(STATE.get("chat")):
        return
    action, mid = q["data"].split(":", 1)
    tg_mid = q["message"]["message_id"]
    tg("answerCallbackQuery", callback_query_id=q["id"], text="⏳")  # instantly, so Telegram never times out
    try:
        if action in ("ok", "now"):
            try:
                res = enqueue(mid, rush=action == "now")
            except Capped as e:
                hold_capped(mid, e)
                res = f"⏸ {e}"
        elif action == "no":
            db.patch("lead_messages", {"id": mid}, {"review": "rejected"})
            res = "❌ رُفضت"
        else:
            STATE["editing"] = mid
            save_state()
            res = "✏️ أرسل لي النص الجديد للرسالة كاملاً (أول سطر يبدأ بـ «الموضوع:» إن أردت تغيير العنوان)"
    except Exception as e:
        db.patch("lead_messages", {"id": mid}, {"review_note": str(e)[:300]})
        res = f"⚠️ {e}"
    tg("editMessageReplyMarkup", chat_id=STATE["chat"], message_id=tg_mid, reply_markup={"inline_keyboard": []})
    say(res)


def on_text(msg):
    chat, text = msg["chat"]["id"], (msg.get("text") or "").strip()
    if text == "/start" and not STATE.get("chat"):
        STATE["chat"] = chat
        save_state()
        say("أهلاً أحمد 👋 ربطت هذا الحساب بالوكيل. ستصلك هنا الرسائل للموافقة والتقرير الصباحي.\nالأوامر: /report /queue /analyze /opps /pause /resume")
        return
    if str(chat) != str(STATE.get("chat")):
        return  # only the owner can control the agent
    if STATE.get("editing") and not text.startswith("/"):
        mid = STATE.pop("editing")
        save_state()
        patch = {"tg_message_id": None, "review": "pending"}
        if text.startswith("الموضوع:"):
            first, _, rest = text.partition("\n")
            patch["subject"], text = first.replace("الموضوع:", "").strip(), rest.strip()
        patch["body"] = text
        db.patch("lead_messages", {"id": mid}, patch)
        push_pending()
        return
    if text == "/report":
        report()
    elif text == "/queue":
        n = len(db.get("lead_messages", select="id", review="eq.pending"))
        say(f"في الانتظار: {n}")
        db.req("PATCH", "lead_messages", {"review": "eq.pending"}, {"tg_message_id": None})
        push_pending()
    elif text == "/analyze":
        left = len(db.get("leads", select="id", profile="is.null", deleted_at="is.null", limit="2000"))
        say(f"🧠 التحليل المحلي ({_local['model'] or 'متوقف — Ollama غير شغّال'}): حلّلت {_local['done']} منذ التشغيل، وبقي {left}")
    elif text == "/opps":
        import threading
        threading.Thread(target=lambda: (run_opportunities(manual=True)), daemon=True).start()
    elif text == "/pause":
        STATE["paused"] = True; save_state(); say("⏸ أوقفت إرسال المسودات. /resume للاستئناف")
    elif text == "/resume":
        STATE["paused"] = False; save_state(); say("▶️ استأنفت"); push_pending()


# ---------------- Morning report ----------------
def report():
    leads = []
    for off in range(0, 20000, 1000):
        page = db.req("GET", "leads", {"select": "id,name,kind,status,score,email,phone,signal,signal_until,next_action_at,needs_reply,followups,deal_value",
                                       "deleted_at": "is.null", "offset": off, "limit": 1000})
        leads += page
        if len(page) < 1000:
            break
    t = date.today().isoformat()
    replies = [l for l in leads if l["needs_reply"]]
    follow = [l for l in leads if l["status"] == "contacted" and l["next_action_at"] and l["next_action_at"] <= t and l["followups"] < 1]
    signals = sorted([l for l in leads if l["signal"] and (not l["signal_until"] or l["signal_until"] >= t) and l["status"] not in ("won", "lost", "skip")],
                     key=lambda l: l["signal_until"] or "9")
    best = sorted([l for l in leads if l["status"] == "new" and l["score"] is not None and (l["email"] or l["phone"])], key=lambda l: -l["score"])
    pending = db.get("lead_messages", select="id", review="eq.pending")
    pipe = sum(float(l["deal_value"] or 0) for l in leads if l["status"] in ("replied", "meeting"))
    won = sum(float(l["deal_value"] or 0) for l in leads if l["status"] == "won")
    lines = [f"☀️ صباح الخير — تقرير {t}",
             f"🔥 ردود تنتظرك: {len(replies)}" + "".join(f"\n   • {l['name']}" for l in replies[:5]),
             f"🔔 فرص مفتوحة الآن: {len(signals)}" + "".join(f"\n   • {l['name']} — {l['signal'][:60]} ({l['signal_until'] or ''})" for l in signals[:5]),
             f"↩️ متابعات مستحقة: {len(follow)}",
             f"🎯 أفضل جدد: " + "، ".join(f"{l['name']} ({l['score']})" for l in best[:5]),
             f"📤 مسودات بانتظار موافقتك: {len(pending)}",
             f"📊 {len(leads)} عميل · تواصلنا مع {sum(1 for l in leads if l['status'] not in ('new', 'skip'))} · قيد التفاوض {pipe:.0f} د.أ · صفقات {won:.0f} د.أ"]
    say("\n\n".join(lines))


# ---------------- Local analysis (Ollama on this PC, no credit) ----------------
_local = {"team": None, "t": 0, "model": None, "done": 0, "warned": False}


def nv_model():
    """NVIDIA hosted model (free tier) when a key is set; Ollama stays the automatic fallback."""
    return "nv:" + E.get("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b") if E.get("NVIDIA_API_KEY") else None


def local_model():
    import local_ai
    if nv_model():
        return nv_model()
    for m in [E.get("OLLAMA_MODEL", "qwen2.5:14b"), "qwen2.5:14b", "qwen2.5-coder:7b"]:
        if local_ai.available(m):
            return m
    return None


def analyze_one():
    """Profile the next un-analysed lead on the local GPU. Organisations first, those with a website first."""
    if E.get("LOCAL_ANALYSIS", "1") != "1" or STATE.get("paused"):
        return
    import local_ai
    if time.time() - _local["t"] > 600:
        _local.update(t=time.time(), model=local_model(),
                      team=((db.get("app_settings", select="data", id="eq.1") or [{}])[0].get("data") or {}))
    if not _local["model"]:
        if not _local["warned"]:
            log("local analysis off: Ollama not running or no model (ollama pull qwen2.5:14b)")
            _local["warned"] = True
        return
    rows = db.get("leads", select="*", profile="is.null", deleted_at="is.null",
                  **{"or": "(email.not.is.null,phone.not.is.null,instagram.not.is.null)"}, limit="40")
    if not rows:
        refresh_one()
        return
    for L in [r for r in rows if local_ai.is_blocked(r)]:  # an old client / big chain from tools/harvester/blocklist.txt
        db.patch("leads", {"id": L["id"]}, {"status": "skip", "notes": "قائمة الاستبعاد (عميل قديم أو سلسلة كبيرة)",
                                             "profile": {"summary": "مستبعد", "analysed_by": "blocklist"}, "score": 0})
        log(f"⛔ {L['name']} is on the blocklist, skipped")
    rows = [r for r in rows if not local_ai.is_blocked(r)]
    if not rows:
        return
    rank = {"pharmacy": 0, "school": 0, "ngo": 1, "org": 2, "hotel": 3, "brand": 4, "event": 5, "restaurant": 6}
    irbid = lambda L: not re.search(r"irbid|إربد|اربد", f"{L.get('city') or ''} {L.get('address') or ''}", re.I)
    rows.sort(key=lambda L: (not L.get("signal"), irbid(L), rank.get(L["kind"], 7), not L.get("website")))
    L = rows[0]
    try:
        p = local_ai.analyze(db, L, _local["team"], _local["model"])
        _local["done"] += 1
        log(f"🧠 {L['name']}: {p['score']} — {p['profile'].get('angle', '')[:80]}")
    except Exception as e:
        log(f"analysis failed for {L['name']}: {e}")
        db.patch("leads", {"id": L["id"]}, {"profile": {"summary": "تعذّر التحليل المحلي", "why": str(e)[:200], "analysed_by": "failed"}, "score": 0})


def refresh_one():
    """Nothing new to analyse: re-check an already analysed lead (fresh news, buying signal, decision makers, tier).
    Highest score first, Irbid first; each lead is re-checked at most every REFRESH_DAYS (default 14)."""
    import local_ai
    if local_ai.exa_limited():
        return  # Exa is cooling down; the same leads stay due
    cutoff = (date.today() - timedelta(days=int(E.get("REFRESH_DAYS", "14")))).isoformat()
    rows = db.get("leads", select="*", status="eq.new", deleted_at="is.null", profile="not.is.null",
                  **{"or": f"(profile->>signal_checked.is.null,profile->>signal_checked.lt.{cutoff})"}, order="score.desc.nullslast", limit="40")
    rows = [L for L in rows if (L.get("profile") or {}).get("analysed_by") != "failed" and (L.get("email") or L.get("phone") or L.get("instagram"))]
    if not rows:
        return
    irbid = lambda L: not re.search(r"irbid|إربد|اربد", f"{L.get('city') or ''} {L.get('address') or ''}", re.I)
    rows.sort(key=lambda L: (irbid(L), -(L.get("score") or 0)))
    L = rows[0]
    try:
        p = local_ai.refresh(db, L, _local["model"])
        _local["done"] += 1
        sig = p.get("signal")
        log(f"🔄 {L['name']}: {p['score']} tier {p['profile'].get('tier')}" + (f" 🔔 {sig[:70]}" if sig else ""))
    except local_ai.ExaLimit:
        log("Exa rate limit: pausing news refresh for 30 min (set EXA_API_KEY in agent.env for a real quota)")
    except Exception as e:
        log(f"refresh failed for {L['name']}: {e}")
        pr = {**(L.get("profile") or {}), "signal_checked": date.today().isoformat()}  # do not retry the same lead in a loop
        db.patch("leads", {"id": L["id"]}, {"profile": pr})


_hb = {"t": 0, "warned": False}


def heartbeat(note=None):
    """Tell the site the agent is alive (every ~20s). Missing table (migration not applied yet) is ignored."""
    if time.time() - _hb["t"] < 20 and not note:
        return
    _hb["t"] = time.time()
    try:
        db.patch("agent_status", {"id": 1}, {"last_seen": datetime.utcnow().isoformat() + "Z",
                                             "model": _local.get("model"), "note": note})
    except Exception as e:
        if not _hb["warned"]:
            log("heartbeat off (apply migration 20261009230000_agent_heartbeat.sql):", str(e)[:120])
            _hb["warned"] = True


def write_requested():
    """Drafts the site asked this PC to write (review='write'), then they go to Telegram for approval."""
    rows = db.get("lead_messages", select="*,leads(*)", review="eq.write", order="created_at", limit="1")
    if not rows:
        return
    import local_ai
    if time.time() - _local["t"] > 600 or not _local["team"]:
        _local.update(t=time.time(), model=local_model(),
                      team=((db.get("app_settings", select="data", id="eq.1") or [{}])[0].get("data") or {}))
    m, L = rows[0], rows[0]["leads"]
    if local_ai.is_blocked(L):
        db.patch("lead_messages", {"id": m["id"]}, {"review": "failed", "review_note": "على قائمة الاستبعاد: لا نراسله"})
        return
    if not _local["model"]:
        db.patch("lead_messages", {"id": m["id"]}, {"review": "failed", "review_note": "Ollama غير شغّال على الجهاز"})
        return
    hist = db.get("lead_messages", select="direction,channel,body,created_at", lead_id=f"eq.{L['id']}", draft="eq.false", order="created_at")
    history = "\n\n".join(f"[{'THEM' if h['direction'] == 'in' else 'US'} · {h['channel']} · {h['created_at'][:10]}]\n{h['body']}" for h in hist)
    mode = "reply" if L.get("needs_reply") else "followup" if L.get("status") == "contacted" else "first" if L.get("status") in ("new", "skip") else "reply"
    try:
        if not L.get("profile"):
            local_ai.analyze(db, L, _local["team"], _local["model"])
            L = db.get("leads", select="*", id=f"eq.{L['id']}")[0]
        p = L.get("profile") or {}
        general = (p.get("email_check") or {}).get("role") or re.match(r"(info|contact|hello|office|admin|mail|enquiries|inquiries)@", L.get("email") or "", re.I)
        if mode == "first" and m["channel"] == "email" and general and not p.get("people") and L.get("kind") in local_ai.ORG_KINDS:
            people = local_ai.find_people(L, _local["model"])  # who decides there (public sources only)
            if people:
                p = {**p, "people": people}
                db.patch("leads", {"id": L["id"]}, {"profile": p})
                L = {**L, "profile": p}
        if mode == "first" and m["channel"] == "email" and p.get("people") and not (p.get("contact") or {}).get("email"):
            who = local_ai.person_email(L, p["people"])
            if who:
                p = {**p, "contact": who}
                db.patch("leads", {"id": L["id"]}, {"profile": p})
                L = {**L, "profile": p}
                log(f"👤 decision maker for {L['name']}: {who['name']} <{who['email']}>")
        writer = nv_model() or E.get("WRITE_MODEL", "gemma3:12b")  # better Arabic; analysis stays on the faster model
        writer = writer if local_ai.available(writer) else _local["model"]
        subject, body = local_ai.write(L, _local["team"], history, m["channel"], mode, m.get("review_note"), writer)
        if m["channel"] != "email":
            subject = None  # WhatsApp / Instagram have no subject
        db.patch("lead_messages", {"id": m["id"]}, {"subject": subject, "body": body, "review": "pending", "review_note": None, "tg_message_id": None})
        log(f"✍️ wrote {mode} for {L['name']}")
        push_pending()
    except Exception as e:
        db.patch("lead_messages", {"id": m["id"]}, {"review": "failed", "review_note": f"الكتابة المحلية فشلت: {e}"[:300]})
        log(f"write failed for {L['name']}: {e}")


# ---------------- Global opportunities (tenders + prospects abroad) ----------------
_opp_busy = threading.Lock()


def run_opportunities(manual=False):
    """Daily scan (or /opps). New finds are saved as leads with a live signal and announced on Telegram right away."""
    if not _opp_busy.acquire(blocking=False):
        if manual:
            say("🌍 البحث عن الفرص يعمل الآن — انتظر نتيجته.")
        return
    try:
        _run_opportunities(manual)
    except Exception as e:
        log("opportunities failed:", e)
        if manual:
            say(f"⚠️ فشل البحث عن الفرص: {str(e)[:200]}")
    finally:
        _opp_busy.release()


def _run_opportunities(manual):
    import opportunities
    model = _local.get("model") or local_model()
    if not model:
        if manual:
            say("لا يوجد نموذج متاح للبحث (NVIDIA أو Ollama).")
        return
    say("🌍 أبحث عن عطاءات وفرص جديدة (الأردن أولاً ثم العالم)…") if manual else None
    saved, seen = opportunities.scan(db, model, STATE.get("opp_seen", []), log=log)
    if opportunities.limited and not saved:
        STATE["opp_day"], STATE["opp_after"] = None, time.time() + 3600  # Exa refused: retry in an hour instead of losing the day
        save_state()
        say("🌍 البحث متوقف مؤقتاً: Exa المجاني وصل حده. سأعيد المحاولة بعد ساعة. (حل دائم: مفتاح Exa مجاني من dashboard.exa.ai ثم EXA_API_KEY في agent.env)")
        return
    STATE["opp_seen"] = seen
    save_state()
    if not saved:
        say("🌍 لا فرص جديدة الآن.") if manual else None
        return
    lines = [f"🌍 {len(saved)} فرصة جديدة (الأردن أولاً):"]
    for o in saved[:8]:
        due = f" — آخر موعد {o['deadline']}" if o["deadline"] else ""
        lines.append(f"\n{'🇯🇴 ' if o.get('jo') else ''}{o['org']}{due}\n{o['what'][:150]}\n{o['url']}")
    lines.append("\nتجدها في الموقع: تبويب 🔔 فرص الآن. اكتب لها من زر «اكتب لأفضل 10».")
    say("\n".join(lines))


# ---------------- Main loop ----------------
def worker():
    """Local AI work (writing + analysis) in its own thread: a 40s Gemma call never blocks the Telegram buttons."""
    while True:
        try:
            if not STATE.get("paused"):
                write_requested()
                analyze_one()
        except Exception as e:
            log("worker error:", e)
        time.sleep(3)


def main():
    threading.Thread(target=worker, daemon=True).start()
    log("FAII Agent started. Open Telegram and send /start to your bot." if not STATE.get("chat") else "FAII Agent started.")
    offset, last_push, last_bounce, report_hour = STATE.get("offset", 0), 0, 0, int(E.get("REPORT_HOUR", "8"))
    while True:
        try:
            ups = tg("getUpdates", offset=offset, timeout=20) or []
            for u in ups:
                offset = u["update_id"] + 1
                if "callback_query" in u:
                    on_callback(u["callback_query"])
                elif "message" in u:
                    on_text(u["message"])
            STATE["offset"] = offset
            save_state()
            heartbeat()
            if STATE.get("chat") and time.time() - last_push > 60:
                push_pending()
                send_site_approved()
                last_push = time.time()
            if time.time() - last_bounce > 300:  # inbox: replies + bounces, every 5 min
                last_bounce = time.time()
                for fn in (check_inbox, check_bounces):
                    try:
                        fn()
                    except Exception as e:
                        log(f"{fn.__name__} failed:", str(e)[:200])
            today = date.today().isoformat()
            if STATE.get("chat") and datetime.now().hour >= report_hour and STATE.get("report_day") != today:
                report()
                STATE["report_day"] = today
                save_state()
            if STATE.get("chat") and datetime.now().hour >= report_hour and STATE.get("opp_day") != today and time.time() > STATE.get("opp_after", 0) and not _opp_busy.locked():
                STATE["opp_day"] = today  # once a day, even if the scan fails half-way
                save_state()
                threading.Thread(target=run_opportunities, daemon=True).start()
        except Exception as e:
            log("error:", e)
            traceback.print_exc()
            time.sleep(15)


if __name__ == "__main__":
    import atexit
    atexit.register(lambda: heartbeat("stopped"))
    try:
        main()
    except KeyboardInterrupt:
        heartbeat("stopped")
