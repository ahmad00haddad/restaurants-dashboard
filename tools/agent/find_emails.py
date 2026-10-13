"""Deep email hunt for leads that have no address: every NGO / organisation / school, and every lead with an open opportunity.

Sources, all read live:
  1) the lead's own website: home page + contact / about pages (Cloudflare-protected and "[at]" addresses decoded),
  2) the opportunity page itself (tenders usually name the submission address),
  3) Exa web search (agent-reach's search backend): it indexes Facebook / Instagram / LinkedIn pages, directories and news,
     which we cannot open directly (login walls),
  4) Jina Reader (agent-reach's page reader) when a site refuses a plain request.
Nothing is invented: a candidate must be written in a page we read. An AI judge picks the address that belongs to THIS
organisation, then code checks it (seen in our text, not a template placeholder, the domain receives mail).
Only empty emails are filled. Report: find_emails.json next to this file (re-runs skip leads already searched).

  python find_emails.py            search and fill
  python find_emails.py --dry      search only, write nothing
"""
import html
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

import httpx

import agent
import emailcheck
import local_ai

HERE = Path(__file__).parent
OUT = HERE / "find_emails.json"
DRY = "--dry" in sys.argv
KINDS = {"ngo", "org", "school"}
EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
JUNK = re.compile(r"(sentry|wixpress|@(?:[a-z0-9-]+\.)*(?:google|facebook|instagram|youtube|linkedin|tiktok|whatsapp|wix|godaddy|cloudflare|exa|jina|"
                  r"reliefweb|globaltenders|developmentaid|ungm|devex|tendersontime|bidsfactory|auftragone)\.[a-z.]+$|\.(png|jpe?g|gif|svg|webp|css|js)$|"
                  r"noreply|no-reply|donotreply|@2x|privacy@|abuse@|dpo@|gdpr@)", re.I)
CONTACT_LINK = re.compile(r"contact|about|reach|connect|get-in-touch|اتصل|تواصل|اتصال|من-نحن|عن-", re.I)
PLATFORM = re.compile(r"facebook|instagram|linktr|google|wixsite|blogspot|wordpress\.com|business\.site|linkedin|twitter|x\.com|tiktok|youtube|whatsapp|wa\.me", re.I)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
_lock = threading.Lock()


def log(*a):
    with _lock:
        print(time.strftime("%H:%M:%S"), *a, flush=True)


def fix_mojibake(t):
    """Old Arabic sites served as cp1256 but read as latin-1 ('ÇáÈÑíÏ') — turn them back into Arabic so the judge can read them."""
    if t.count("Ç") + t.count("á") + t.count("Ã") > 20:
        try:
            return t.encode("latin-1", "ignore").decode("cp1256", "ignore")
        except Exception:
            pass
    return t


def decode_cf(h):
    """Cloudflare email protection: data-cfemail="hex" → the real address."""
    out = []
    for hexs in re.findall(r'data-cfemail="([0-9a-fA-F]+)"', h) + re.findall(r"/cdn-cgi/l/email-protection#([0-9a-fA-F]+)", h):
        try:
            k = int(hexs[:2], 16)
            out.append("".join(chr(int(hexs[i:i + 2], 16) ^ k) for i in range(2, len(hexs), 2)))
        except ValueError:
            pass
    return " ".join(out)


def deobfuscate(t):
    t = re.sub(r"\s*[\[\(\{]\s*(?:at|@)\s*[\]\)\}]\s*", "@", t, flags=re.I)
    return re.sub(r"\s*[\[\(\{]\s*(?:dot|\.)\s*[\]\)\}]\s*", ".", t, flags=re.I)


def fetch(url, jina_fallback=True):
    """(text, raw html) of a page, or ('', '')."""
    raw = ""
    try:
        r = httpx.get(url, headers=UA, timeout=20, follow_redirects=True, verify=False)
        if r.status_code < 400:
            raw = r.text
    except Exception:
        pass
    if len(raw) < 500 and jina_fallback:
        try:
            r = httpx.get("https://r.jina.ai/" + url, timeout=45, headers={"X-Return-Format": "html"})
            if r.status_code < 400:
                raw = r.text
        except Exception:
            pass
    if not raw:
        return "", ""
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    mailto = " ".join(unquote(m) for m in re.findall(r"mailto:([^\"'?\s>\\]+)", raw))
    return fix_mojibake(deobfuscate(re.sub(r"\s+", " ", text)) + " " + mailto + " " + decode_cf(raw)), raw


def site_pages(website):
    """[(url, text)] for the home page and up to 4 contact/about pages on the same site."""
    if not website:
        return []
    home = website if website.startswith("http") else "https://" + website
    text, raw = fetch(home)
    if not text:
        return []
    pages, host = [(home, text)], urlparse(home).netloc.removeprefix("www.")
    links = []
    for href in re.findall(r'href=["\']([^"\'#]+)', raw):
        u = urljoin(home, href)
        if urlparse(u).netloc.removeprefix("www.") == host and CONTACT_LINK.search(unquote(u)) and u not in links:
            links.append(u)
    for guess in ("/contact", "/contact-us", "/contactus", "/about", "/about-us"):
        links.append(urljoin(home, guess))
    seen = {home}
    for u in links:
        if len(pages) >= 5:
            break
        if u in seen:
            continue
        seen.add(u)
        t, _ = fetch(u, jina_fallback=False)
        if t and EMAIL.search(t):
            pages.append((u, t))
    return pages


_exa_lock = threading.Lock()
_exa_next = [0.0]


def exa(query, n=8):
    """[(url, title+highlights)] from Exa, paced to one call every 4 s. While Exa is cooling down after a rate limit we skip it
    (DuckDuckGo carries the search) and the lead is marked so a later run can repeat it with Exa."""
    with _exa_lock:
        if time.time() < _exa_next[0] - 4:
            return None
        time.sleep(max(0, _exa_next[0] - time.time()))
        _exa_next[0] = time.time() + 4
    try:
        local_ai._exa_block["until"] = 0
        txt = local_ai._exa(query, n)
    except local_ai.ExaLimit:
        with _exa_lock:
            _exa_next[0] = time.time() + 600
        log("Exa rate limit — DuckDuckGo only for 10 min")
        return None
    except Exception as e:
        log("Exa error", str(e)[:80])
        return []
    out = []
    for block in txt.split("\n---\n"):
        m = re.search(r"^URL:\s*(\S+)", block, re.M)
        out.append((m.group(1) if m else "exa", fix_mojibake(deobfuscate(block))))
    return out


_ddg_lock = threading.Lock()
_ddg_next = [0.0]


def ddg(query):
    """[(url, title + snippet)] from DuckDuckGo's HTML page, paced to one call every 3 s; backs off when it shows a challenge."""
    for attempt in range(3):
        with _ddg_lock:
            time.sleep(max(0, _ddg_next[0] - time.time()))
            _ddg_next[0] = time.time() + 3
        try:
            r = httpx.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=UA, timeout=25)
        except Exception:
            continue
        out = []
        for m in re.finditer(r'result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?result__snippet[^>]*>(.*?)</a>', r.text, re.S):
            url = m.group(1)
            if "uddg=" in url:
                url = unquote(re.search(r"uddg=([^&]+)", url).group(1))
            text = html.unescape(re.sub(r"<[^>]+>", "", m.group(2) + " — " + m.group(3)))
            out.append((url, deobfuscate(text)))
        if out or "result--no-result" in r.text or "No results" in r.text:
            return out
        with _ddg_lock:
            _ddg_next[0] = time.time() + 60 * (attempt + 1)  # challenge page: let it cool
        log("DuckDuckGo challenge — backing off")
    return []


STOP = set("""the and for of in at to a an school schools academy academic college kindergarten nursery preschool kg center centre
association society foundation fund charity charitable organization organisation organisations international jordan jordanian amman
irbid zarqa aqaba salt madaba karak office country regional hub group company co ltd llc institute institution initiative
مدرسة مدارس روضة رياض حضانة اكاديمية أكاديمية جمعية الجمعية مؤسسة صندوق مركز الأردن الاردن الأردنية الاردنية عمان الخيرية خيرية
النموذجية الدولية الخاصة للبنين للبنات الأطفال الاطفال""".split())


def name_tokens(name):
    toks = [t for t in re.findall(r"[\w']+", name.lower()) if len(t) >= 3 and t not in STOP]
    return toks or [t for t in re.findall(r"[\w']+", name.lower()) if len(t) >= 3]


def matches(name, text):
    toks = name_tokens(name)
    hits = sum(1 for t in toks if t in text.lower())
    return toks and hits >= max(1, (len(toks) + 1) // 2)


LOGIN_WALL = re.compile(r"facebook\.com|instagram\.com|linkedin\.com|twitter\.com|x\.com/|tiktok\.com|youtube\.com", re.I)


def candidates(sources):
    """{email: [(url, context)]} from [(url, text)]."""
    found = {}
    for url, text in sources:
        for m in EMAIL.finditer(text):
            e = m.group(0).strip(".").lower()
            if JUNK.search(e) or emailcheck.PLACEHOLDER.search(e):
                continue
            ctx = text[max(0, m.start() - 260): m.end() + 120]
            lst = found.setdefault(e, [])
            if len(lst) < 3 and url not in [u for u, _ in lst]:
                lst.append((url, ctx))
    return found


def domain_of(url):
    return urlparse(url if "://" in url else "https://" + url).netloc.lower().removeprefix("www.") if url else ""


JUDGE = """You pick the email address that belongs to ONE specific organisation, from addresses found on web pages.
You get the organisation (name, type, city, website, phone) and candidate addresses, each with the page it was found on and
the text around it. Rules:
- Choose an address only if the text around it shows it is THIS organisation's address (same name, same branch / country
  office in Jordan for international organisations, or found on the organisation's own website / own social page).
- Never choose the address of a different organisation, a directory / news site / platform's own address, a donor, a
  ministry, or a person at another organisation. Similar names are not enough: check city, phone or website match.
- For a large international organisation prefer the Jordan office or a named communications / media person in Jordan.
- An address at the organisation's own website domain is strong evidence. A gmail/hotmail address is fine for small
  local organisations and schools when the text ties it to them.
- When the organisation has an open opportunity (a tender / request for proposals for video or photo work), the address
  that the opportunity page gives for submissions or questions is the right one: choose it.
- Otherwise avoid HR / recruitment / jobs / careers / finance / procurement-only addresses when a general, communications or
  director address of the same organisation exists.
- confidence: "high" = clearly theirs (own domain, own page, or name + matching phone/city right next to it);
  "medium" = theirs per one reliable listing; "low" = plausible but unsure. Empty email when none fits.
Return JSON only: {"email":"...","confidence":"high|medium|low","why":"one short sentence"}"""


def judge(L, found):
    lines = []
    for e, ctxs in list(found.items())[:25]:
        lines.append(f"\n### {e}")
        for url, ctx in ctxs[:2]:
            lines.append(f"- page: {url}\n  text: ...{ctx.strip()[:380]}...")
    org = (f"name: {L['name']}\ntype: {L['kind']} ({L.get('category') or ''})\ncity: {L.get('city') or ''}\n"
           f"website: {L.get('website') or ''}\nphone: {L.get('phone') or ''}\nfacebook: {L.get('facebook') or ''}\n"
           f"instagram: {L.get('instagram') or ''}\nopportunity: {L.get('signal') or 'none'} {L.get('signal_url') or ''}")
    for attempt in range(3):
        try:
            v = local_ai.chat(agent.local_model(), JUDGE, f"ORGANISATION\n{org}\n\nCANDIDATES{''.join(lines)}")
            return v if isinstance(v, dict) else {}
        except Exception as e:
            log("judge failed", str(e)[:80])
            time.sleep(20)
    return {}


def hunt(L):
    name, city = L["name"].strip(), (L.get("city") or "Jordan").strip()
    dom = domain_of(L.get("website"))
    if PLATFORM.search(dom):
        dom = ""  # a Facebook / Linktree / Google Sites "website" says nothing about their mail domain
    sources = site_pages(L["website"]) if dom else []
    if L.get("signal_url"):
        t, _ = fetch(L["signal_url"])
        if t:
            sources.append((L["signal_url"], t))
    exa_ok, site_found = True, ""

    def own():
        return [e for e in candidates(sources) if dom and (e.endswith("@" + dom) or e.endswith("." + dom))]

    if not own():
        arabic = bool(re.search(r"[؀-ۿ]", name))
        hits = ddg(f"{name} {city} email") + ddg(f"{name} البريد الإلكتروني" if arabic else f"{name} {city} contact us")
        for q in [f"{name} {city} email contact"] + ([f'"@{dom}"'] if dom else []):
            r = exa(q, 8)
            exa_ok = exa_ok and r is not None
            hits += r or []
        sources += hits
        # follow the results that are about this organisation: their own site, directory pages that copy their Facebook "About"
        fetched, follow = {u for u, _ in sources}, []
        for url, text in hits:
            if url.startswith("http") and url not in fetched and not LOGIN_WALL.search(url) and matches(name, unquote(url) + " " + text[:600]):
                fetched.add(url)
                follow.append(url)
        for url in follow[:5]:
            d = domain_of(url)
            if not dom and not site_found and matches(name, d.replace("-", " ").replace(".", " ")):
                pages = site_pages(f"https://{d}/")  # looks like their own website: read its contact pages too
                if pages:
                    site_found, sources = f"https://{d}/", sources + pages
                    continue
            t, _ = fetch(url)
            if t:
                sources.append((url, t))
        if not [e for e, c in candidates(sources).items() if any(matches(name, x) for _, x in c)]:
            r = exa(f"{name} facebook instagram email", 8)  # their social pages, as Exa indexed them
            exa_ok = exa_ok and r is not None
            sources += r or []
    found = candidates(sources)
    base = {"exa": exa_ok, "website_found": site_found}
    if not found:
        return {**base, "email": "", "confidence": "none", "why": "لم يظهر أي إيميل في المصادر", "candidates": {}}
    mine = own()
    v = judge(L, found)
    e = (v.get("email") or "").strip().lower()
    if e and e not in found:
        v, e = {"email": "", "confidence": "none", "why": f"الحكم اختار عنواناً غير موجود في النصوص ({e})"}, ""
    if not e and mine:
        v, e = {"email": mine[0], "confidence": "high", "why": "على نطاق موقعهم"}, mine[0]
    if e:
        c = emailcheck.check(e)
        if c["ok"] is False:
            v = {**v, "confidence": "rejected", "why": c["reason"]}
    return {**base, **v, "candidates": {k: [u for u, _ in x] for k, x in found.items()}}


def main():
    rows, off = [], 0
    while True:
        r = agent.db.get("leads", select="id,kind,name,category,city,phone,email,website,facebook,instagram,linkedin,signal,signal_url,status,deleted_at",
                         limit=1000, offset=off)
        rows += r
        off += 1000
        if len(r) < 1000:
            break
    todo = [L for L in rows if not L["deleted_at"] and not L["email"] and L["status"] != "skip"
            and (L["kind"] in KINDS or L["signal"])]
    todo.sort(key=lambda L: (not L["signal"], L["kind"] != "ngo"))  # opportunities first, then NGOs, then schools
    report = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    todo = [L for L in todo if L["id"] not in report]
    log(f"{len(todo)} leads to search")

    def one(L):
        try:
            v = hunt(L)
        except Exception as e:
            log("FAILED", L["name"], e)
            return
        v.update(name=L["name"], kind=L["kind"], signal=bool(L["signal"]))
        wrote = False
        if v.get("email") and v.get("confidence") in ("high", "medium") and not DRY:
            cur = agent.db.get("leads", select="email,website", id=f"eq.{L['id']}")
            if cur and not cur[0]["email"]:
                patch = {"email": v["email"]}
                if v.get("website_found") and not cur[0]["website"]:
                    patch["website"] = v["website_found"]
                agent.db.patch("leads", {"id": L["id"]}, patch)
                wrote = True
        v["written"] = wrote
        with _lock:
            report[L["id"]] = v
            OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"{'✔' if wrote else '·'} {L['kind']:7} {L['name'][:45]:45} → {v.get('email') or '-'} ({v.get('confidence')})")

    with ThreadPoolExecutor(3) as pool:
        list(pool.map(one, todo))
    done = [v for v in report.values() if v.get("written")]
    log(f"done: {len(done)} emails written, {len(report) - len(done)} without a sure address")


if __name__ == "__main__":
    main()
