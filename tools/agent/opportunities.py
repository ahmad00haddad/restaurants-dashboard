"""Global opportunity scanner: paid shooting work Ahmad can apply for, found on the open web, fresh and checked.

A) Tenders / consultancies / commissions for video, film, photography (UN, NGOs, companies, anywhere in the world).
B) Prospects outside Jordan with a real, recent reason to need content (opening, launch, event).

Sources: Exa web search (no key) and ReliefWeb's public RSS. Nothing is invented: every item must
  1) be dated (published within 60 days, or an explicit deadline still in the future),
  2) name the organisation verbatim in the text we read,
  3) involve video / film / photo work,
  4) pass a deadline check in code (the model only extracts, code decides).
Results go into `leads` with signal / signal_url / signal_until (the site's "🔔 فرص الآن" tab) via the ingest_leads RPC.
"""
import html
import json
import re
from datetime import date, datetime, timedelta, timezone

import httpx

import local_ai

VIDEO = re.compile(r"video|film|documentar|photograph|audiovisual|multimedia|media production|filming|footage|animation|reel|تصوير|فيديو|فيلم", re.I)
JORDAN_QUERIES = [  # tender aggregators mirror JONEPS / UNGM / donor notices, so English queries find the real Jordanian tenders
    "Jordan tender video production {y}",
    "Jordan tender videography photography services {y}",
    "Jordan request for quotation documentary film production {y}",
    "Jordan RFP media production communication campaign video {y}",
    "joneps Jordan tender video photography services",
    "ungm Jordan videography photography consultancy",
    "developmentaid Jordan tender video production",
    "Jordan LTA video photography services {y}",
    "Jordan call for consultants impact documentary film {y}",
    "Amman tender provision of video production services ministry",
]
TENDER_QUERIES = [
    "request for quotation video production services {y}",
    "call for proposals documentary film production consultancy {y}",
    "terms of reference videographer photographer consultant {y}",
    "tender photography and video services UN agency {y}",
    "individual consultant videographer short film humanitarian {y}",
]
REGIONS = ["Dubai UAE", "Doha Qatar", "Riyadh Saudi Arabia", "Muscat Oman", "Cairo Egypt", "London"]
PROSPECT_QUERIES = ["new hotel opening {y} {r}", "new restaurant opening soon {y} {r}", "upcoming conference exhibition {y} {r} organiser"]

EXTRACT_SYSTEM = """You extract paid-work opportunities for a freelance film director / cinematographer from web search snippets.
For each snippet that really is such an opportunity, return an item. Rules:
- kind: "tender" (RFQ/RFP/call for proposals/ToR/LTA to hire a company or individual for video/film/photo work), "commission" (a named organisation clearly looking to hire a video/film/photo producer), "opening" (a named business that has NOT opened yet and will open on a date written in the snippet), "event" (a named event that has NOT happened yet, with its date written in the snippet).
- Past events do not count: "launched", "opened", "was held" = skip. A closed or expired tender = skip.
- Skip: full-time staff jobs, courses, stock footage, software, news about other topics, or anything not clearly about video/film/photo work or a business/event that will need it.
- org = the organisation issuing the tender or opening/hosting (exact name as written). org_quote = a short EXACT quote from the snippet that contains the org name.
- what = one plain sentence in English describing the work or the opening, using only facts in the snippet.
- deadline = the application deadline or the opening/event date as YYYY-MM-DD ONLY if it is written in the snippet, otherwise null. Never guess a date.
- country = country if stated, else null.
- eligibility = a short quote if the snippet restricts who can apply (registered company, local firm only, nationals only), else "".
- apply = an email address or URL to apply/contact if written in the snippet, else "".
Return JSON only: {"items":[{"index":<snippet number>,"kind":"...","org":"...","org_quote":"...","what":"...","deadline":"YYYY-MM-DD or null","country":"...","eligibility":"...","apply":"..."}]}. Empty list when none."""

AGGREGATORS = re.compile(r"bidding ?source|biddetail|globaltenders|global tenders|bidsfactory|bids factory|developmentaid|development aid|tenderimpulse|tender impulse|"
                         r"ungm|reliefweb|linkedin|tendersontime|tenders on time|biddingsource|devex|dgmarket|joneps", re.I)
LABEL = {"tender": "مناقصة/طلب عروض", "commission": "جهة تبحث عن مصوّر", "opening": "افتتاح/إطلاق قريب", "event": "فعالية قادمة"}
KIND_OF = {"tender": "ngo", "commission": "org", "opening": "brand", "event": "event"}


def _snippets(query, n=8):
    """[(url, published 'YYYY-MM-DD' or '', text)] from Exa."""
    try:
        text = local_ai._exa(query, n)
    except Exception:
        return []
    out = []
    for ch in re.split(r"(?m)^Title: ", text)[1:]:
        url = (re.search(r"^URL: (\S+)", ch, re.M) or [None, ""])[1]
        pub = (re.search(r"^Published: (\S+)", ch, re.M) or [None, ""])[1]
        out.append((url, pub[:10] if re.match(r"20\d\d-\d\d-\d\d", pub) else "", "Title: " + ch[:1800]))
    return out


def _reliefweb():
    """Consultancies/tenders from ReliefWeb's public RSS (structured closing dates). Global."""
    out = []
    for term in ["videographer", "video production", "documentary", "photographer consultant", "multimedia consultant", "RFQ video"]:
        try:
            xml = httpx.get("https://reliefweb.int/jobs/rss.xml", params={"search": term}, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
        except Exception:
            continue
        for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
            link = re.search(r"<link>(.*?)</link>", item)
            desc = html.unescape((re.search(r"<description>(.*?)</description>", item, re.S) or [None, ""])[1])
            title = html.unescape((re.search(r"<title>(.*?)</title>", item) or [None, ""])[1])
            org = re.search(r"Organization: ([^<\n]+)", desc)
            close = re.search(r"Closing date: ([^<\n]+)", desc)
            ctry = re.search(r"Country: ([^<\n]+)", desc)
            if not (link and org and close):
                continue
            if not (VIDEO.search(title) and re.search(r"consult|tender|RFQ|RFP|quotation|EOI|expression|contract|freelanc|service", title + desc[:600], re.I)):
                continue  # staff posts and unrelated posts are dropped
            try:
                until = datetime.strptime(close.group(1).strip(), "%d %b %Y").date()
            except ValueError:
                continue
            out.append({"url": link.group(1), "org": org.group(1).strip(), "title": title, "until": until, "country": (ctry.group(1).strip() if ctry else None),
                        "text": re.sub(r"<[^>]+>", " ", desc)[:1500]})
    return out


def _extract(model, batch):
    body = "\n\n".join(f"[{i}] ({pub or 'undated'}) {t}" for i, (_, pub, t) in enumerate(batch))
    try:
        return local_ai.chat(model, EXTRACT_SYSTEM, "SNIPPETS:\n" + body).get("items") or []
    except Exception:
        return []


def _date_in_text(d, text):
    """True when the text really writes this date (ISO, or day + month name + year in any order)."""
    t = text.lower()
    if d.isoformat() in t:
        return True
    month = d.strftime("%B").lower()
    return (month in t or month[:3] in t) and re.search(r"0?%d" % d.day, t) is not None and str(d.year) in t


def _valid(it, batch, today, kinds):
    """Code-side proof. Returns the clean opportunity dict or None."""
    try:
        i = int(it.get("index"))
    except (TypeError, ValueError):
        return None
    if not 0 <= i < len(batch) or it.get("kind") not in kinds:
        return None
    url, pub, text = batch[i]
    org, quote = str(it.get("org") or "").strip(), str(it.get("org_quote") or "").strip()
    if len(org) < 3 or org.lower() not in text.lower() or (quote and quote not in text) or AGGREGATORS.search(org):
        return None  # the organisation is the issuer, never the website that republishes the notice
    if not VIDEO.search(text):
        return None
    deadline = None
    if it.get("deadline"):
        try:
            deadline = date.fromisoformat(str(it["deadline"]))
        except ValueError:
            deadline = None
        if deadline and not _date_in_text(deadline, text):
            deadline = None  # a date the text does not contain is a guess: ignore it
    if re.search(r"closed tender|tender closed|expired|deadline (has )?passed", text, re.I) and not (deadline and deadline >= today):
        return None
    if it["kind"] != "tender":
        if not deadline or deadline < today:
            return None  # an opening / event / commission must carry a written FUTURE date
    elif deadline and deadline < today:
        return None  # already closed
    elif not deadline and not (pub and date.fromisoformat(pub) >= today - timedelta(days=90)):
        return None  # tender with no written deadline: must at least be recent; the page itself is read for the deadline (see scan)
    what = str(it.get("what") or "").strip()[:240]
    if len(what) < 15:
        return None
    return {"needs_deadline": it["kind"] == "tender" and not deadline, "kind": it["kind"], "org": org, "what": what, "deadline": deadline, "country": it.get("country"),
            "eligibility": str(it.get("eligibility") or "")[:160], "apply": str(it.get("apply") or "")[:200], "url": url, "text": text}


JUNK_MAIL = re.compile(r"example|@mail\.com|@email\.com|@domain|sentry|wixpress|@test\.|your-?name|name@|user@|\.(png|jpg|gif|svg)$|noreply|no-reply", re.I)


def _contact(org, country):
    """Official website + public email/socials of the organisation (read by the same reader the lead collector uses)."""
    try:
        from harvest import read_site
        words = [w for w in re.findall(r"[a-z0-9]+", org.lower()) if len(w) > 2][:3]
        for url, _pub, _t in _snippets(f"{org} {country or ''} official website contact", 5):
            host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
            if any(b in host for b in ("linkedin", "facebook", "instagram", "twitter", "x.com", "wikipedia", "reliefweb", "ungm", "youtube")):
                continue
            if words and any(w in host for w in words):
                info = read_site({"name": org, "website": "https://" + host})
                got = {k: info.get(k) for k in ("email", "phone", "instagram", "facebook", "linkedin") if info.get(k)}
                if got.get("email") and JUNK_MAIL.search(got["email"]):
                    got.pop("email")
                return {"website": "https://" + host, **got}
    except Exception:
        pass
    return {}


def _find_deadline(model, url, today):
    """Read the notice page and return its submission deadline only if that date is literally written there and still ahead."""
    try:
        page = httpx.get("https://r.jina.ai/" + url, headers={"Accept": "text/plain"}, timeout=45).text[:9000]
        d = local_ai.chat(model, 'Return JSON only: {"deadline":"YYYY-MM-DD or null"}. The submission / closing deadline of this tender or call, only if it is written in the text. Never guess.', page).get("deadline")
        d = date.fromisoformat(str(d)) if d else None
    except Exception:
        return None
    return d if d and d >= today and _date_in_text(d, page) else None


def scan(db, model, seen, log=print, max_new=25):
    """Find new opportunities, save them as leads with a live signal. Returns the list saved (for the Telegram note)."""
    today = date.today()
    found, urls = [], set(seen)

    from concurrent.futures import ThreadPoolExecutor
    jobs = [(q.format(y=today.year), 8, True) for q in JORDAN_QUERIES] + [(q.format(y=today.year), 8, False) for q in TENDER_QUERIES] +            [(q.format(y=today.year, r=r), 5, False) for r in REGIONS for q in PROSPECT_QUERIES[:2]]
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(lambda j: _snippets(j[0], j[1]), jobs))
    batches = []  # (is_jordan, snippets)
    for (q, n, jo), res in zip(jobs, results):
        res = [x for x in res if x[0] not in urls]
        urls.update(x[0] for x in res)
        batches.append((jo, res))
    for jo, s_ in batches:
        for k in range(0, len(s_), 8):
            batch = s_[k:k + 8]
            for it in _extract(model, batch):
                ok = _valid(it, batch, today, {"tender", "commission", "opening", "event"})
                if ok and ok.pop("needs_deadline"):
                    ok["deadline"] = _find_deadline(model, ok["url"], today)
                    if not ok["deadline"]:
                        continue  # cannot prove it is still open
                if ok:
                    ok["jo"] = jo or bool(re.search(r"jordan|amman|الأردن", (ok.get("country") or "") + ok["text"][:400], re.I))
                    found.append(ok)

    # --- ReliefWeb (structured)
    for rw in _reliefweb():
        if rw["until"] >= today and rw["url"] not in seen:
            found.append({"jo": "jordan" in (rw["country"] or "").lower(), "kind": "tender", "org": rw["org"], "what": rw["title"], "deadline": rw["until"], "country": rw["country"],
                          "eligibility": "", "apply": "", "url": rw["url"], "text": rw["text"]})

    # one row per organisation, earliest deadline first
    by_org, seen_what = {}, set()
    for o in sorted(found, key=lambda o: (not o.get("jo"), o["deadline"] or date.max)):
        w = re.sub(r"\W+", "", o["what"].lower())[:50]
        if w in seen_what:
            continue  # same notice republished on several sites
        seen_what.add(w)
        by_org.setdefault(o["org"].lower(), o)
    rows, saved = [], []
    for o in list(by_org.values())[:max_new]:
        c = _contact(o["org"], o["country"])
        sig = ("🇯🇴 " if o.get("jo") else "") + f"{LABEL[o['kind']]}: {o['what']}" + (f" — ⚠ {o['eligibility']}" if o["eligibility"] else "") + ("" if o["deadline"] else " — الموعد النهائي غير مذكور، راجع الرابط") + (f" — للتقديم: {o['apply']}" if o["apply"] else "")
        rows.append({"name": o["org"], "kind": KIND_OF[o["kind"]], "city": o["country"], "source": "opportunities",
                     "signal": sig[:500], "signal_url": o["url"],
                     "signal_until": o["deadline"].isoformat() if o["deadline"] else (today + timedelta(days=14)).isoformat(),
                     "about": o["text"][:3000], **c})
        saved.append(o)
    if rows:
        db.req("POST", "rpc/ingest_leads", body={"rows": rows})
    seen_new = list(urls)[-800:]
    return saved, seen_new
