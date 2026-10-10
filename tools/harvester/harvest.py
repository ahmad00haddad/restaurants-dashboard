"""FAII lead collector — runs on your PC with a real browser.

Searches Google Maps, opens every place, then reads each website for email + social accounts + text.
Output: leads-<kind>-<date>.json  →  upload it in the site with "استيراد من الجامع" (duplicates are merged there too).
"""
import html, json, os, re, sys, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import httpx

CITIES = ["Irbid", "Ramtha", "Amman", "Zarqa", "Aqaba", "Salt", "Madaba", "Jerash", "Mafraq", "Karak", "Ajloun"]
PRESETS = {
    "ngo": ["NGO", "non-profit organization", "charity", "foundation", "UN agency", "humanitarian organization",
            "community development organization", "women empowerment organization", "youth organization",
            "refugee support organization", "environmental organization", "cultural center", "embassy",
            "منظمة غير حكومية", "جمعية خيرية"],
    "org": ["university", "private school", "hospital", "museum", "marketing agency", "real estate developer", "bank",
            "tech company", "conference center", "clinic"],
    "roastery": ["coffee roastery", "specialty coffee roasters", "coffee roasters", "محمصة قهوة", "محامص قهوة مختصة", "محمص بن"],
    "pharmacy": ["pharmacy", "صيدلية", "pharmacy chain", "صيدليات", "drugstore", "medical center pharmacy"],
    "school": ["private school", "مدرسة خاصة", "international school", "academy school", "kindergarten", "nursery", "مدارس"],
    "restaurant": ["restaurant", "cafe", "fine dining restaurant", "bakery", "coffee roastery", "dessert shop"],
    "hotel": ["hotel", "resort", "eco lodge", "tour operator", "guest house"],
    "brand": ["clothing store", "cosmetics brand", "furniture store", "jewelry store", "car dealership", "gym"],
    "event": ["event planner", "wedding hall", "event venue", "exhibition center"],
}


# ---------------- Google Maps ----------------
# ---------------- Blocklist: existing clients and chains we never contact ----------------
BLOCKLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocklist.txt")


def _blocklist():
    try:
        words = [l.strip() for l in open(BLOCKLIST_FILE, encoding="utf-8") if l.strip() and not l.startswith("#")]
    except OSError:
        words = []
    return re.compile("|".join(re.escape(w) for w in words), re.I) if words else None


def is_blocked(d):
    """True for a lead whose name, website or social account matches a line of blocklist.txt (old clients, chains with many branches)."""
    rx = _blocklist()
    if not rx:
        return False
    blob = " ".join(str(d.get(k) or "") for k in ("name", "website", "instagram", "facebook", "email"))
    return bool(rx.search(blob))


def roastery_ok(d):
    """Coffee roasteries only: not cafes, restaurants or nut shops. Needs a coffee/roaster word, and a cafe-type category must say roaster too."""
    c = f"{d.get('category') or ''}".lower()
    n = f"{d.get('name') or ''}".lower()
    coffee = re.compile(r"roast|coffee|قهوة")  # not محمص alone: that is also a nut roaster
    cafe = re.compile(r"cafe|café|coffee shop|restaurant|dessert|bakery|مقهى|كافيه|مطعم|حلويات|مخبز")
    says_roaster = re.search(r"roast|محمصة قهوة|محمص قهوة|محمص البن|محمص بن", c + " " + n)
    if cafe.search(c) and not says_roaster:
        return False
    return bool(says_roaster or (coffee.search(c + " " + n) and re.search(r"store|supplier|wholesale|متجر|تجارة", c)))


def human_check(pg):
    return "/sorry/" in pg.url or pg.locator("iframe[src*='recaptcha']").count() > 0


def wait_if_blocked(pg, show):
    """Google's 'I'm not a robot' page: stop touching the page so the person can solve it, then go on. False = give up."""
    if not human_check(pg):
        return True
    if not show:
        print("  ⛔ Google asked for a human check. Run again and answer y to 'Show browser'.")
        return False
    print("  ⏸ Google human check: solve it in the browser window. I wait here (up to 10 minutes) and don't touch the page.")
    for _ in range(300):
        pg.wait_for_timeout(2000)
        if not human_check(pg):
            pg.wait_for_timeout(2000)
            print("  ▶ continuing")
            return True
    return False


def ckpt_path(kind):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), f".progress-{kind}.json")


def ckpt_load(kind):
    try:
        return json.load(open(ckpt_path(kind), encoding="utf-8"))
    except (OSError, ValueError):
        return {"rows": [], "seen": [], "queries_done": []}


def ckpt_save(kind, ck):
    tmp = ckpt_path(kind) + ".tmp"
    json.dump(ck, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, ckpt_path(kind))  # never a half-written progress file, even if the window is closed mid-save


def maps(queries, per_query, show, ck, kind_key):
    """Saves progress after every place; places and searches already in `ck` are skipped, so a closed window loses nothing."""
    import random
    from playwright.sync_api import sync_playwright
    out = ck["rows"]
    seen = set(ck["seen"])
    with sync_playwright() as p:
        # persistent profile: once a check is solved, Google remembers it for the next runs
        b = p.chromium.launch_persistent_context(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".gprofile"),
                                                 headless=not show, locale="en-US")
        pg = b.pages[0] if b.pages else b.new_page()
        for kind, text, city in queries:
            if text in ck["queries_done"]:
                print("\n✔ already done:", text)
                continue
            print(f"\n🔎 {text}")
            try:
                pg.goto("https://www.google.com/maps/search/" + urllib.parse.quote(text) + "?hl=en", timeout=60000)
                pg.wait_for_timeout(3500)
                if not wait_if_blocked(pg, show):
                    break
                for t in ("Reject all", "Accept all"):
                    if pg.locator(f"button:has-text('{t}')").count():
                        pg.locator(f"button:has-text('{t}')").first.click(); pg.wait_for_timeout(2000); break
                links = scroll(pg, per_query) or ([pg.url] if pg.locator("h1.DUwDvf").count() else [])
            except Exception as e:
                print("  ✗", str(e)[:100]); continue
            print(f"   {len(links)} places")
            stop = False
            for url in links:
                if url.split("?")[0] in seen:
                    continue
                try:
                    pg.goto(url, timeout=45000)
                    pg.wait_for_timeout(random.randint(1200, 3200))  # a human pace: fewer checks from Google
                    if not wait_if_blocked(pg, show):
                        stop = True
                        break
                    pg.wait_for_selector("h1.DUwDvf", timeout=12000)
                    d = place(pg)
                except Exception:
                    continue
                seen.add(url.split("?")[0])
                ck["seen"] = sorted(seen)
                if kind == "roastery" and not roastery_ok(d):
                    print("  ✗ not a coffee roastery:", d["name"], "|", d.get("category"))
                    ckpt_save(kind_key, ck)
                    continue
                if is_blocked(d):
                    print("  ✗ skipped (blocklist):", d["name"])
                    ckpt_save(kind_key, ck)
                    continue
                d.update(kind=kind, city=d.get("city") or city, maps_url=url.split("?")[0], source="maps: " + text)
                out.append(d)
                ckpt_save(kind_key, ck)
                print("  +", d["name"], d.get("phone") or "", d.get("website") or "")
            if stop:
                print("  (stopping the search here; everything found so far is still saved)")
                break
            ck["queries_done"].append(text)
            ckpt_save(kind_key, ck)
        b.close()
    return out


def scroll(pg, limit):
    feed = pg.locator("div[role=feed]")
    if not feed.count():
        return []
    seen, stale = [], 0
    while len(seen) < limit and stale < 4:
        before = len(seen)
        for h in pg.eval_on_selector_all("a.hfpxzc", "els => els.map(e => e.href)"):
            if h not in seen:
                seen.append(h)
        if pg.locator("text=You've reached the end of the list").count():
            break
        stale = stale + 1 if len(seen) == before else 0
        feed.first.evaluate("el => el.scrollBy(0, 4000)")
        pg.wait_for_timeout(1800)
    return seen[:limit]


def attr(pg, sel, a="aria-label"):
    l = pg.locator(sel)
    return (l.first.get_attribute(a) or "") if l.count() else ""


def place(pg):
    addr = re.sub(r"^Address:\s*", "", attr(pg, 'button[data-item-id="address"]')).strip()
    site = attr(pg, 'a[data-item-id="authority"]', "href")
    m = re.search(r"([\d.]+)", attr(pg, 'div.F7nice span[role="img"]'))
    d = {
        "name": pg.locator("h1.DUwDvf").first.inner_text().strip(),
        "phone": re.sub(r"^Phone:\s*", "", attr(pg, 'button[data-item-id^="phone"]')).strip() or None,
        "address": addr or None,
        "website": site or None,
        "category": pg.locator("button.DkEaL").first.inner_text() if pg.locator("button.DkEaL").count() else None,
        "rating": float(m.group(1)) if m else None,
    }
    city = addr.split(",")[-1].strip() if "," in addr else ""
    if city and not re.search(r"\d", city):
        d["city"] = city
    for net in ("facebook", "instagram", "tiktok"):
        if site and net in site:
            d[net], d["website"] = site, None
    return d


# ---------------- Website reading ----------------
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
BAD = re.compile(r"(sentry|wixpress|example\.|domain\.|\.(png|jpe?g|gif|svg|webp|css|js)$|noreply|no-reply|@2x)", re.I)
SOCIAL = {
    "instagram": r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+",
    "facebook": r"https?://(?:www\.|m\.)?facebook\.com/[A-Za-z0-9_.\-]+",
    "linkedin": r"https?://(?:[a-z]+\.)?linkedin\.com/(?:company|in)/[A-Za-z0-9_\-%]+",
    "youtube": r"https?://(?:www\.)?youtube\.com/(?:@|c/|channel/|user/)[A-Za-z0-9_\-]+",
    "tiktok": r"https?://(?:www\.)?tiktok\.com/@[A-Za-z0-9_.]+",
}
HINT = re.compile(r"contact|about|who-we-are|our-work|projects|programs|programmes|stories|menu|team|marketing|media|careers|تواصل|من-نحن|اتصل|مشاريع|فريق|التسويق", re.I)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}


def get(c, url):
    try:
        r = c.get(url, timeout=12, follow_redirects=True)
        return r.text[:500_000] if r.status_code == 200 and "html" in r.headers.get("content-type", "") else ""
    except Exception:
        return ""


def text(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer)[^>]*>.*?</\1>", " ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def read_site(d):
    site = d.get("website")
    if not site:
        return d
    site = site if site.startswith("http") else "https://" + site
    base = re.match(r"https?://[^/]+", site).group(0)
    with httpx.Client(headers=UA, verify=False) as c:
        home = get(c, site)
        links = [l for l in dict.fromkeys(re.findall(r'href=["\']([^"\'#]+)["\']', home)) if HINT.search(l)][:4]
        pages = [home] + [get(c, urllib.parse.urljoin(base + "/", l)) for l in (links or ["/contact", "/about"])]
    blob = " ".join(pages)
    dom = re.sub(r"^www\.", "", urllib.parse.urlparse(site).netloc)
    emails = []
    for e in re.findall(r"mailto:([^\"'?\s>\\]+)", blob) + EMAIL_RE.findall(blob):
        m = EMAIL_RE.search(urllib.parse.unquote(e))  # keep only the address itself (no trailing \ or junk)
        if not m:
            continue
        e = m.group(0)
        e = urllib.parse.unquote(e).lower().strip(".")
        if not BAD.search(e) and e not in emails:
            emails.append(e)
    emails.sort(key=lambda e: (not e.endswith(dom), not re.match(r"(marketing|social|media|comm|pr|brand|digital|content|info|contact|hello)", e)))
    if emails:
        d["email"] = emails[0]
        d["emails"] = emails[:15]  # all addresses on the site: the agent looks among them for a named decision maker
    for k, rx in SOCIAL.items():
        m = re.search(rx, blob)
        if m and not d.get(k) and not re.search(r"/(sharer|share|tr|plugins|intent)\b", m.group(0)):
            d[k] = m.group(0)
    about = "\n---\n".join(text(p)[:1500] for p in pages if p)
    if about:
        d["about"] = about[:4000]
    return d


# ---------------- Deep analysis (ScrapeGraphAI + local Ollama, free) ----------------
DEEP_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
DEEP_PROMPT = ("Extract facts about this organisation for a film/photo studio that wants to introduce itself to them. "
               "JSON keys: summary, mission, programs (list), recent_projects_or_stories (list of specific names), "
               "audiences (list), events_or_campaigns (list), uses_video (yes/no + evidence), "
               "comms_contact (name, role, email), language_of_site. Only facts present in the text; empty if unknown.")


def deep_graph():
    """Returns a function text->facts, or None if ScrapeGraphAI/Ollama isn't available."""
    try:
        import langchain_community.chat_models as cm
        from langchain_ollama import ChatOllama
        cm.ChatOllama = ChatOllama  # scrapegraphai still imports it from the old location
        from scrapegraphai.graphs import SmartScraperGraph
        httpx.get("http://127.0.0.1:11434/api/tags", timeout=3)
    except Exception as e:
        print("  (deep analysis unavailable:", str(e)[:80], ")")
        return None
    cfg = {"llm": {"model": "ollama/" + DEEP_MODEL, "temperature": 0, "format": "json", "model_tokens": 8192}, "verbose": False}

    def run(text):
        r = SmartScraperGraph(prompt=DEEP_PROMPT, source=text, config=cfg).run()
        return r.get("content", r) if isinstance(r, dict) else r
    return run


def deepen(rows):
    run = deep_graph()
    if not run:
        return rows
    todo = [r for r in rows if r.get("about")]
    print(f"\n🧠 deep analysis of {len(todo)} sites with {DEEP_MODEL} (local, free)…")
    for i, r in enumerate(todo, 1):
        try:
            facts = run(r["about"])
            c = facts.get("comms_contact") if isinstance(facts, dict) else None
            if isinstance(c, dict) and not r.get("email") and "@" in str(c.get("email", "")):
                r["email"] = c["email"]
            r["about"] = "FACTS (extracted):\n" + json.dumps(facts, ensure_ascii=False) + "\n---\n" + r["about"]
            print(f"  [{i}/{len(todo)}] {r['name']}: {str(facts.get('summary', ''))[:90] if isinstance(facts, dict) else ''}")
        except Exception as e:
            print(f"  [{i}/{len(todo)}] {r['name']}: ✗ {str(e)[:80]}")
    return rows


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        ph = re.sub(r"\D", "", r.get("phone") or "")[-9:]
        keys = {k for k in (ph and "p" + ph, r.get("website") and "w" + re.sub(r"^(https?://)?(www\.)?", "", r["website"]).split("/")[0],
                             "n" + re.sub(r"\W", "", r["name"].lower()) + (r.get("city") or "")) if k}
        if keys & seen:
            continue
        seen |= keys
        out.append(r)
    return out


# ---------------- Buying signals (ReliefWeb) ----------------
SIGNAL_TERMS = ["videographer", "video production", "documentary", "photographer", "audiovisual", "multimedia",
                "communication officer", "communications officer", "visibility", "media production", "content creator",
                "storytelling", "RFQ video", "photography services"]
RELEVANT_TITLE = re.compile(r"video|film|photo|media|communicat|visibility|content|audiovisual|multimedia|documentar|"
                            r"storytell|campaign|advocacy|outreach|branding|RFQ|RFP|tender|quotation|event|إعلام|تصوير|اتصال", re.I)
COUNTRY_ID = {"Jordan": "C129"}
VIDEO_WORDS = re.compile(r"video|film|documentar|photo|audiovisual|multimedia|media production|filming|تصوير|فيديو", re.I)


def signals(country="Jordan"):
    """Organisations in the country that are hiring comms/media people or tendering media work right now."""
    from email.utils import parsedate_to_datetime
    out, seen = [], set()
    cid = COUNTRY_ID.get(country)
    for term in [""] + SIGNAL_TERMS:
        params = {"search": term} if term else {}
        if cid:
            params["advanced-search"] = f"({cid})"
        try:
            xml = httpx.get("https://reliefweb.int/jobs/rss.xml", params=params, headers=UA, timeout=30).text
        except Exception as e:
            print("  ✗", term, e); continue
        for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
            link = re.search(r"<link>(.*?)</link>", item).group(1)
            desc = html.unescape(re.search(r"<description>(.*?)</description>", item, re.S).group(1))
            if link in seen or f"Country: {country}" not in desc:
                continue
            seen.add(link)
            title = html.unescape(re.search(r"<title>(.*?)</title>", item).group(1))
            org = re.search(r"Organization: ([^<]+)", desc)
            close = re.search(r"Closing date: ([^<]+)", desc)
            if not org or not RELEVANT_TITLE.search(title):
                continue
            from datetime import datetime
            until = datetime.strptime(close.group(1).strip(), "%d %b %Y").date().isoformat() if close else None
            body = text(desc)
            tender = re.search(r"(RFQ|RFP|tender|quotation|EOI|expression of interest|consultan)", title, re.I)
            kind = "Tender" if tender else "Hiring"
            hot = bool(VIDEO_WORDS.search(title + " " + body[:3000]))
            if tender and not VIDEO_WORDS.search(title + " " + body[:6000]):
                continue  # a tender for something we don't do
            out.append({
                "name": org.group(1).strip(), "kind": "ngo", "city": None, "source": "reliefweb",
                "signal": f"{kind}: {title}" + ("" if hot else " (comms)"), "signal_url": link, "signal_until": until,
                "about": f"Their current posting — {title}:\n{body[:3500]}",
            })
            print(f"  🔔 {org.group(1).strip()} — {title} (closes {until})")
    return out


def ask(prompt, default):
    v = input(f"{prompt} [{default}]: ").strip()
    return v or default


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Kinds:", ", ".join(PRESETS), "| signals = organisations hiring media people / tendering video work now")
    kind = ask("Kind", "ngo")
    if kind == "signals":
        rows = signals(ask("Country", "Jordan"))
        path = f"leads-signals-{date.today()}.json"
        json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n✅ {len(rows)} live opportunities → {path}\nUpload it in the site: ⬆️ استيراد من الجامع")
        sys.exit()
    cities = [c.strip() for c in ask("Cities (comma separated, or 'all'; Irbid first)", "Irbid").split(",")]
    cities = CITIES if cities == ["all"] else cities
    custom = ask("Custom search terms (comma separated, empty = presets)", "")
    terms = [t.strip() for t in custom.split(",") if t.strip()] or PRESETS[kind]
    per = int(ask("Max places per search", "40"))
    show = ask("Show browser? y/n", "n") == "y"
    deep = ask("Deep analysis with local AI (ScrapeGraphAI + Ollama, ~15s/site)? y/n", "y" if kind in ("ngo", "org") else "n") == "y"

    qs = [(kind, f"{t} in {c} Jordan", c) for c in cities for t in terms]
    print(f"\n{len(qs)} searches…")
    ck = ckpt_load(kind)
    if ck["rows"] or ck["queries_done"]:
        print(f"↻ resuming the previous run: {len(ck['rows'])} places and {len(ck['queries_done'])} searches already saved")
    try:
        maps(qs, per, show, ck, kind)
    except KeyboardInterrupt:
        print("\n⏹ stopped by you: processing what was collected so far (run again to continue the rest)")
    rows = dedupe(ck["rows"])
    print(f"\n🌐 reading {sum(1 for r in rows if r.get('website'))} websites…")
    with ThreadPoolExecutor(8) as ex:
        rows = list(ex.map(read_site, rows))
    if deep:
        rows = deepen(rows)
    path = f"leads-{kind}-{date.today()}.json"
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if len(ck["queries_done"]) >= len(qs):
        try:
            os.remove(ckpt_path(kind))  # finished: the next run starts fresh
        except OSError:
            pass
    print(f"\n✅ {len(rows)} unique leads, {sum(1 for r in rows if r.get('email'))} with email → {path}")
    print("Upload it in the site: ⬆️ استيراد من الجامع")
