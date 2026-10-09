"""Cheap email checks before we send: syntax, disposable domains, role addresses (info@…), and a real MX lookup.

No SMTP probing (unreliable and bad for our own IP). A missing MX record = the domain cannot receive mail = sure bounce.
"""
import re
import httpx

ROLE = {"info", "contact", "contactus", "hello", "admin", "office", "support", "sales", "enquiries", "inquiries", "mail", "reception",
        "hr", "jobs", "careers", "press", "media", "booking", "bookings", "reservations", "service", "customerservice", "webmaster", "noreply", "no-reply"}
DISPOSABLE = {"mailinator.com", "10minutemail.com", "guerrillamail.com", "tempmail.com", "yopmail.com", "trashmail.com"}
SYNTAX = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})")
_mx = {}


def has_mx(domain):
    """True/False when DNS answers, None when we could not ask (never block on our own network trouble)."""
    if domain in _mx:
        return _mx[domain]
    try:
        r = httpx.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": "MX"},
                      headers={"accept": "application/dns-json"}, timeout=10)
        d = r.json()
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
    if domain in DISPOSABLE:
        return {"ok": False, "role": False, "reason": "إيميل مؤقت"}
    ok = has_mx(domain)
    return {"ok": ok, "role": local.replace(".", "") in ROLE, "reason": "" if ok is not False else "النطاق لا يستقبل بريداً (لا MX)"}
