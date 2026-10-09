"""FAII Agent — runs on your PC.

- Every draft queued from the site ("📤 للموافقة") arrives on your Telegram with ✅ / ✏️ / ❌.
- ✅ on an email → sent from your Gmail and logged in the site. ✅ on WhatsApp → you get a one-tap link.
- ✏️ → reply with the new text, it comes back for approval.
- Morning report every day + /report /queue /pause /resume commands.
Config: agent.env (see agent.env.example).
"""
import json, re, smtplib, sys, time, traceback
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
STATE = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state():
    STATE_FILE.write_text(json.dumps(STATE))


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
def send_email(to, subject, body):
    cap = int(E.get("DAILY_CAP", "20"))
    today = date.today().isoformat()
    if STATE.get("sent_day") != today:
        STATE.update(sent_day=today, sent_count=0)
    if STATE["sent_count"] >= cap:
        raise RuntimeError(f"وصلت للحد اليومي ({cap}) — سيُرسل غداً")
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject or E.get("SENDER_NAME", "")
    msg["From"] = formataddr((E.get("SENDER_NAME", ""), E["GMAIL_USER"]))
    msg["To"] = to
    msg["Message-ID"] = make_msgid(domain=E["GMAIL_USER"].split("@")[-1])
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(E["GMAIL_USER"], E["GMAIL_APP_PASSWORD"].replace(" ", ""))
        s.send_message(msg)
    STATE["sent_count"] += 1
    save_state()


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
        links = E.get("ALLOWED_LINKS") or "ahmadhaddad.lovable.app,faiihouse.lovable.app,behance.net/ahmad00haddad,behance.com/ahmad00haddad"
        _allowed["urls"] = {u.strip().lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/") for u in links.split(",") if u.strip()}
    return _allowed["urls"]


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
    if m["channel"] == "email" and len(body) > 1600 and not (L.get("status") in ("replied", "meeting")):
        why.append("أطول من اللازم لرسالة أولى")
    if L.get("status") in ("lost", "skip"):
        why.append("العميل مغلق (رفض أو تجاهل)")
    return why


# ---------------- Approval flow ----------------
KIND = {"ngo": "منظمة", "org": "مؤسسة", "restaurant": "مطعم", "brand": "براند", "hotel": "فندق", "event": "فعاليات", "other": "أخرى"}
CH = {"email": "✉️ إيميل", "whatsapp": "💬 واتساب", "instagram": "📷 إنستغرام"}


def card(m):
    L = m["leads"]
    to = L.get("email") if m["channel"] == "email" else L.get("phone") if m["channel"] == "whatsapp" else L.get("instagram")
    head = f"{CH.get(m['channel'], m['channel'])} → {L['name']} ({KIND.get(L['kind'], L['kind'])})\nإلى: {to or '— غير متوفر'}"
    if L.get("score") is not None:
        head += f" · تقييم {L['score']}"
    if L.get("signal"):
        head += f"\n🔔 {L['signal']}"
    subj = f"\nالموضوع: {m['subject']}" if m.get("subject") else ""
    return f"{head}{subj}\n────────\n{m['body']}"


def buttons(mid):
    return {"inline_keyboard": [[{"text": "✅ أرسل", "callback_data": f"ok:{mid}"},
                                 {"text": "✏️ عدّل", "callback_data": f"ed:{mid}"},
                                 {"text": "❌ ارفض", "callback_data": f"no:{mid}"}]]}


def push_pending():
    if STATE.get("paused"):
        return
    rows = db.get("lead_messages", select="*,leads(*)", review="eq.pending", tg_message_id="is.null", order="created_at", limit="10")
    for m in rows:
        r = say(card(m), reply_markup=buttons(m["id"]))
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
    m = db.get("lead_messages", select="*,leads(*)", id=f"eq.{mid}")[0]
    L = m["leads"]
    if m["review"] == "sent":
        return "أُرسلت مسبقاً"
    problems = gate(m, L)
    if problems:
        db.patch("lead_messages", {"id": mid}, {"review": "failed", "review_note": " · ".join(problems)[:300]})
        return "🛑 لم تُرسل — الفحص أوقفها:\n• " + "\n• ".join(problems) + "\nعدّلها (✏️ من الموقع) ثم أعد إرسالها للموافقة."
    if m["channel"] == "email":
        if not L.get("email"):
            return "لا يوجد إيميل لهذا العميل"
        send_email(L["email"], m.get("subject"), m["body"])
        done = f"✅ أُرسلت إلى {L['email']}"
    elif m["channel"] == "whatsapp":
        if not L.get("phone"):
            return "لا يوجد رقم لهذا العميل"
        say(f"اضغط لإرسالها من واتسابك إلى {L['name']}:", reply_markup={"inline_keyboard": [[{"text": "💬 افتح واتساب", "url": wa_link(L["phone"], m["body"])}]]})
        done = "✅ جاهزة في واتساب"
    else:
        say(m["body"])
        done = f"✅ انسخ الرسالة أعلاه وأرسلها في الدايركت: {L.get('instagram') or ''}"
    now = datetime.utcnow().isoformat()
    db.patch("lead_messages", {"id": mid}, {"review": "sent", "draft": False, "sent_at": now, "created_at": now})
    after_send(L)
    return done


def send_site_approved():
    """Drafts approved from the site's Approvals tab are sent here too."""
    for m in db.get("lead_messages", select="id,tg_message_id", review="eq.approved", limit="10"):
        try:
            say(approve(m["id"], m["tg_message_id"]))
        except Exception as e:
            db.patch("lead_messages", {"id": m["id"]}, {"review": "failed", "review_note": str(e)[:300]})
            say(f"⚠️ {e}")


def on_callback(q):
    if str(q["message"]["chat"]["id"]) != str(STATE.get("chat")):
        return
    action, mid = q["data"].split(":", 1)
    tg_mid = q["message"]["message_id"]
    try:
        if action == "ok":
            res = approve(mid, tg_mid)
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
    tg("answerCallbackQuery", callback_query_id=q["id"])
    tg("editMessageReplyMarkup", chat_id=STATE["chat"], message_id=tg_mid, reply_markup={"inline_keyboard": []})
    say(res)


def on_text(msg):
    chat, text = msg["chat"]["id"], (msg.get("text") or "").strip()
    if text == "/start" and not STATE.get("chat"):
        STATE["chat"] = chat
        save_state()
        say("أهلاً أحمد 👋 ربطت هذا الحساب بالوكيل. ستصلك هنا الرسائل للموافقة والتقرير الصباحي.\nالأوامر: /report /queue /analyze /pause /resume")
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


def local_model():
    import local_ai
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
        return
    rank = {"ngo": 0, "org": 1, "hotel": 2, "brand": 3, "event": 4, "restaurant": 5}
    rows.sort(key=lambda L: (not L.get("signal"), rank.get(L["kind"], 6), not L.get("website")))
    L = rows[0]
    try:
        p = local_ai.analyze(db, L, _local["team"], _local["model"])
        _local["done"] += 1
        log(f"🧠 {L['name']}: {p['score']} — {p['profile'].get('angle', '')[:80]}")
    except Exception as e:
        log(f"analysis failed for {L['name']}: {e}")
        db.patch("leads", {"id": L["id"]}, {"profile": {"summary": "تعذّر التحليل المحلي", "why": str(e)[:200], "analysed_by": "failed"}, "score": 0})


# ---------------- Main loop ----------------
def main():
    log("FAII Agent started. Open Telegram and send /start to your bot." if not STATE.get("chat") else "FAII Agent started.")
    offset, last_push, report_hour = STATE.get("offset", 0), 0, int(E.get("REPORT_HOUR", "8"))
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
            analyze_one()
            if STATE.get("chat") and time.time() - last_push > 60:
                push_pending()
                send_site_approved()
                last_push = time.time()
            today = date.today().isoformat()
            if STATE.get("chat") and datetime.now().hour >= report_hour and STATE.get("report_day") != today:
                report()
                STATE["report_day"] = today
                save_state()
        except Exception as e:
            log("error:", e)
            traceback.print_exc()
            time.sleep(15)


if __name__ == "__main__":
    main()
