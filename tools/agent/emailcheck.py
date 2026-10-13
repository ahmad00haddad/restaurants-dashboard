"""Cheap email checks before we send: syntax, disposable domains, role addresses (info@…), and a real MX lookup.

No SMTP probing (unreliable and bad for our own IP). A missing MX record = the domain cannot receive mail = sure bounce.
"""
import re
import httpx

ROLE = {"info", "contact", "contactus", "hello", "admin", "office", "support", "sales", "enquiries", "inquiries", "mail", "reception",
        "hr", "jobs", "careers", "press", "media", "booking", "bookings", "reservations", "service", "customerservice", "webmaster", "noreply", "no-reply"}
DISPOSABLE = {"mailinator.com", "10minutemail.com", "guerrillamail.com", "tempmail.com", "yopmail.com", "trashmail.com"}
SYNTAX = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
# Big international organisations: their generic mailbox (info@, contact@…) reaches a global donor / supporter desk, not the country office
# (learned from the Mercy Corps and IRC auto-replies). A named person's address at the same domain is still fine.
BIG_ORG_DOMAINS = {"rescue.org", "mercycorps.org", "unicef.org", "undp.org", "unhcr.org", "wfp.org", "savethechildren.org", "savethechildren.net",
                   "wvi.org", "worldvision.org", "oxfam.org", "care.org", "nrc.no", "icrc.org", "ifrc.org", "who.int", "unwomen.org", "unfpa.org",
                   "ilo.org", "iom.int", "redcross.org", "caritas.org", "drc.ngo", "plan-international.org", "actionagainsthunger.org", "msf.org",
                   "handicap-international.org", "hi.org", "internationalmedicalcorps.org", "irc.org", "intersos.org", "cesvi.org", "cordaid.org"}
# Placeholder addresses that website templates ship with (learned from a bounce: example@youremail.com on a harvested site).
PLACEHOLDER = re.compile(r"(youremail|yourname|your-?email|yourdomain|yoursite|mysite|mydomain|@email\.com$|@domain\.[a-z]+$|@example\.|^(example|name|user|test|email|someone|john\.?doe|jane\.?doe)@)", re.I)
# Mailboxes that are never the person who decides about a film: donation / supporter / jobs / billing desks, and addresses of news sites.
WRONG_DESK = re.compile(r"^(donat\w*|donor\w*|giving|monthlygiving|supporter\w*|fundrais\w*|career\w*|jobs?|recruit\w*|hr|billing|invoice\w*|accounts?|complaints?|"
                        r"privacy|legal|abuse|postmaster|webmaster|unsubscribe|donatori\w*|spende\w*|don)$", re.I)
NEWS_ADDR = re.compile(r"(news|akhbar|ammon|jordanzad|khaberni|alraqeb|7areer)", re.I)
# Foreign government mail servers (embassies, ministries abroad) refuse unknown senders: a South African embassy address bounced with
# "550 5.4.1 Recipient address rejected: Access denied". Jordanian .gov.jo stays allowed (real clients and tenders).
FOREIGN_GOV = re.compile(r"\.(gov|gouv|go|mil|govt)(\.[a-z]{2})?$|\.gob\.[a-z]{2}$|(^|\.)itamaraty\.|\.admin\.ch$", re.I)
_mx = {}


def has_mx(domain):
    """True/False when DNS answers, None when we could not ask (never block on our own network trouble)."""
    if domain in _mx:
        return _mx[domain]
    try:
        r = httpx.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": "MX"},
                      headers={"accept": "application/dns-json"}, timeout=10)
        d = r.json()
        if d.get("Status") not in (0, 3):  # 3 = domain does not exist; anything else (SERVFAIL…) = we don't know
            return None
        ok = d.get("Status") == 0 and any(a.get("type") == 15 for a in d.get("Answer", []))
        if not ok and d.get("Status") == 0:  # no MX: RFC says fall back to an A record
            a = httpx.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": "A"},
                          headers={"accept": "application/dns-json"}, timeout=10).json()
            ok = a.get("Status") == 0 and bool(a.get("Answer"))
        _mx[domain] = ok
    except Exception:
        return None
    return _mx[domain]


def check(email):
    """{'ok': bool|None, 'role': bool, 'reason': str}. ok=None means unknown (treated as allowed, not as verified)."""
    m = SYNTAX.fullmatch((email or "").strip())
    if not m:
        return {"ok": False, "role": False, "reason": "صيغة الإيميل غير صالحة"}
    local, domain = email.strip().lower().rsplit("@", 1)
    if FOREIGN_GOV.search(domain) and not domain.endswith(".jo"):
        return {"ok": False, "role": False, "reason": "بريد حكومي أجنبي (سفارة أو وزارة): خوادمهم ترفض المرسل الغريب، وغالباً ليسوا جهة التعاقد"}
    if WRONG_DESK.match(local.replace(".", "").replace("_", "").replace("-", "")):
        return {"ok": False, "role": True, "reason": "صندوق تبرعات أو وظائف أو فواتير وليس جهة القرار: ابحث عن عنوان التواصل أو الإعلام"}
    if NEWS_ADDR.search(domain) or NEWS_ADDR.search(local):
        return {"ok": False, "role": False, "reason": "عنوان موقع إخباري وليس العميل: غالباً التقطه الجامع من صفحة خارجية"}
    if PLACEHOLDER.search(email.strip()):
        return {"ok": False, "role": False, "reason": "عنوان نموذجي من قالب الموقع وليس عنوان العميل"}
    if domain in DISPOSABLE:
        return {"ok": False, "role": False, "reason": "إيميل مؤقت"}
    if local.replace(".", "") in ROLE and any(domain == d or domain.endswith("." + d) for d in BIG_ORG_DOMAINS):
        return {"ok": False, "role": True, "reason": "عنوان عام لمنظمة دولية كبيرة: يصل غالباً لخدمة الداعمين وليس لفريق الأردن، ابحث عن شخص بالاسم"}
    ok = has_mx(domain)
    return {"ok": ok, "role": local.replace(".", "") in ROLE, "reason": "" if ok is not False else "النطاق لا يستقبل بريداً (لا MX)"}
