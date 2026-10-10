"""Local analysis on your GPU (Ollama) — no Lovable credit.

Reads each new lead's website, builds the same profile the site's AI builds (who they are, interests,
content needs, best service, angle, hook, closest flagship work, which site to link, language, score)
and saves it, so "best new leads" and message writing work from it.
"""
import json, os, re, sys, time
from datetime import date
from pathlib import Path
import httpx
import emailcheck

sys.path.insert(0, str(Path(__file__).parent.parent / "harvester"))
from harvest import read_site, is_blocked, school_ok  # same website reader the collector uses (email, socials, text)

OLLAMA = "http://127.0.0.1:11434"

SYSTEM = """You research potential clients for Ahmad Haddad, a director/cinematographer with a team (FAII House) in Jordan,
before anyone contacts them. Figure out what kind of client this is, what they care about, and what visual content would
genuinely help them. Be honest: weak signals = low score. Organisations with programmes, beneficiaries, donors, campaigns
or anniversaries are strong documentary fits; brands, restaurants and cafés fit brand films, ads and social content.
Write the profile in Arabic, except names. Return JSON only."""

SCHEMA = """{"summary":"who they are, one line","interests":["what they care about"],"content_needs":["visual content they likely need"],
"best_service":"one of our services","other_services":["..."],"angle":"one concrete film/photo idea made for them",
"hook":"a real specific detail from their info to open with. If RECENT PUBLIC NEWS is given and relates to them, use the newest relevant item (say what happened, no date needed, never invent beyond it). Empty if none","portfolio_pick":"name of the closest ★ work (no url)",
"link_pick":"personal | team | behance","tone":"formal|warm|casual","lang":"ar|en","channel":"email|whatsapp|instagram",
"decision_maker":"role to address","score":0-100,"why":"one short line"}"""

LANG_HINT = """Language for the future message: UN agencies, international NGOs/donors, EU programmes, embassies, international brands and
tech companies → en; Jordanian institutions, local charities and initiatives, restaurants, cafés, shops and local brands → ar.
Their own website's main language wins. link_pick: personal for organisations/NGOs/culture/documentary; team for brands,
restaurants, pharmacies, companies, campaigns; behance only for creative agencies."""


NV_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NV_SMALL = "nv:nvidia/nemotron-3-super-120b-a12b"


def _nv_key():
    return os.environ.get("NVIDIA_API_KEY", "").strip()


def is_nv(model):
    return str(model).startswith("nv:")


def available(model):
    if is_nv(model):
        return bool(_nv_key())
    try:
        names = [m["name"] for m in httpx.get(f"{OLLAMA}/api/tags", timeout=5).json()["models"]]
        return model in names or f"{model}:latest" in names
    except Exception:
        return False


def _nv_chat(model, messages, temperature):
    """NVIDIA's hosted models (free tier, OpenAI-compatible). Retries a rate limit / server error once."""
    for attempt in range(2):
        r = httpx.post(NV_URL, timeout=120, headers={"Authorization": "Bearer " + _nv_key()},
                       json={"model": model[3:], "temperature": temperature, "max_tokens": 2048, "messages": messages,
                             "chat_template_kwargs": {"enable_thinking": False}})
        if (r.status_code == 429 or r.status_code >= 500) and attempt == 0:
            time.sleep(8)
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""


def _ollama_chat(model, messages, temperature, as_json):
    body = {"model": model, "stream": False, "options": {"temperature": temperature, "num_ctx": 8192}, "messages": messages}
    if as_json:
        body["format"] = "json"
    r = httpx.post(f"{OLLAMA}/api/chat", timeout=300, json=body)
    r.raise_for_status()
    return r.json()["message"]["content"]


_down = {}  # model -> time until which it is skipped (hung or failing)


def complete(model, system, user, temperature=0.2, as_json=True):
    """One call to the chosen model. 'nv:<id>' = NVIDIA; if it fails, the local Ollama model (OLLAMA_MODEL) takes over."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if is_nv(model):
        err = RuntimeError("NVIDIA models are resting after failures")
        for m in dict.fromkeys([model, NV_SMALL]):  # big model first, then the faster NVIDIA one, then local
            if _down.get(m, 0) > time.time():
                continue  # failed recently: don't wait another 2 minutes on it
            try:
                return _nv_chat(m, messages, temperature)
            except Exception as e:
                err = e
                _down[m] = time.time() + 1800
                print(f"{m} failed ({type(e).__name__}) — skipping it for 30 min", flush=True)
        model = os.environ.get("OLLAMA_MODEL", "qwen2.5:14b")
        if not available(model):
            raise err
        print(f"NVIDIA failed ({str(err)[:80]}), using local {model}", flush=True)
    return _ollama_chat(model, messages, temperature, as_json)


def chat(model, system, user):
    txt = complete(model, system, user)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("model returned no JSON")
    return json.loads(m.group(0))


# ---------------- Fresh facts (Exa web search, no key) ----------------
EXA = "https://mcp.exa.ai/mcp"


def fresh(L, months=12, limit=3):
    """Recent public items about this client, newest first: [{date, title, url, text}]. Only items that mention the client
    by name and are younger than `months`, so the hook is current and about the right organisation."""
    from datetime import datetime, timedelta, timezone
    name = (L.get("name") or "").strip()
    if not name:
        return []
    q = f"{name} {L.get('city') or ''} news projects announcement".strip()
    try:
        text = _exa(q, 8)
    except ExaLimit:
        return None  # None = could not ask (rate limit), unlike [] = asked and found nothing; callers must not mark the lead as checked
    except Exception:
        return []
    place = {"jordan", "amman", "irbid", "zarqa", "aqaba", "الأردن", "عمان", "عمّان", "إربد", "الزرقاء", "العقبة", "the", "of", "and"}
    toks = [w for w in re.findall(r"\w+", re.sub(r"\s*[\(\-|–].*$", "", name).lower()) if len(w) > 1 and w not in place]         or re.findall(r"\w+", name.lower())  # distinctive words of the name; at least half must appear
    need = max(1, (len(toks) + 1) // 2)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30 * months)
    out = []
    for chunk in re.split(r"(?m)^Title: ", text)[1:]:
        title = chunk.splitlines()[0].strip()
        url = (re.search(r"^URL: (\S+)", chunk, re.M) or [None, ""])[1]
        pub = (re.search(r"^Published: (\S+)", chunk, re.M) or [None, ""])[1]
        try:
            when = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except ValueError:
            continue  # undated = can't prove it is current
        body = chunk.split("Highlights:", 1)[-1]
        hay = (title + " " + body).lower()
        if when < cutoff or sum(t in hay for t in toks) < need:
            continue
        out.append({"date": pub[:10], "title": title[:160], "url": url, "text": re.sub(r"\s+", " ", body)[:400].strip()})
    out.sort(key=lambda x: x["date"], reverse=True)
    return out[:limit]


def us(team):
    return "\n".join([
        f"Services:\n{team.get('services', '')}",
        f"Priority: {team.get('focus', '')}",
        "Flagship works (★) and others, title | url | tags:\n" + "\n".join(
            l for l in team.get("portfolio", "").splitlines() if l.strip())[:3500],
        "Past clients (name | sector | language):\n" + team.get("pastClients", "")[:2500],
    ])


def them(L):
    keys = ["kind", "name", "category", "city", "address", "website", "instagram", "facebook", "linkedin", "youtube", "rating", "notes", "signal"]
    lines = [f"{k}: {L[k]}" for k in keys if L.get(k)]
    if L.get("about"):
        lines.append("What their website says:\n" + L["about"][:3500])
    return "\n".join(lines)


HOOK_SYSTEM = """You pick ONE recent news item to open an outreach message with. Rules:
- The item must be about the client itself doing something (launch, partnership, event, award, programme, opening).
- Skip bad news (funding cuts, crises, deaths, scandals, appeals) and items about other organisations or generic pages.
- Pick the newest item that passes. If none passes, answer index -1.
- hook = ONE plain factual sentence stating what happened, using only words found in the item. No praise, no dates, no invented detail.
Return JSON only: {"index": <number or -1>, "hook": "..."}"""


def recent_hook(L, recent, lang, model):
    """Hook built from the newest verified news item. Returns '' when no safe item exists (caller keeps the old hook)."""
    items = "\n".join(f"[{i}] {x['date']} · {x['title']} — {x['text'][:300]}" for i, x in enumerate(recent))
    try:
        out = chat(model, HOOK_SYSTEM, f"CLIENT: {L.get('name')}\nWrite the hook in {'Arabic' if lang == 'ar' else 'English'}.\nITEMS:\n{items}")
        i, hook = int(out.get("index", -1)), str(out.get("hook") or "").strip()
    except Exception:
        return ""
    if not 0 <= i < len(recent) or len(hook) < 15 or len(hook) > 300 or hook[-1] not in ".!؟?":  # cut-off sentence = unsafe
        return ""
    return hook


SIGNAL_SYSTEM = """You spot BUYING SIGNALS: a recent event that makes an organisation more likely to hire a film director / cinematographer NOW.
Signal types: project_launch, grant_funding, campaign, new_branch, event_conference, annual_report, product_launch, rebrand, new_programme, anniversary, award, partnership.
Pick ONE item from the list that is a real signal of one of these types, about the client itself, positive or neutral (no crises, funding cuts, appeals, deaths).
- text = one short Arabic sentence saying what happened and why it creates a need for film or photo content. Use only facts in the item.
- until = the date of the upcoming event/deadline ONLY if it is written in the item, else null.
Return JSON only: {"index": <number or -1>, "type": "<one of the types>", "text": "...", "until": "YYYY-MM-DD or null"}. index -1 when nothing qualifies."""
SIGNAL_TYPES = {"project_launch", "grant_funding", "campaign", "new_branch", "event_conference", "annual_report", "product_launch", "rebrand",
                "new_programme", "anniversary", "award", "partnership"}


def buying_signal(L, recent, model):
    """{type, text, url, until} for the newest qualifying news item, or None. The model picks, code checks dates:
    the signal lives 45 days from the news date (or until the written upcoming date), so only 'happening now' counts."""
    from datetime import date, timedelta
    items = "\n".join(f"[{i}] {x['date']} · {x['title']} — {x['text'][:300]}" for i, x in enumerate(recent))
    try:
        out = chat(model, SIGNAL_SYSTEM, f"CLIENT: {L.get('name')}\nITEMS:\n{items}")
        i, typ, text = int(out.get("index", -1)), out.get("type"), str(out.get("text") or "").strip()
    except Exception:
        return None
    if not 0 <= i < len(recent) or typ not in SIGNAL_TYPES or len(text) < 15 or text[-1] not in ".!؟?":
        return None
    today, news_day = date.today(), date.fromisoformat(recent[i]["date"])
    until = news_day + timedelta(days=45)
    try:
        written = date.fromisoformat(str(out.get("until"))) if out.get("until") else None
    except ValueError:
        written = None
    if written and written >= today and written.isoformat() in (recent[i]["text"] + recent[i]["title"]):
        until = max(until, written)
    if until < today:
        return None  # older than 45 days with no upcoming date: not "now"
    return {"type": typ, "text": text, "url": recent[i]["url"], "until": until.isoformat()}


PEOPLE_SYSTEM = """You find who to address at an organisation, from web search snippets. Rules:
- Only people the snippet says CURRENTLY work at that exact organisation (same country office if the snippet says so).
- Skip anyone described as former / ex- / left / "after N years" / "new job", people at other organisations or other country offices, and posts about someone else.
- name must be copied EXACTLY as written in the snippet. Never guess, never complete a name.
- role = their title as written. Prefer communications / media / marketing / outreach / partnerships / fundraising, then director / head / owner / founder / general manager.
Return JSON only: {"people":[{"name":"...","role":"...","url":"...","index":<snippet number>}]}. Empty list when unsure."""
ROLE_OK = re.compile(r"communicat|comms|media|marketing|outreach|advocacy|public information|brand|content|social media|fundrais|partnership|resource mobili|director|head of|manager|owner|founder|ceo|chief|president|coordinator|officer", re.I)
ROLE_TOP = re.compile(r"communicat|comms|media|marketing|outreach|advocacy|public information|brand|content|social media|fundrais|partnership", re.I)
STALE = re.compile(r"\b(former|formerly|ex-|previously|past)\b|\bafter \d+ years\b|new job|i'?m now|officially (left|leaving)", re.I)
ORG_KINDS = {"ngo", "org", "hotel", "brand", "event", "pharmacy", "school", "roastery"}


class ExaLimit(Exception):
    """Exa's rate limit (the keyless MCP is limited). Set EXA_API_KEY in agent.env for a real quota."""


_exa_block = {"until": 0.0}


def exa_limited():
    return time.time() < _exa_block["until"]


def _exa(query, n=8):
    if exa_limited():
        raise ExaLimit("cooling down")
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if os.environ.get("EXA_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["EXA_API_KEY"]
    r = httpx.post(EXA, timeout=40, headers=headers,
                   json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "web_search_exa", "arguments": {"query": query, "numResults": n}}})
    if r.status_code == 429 or "rate limit" in r.text[:300].lower():
        _exa_block["until"] = time.time() + 1800  # stop hammering for 30 minutes
        raise ExaLimit("Exa rate limit")
    data = next((json.loads(l[5:]) for l in r.text.splitlines() if l.startswith("data:")), {})
    return "".join(c.get("text", "") for c in data.get("result", {}).get("content", []))


def find_people(L, model, limit=3):
    """Candidate decision makers: [{name, role, url, top, status:'unverified'}]. Every name must appear verbatim in the search
    text and pass the staleness filter. Still candidates, never facts: a human checks before anyone is addressed by name."""
    name, city = (L.get("name") or "").strip(), (L.get("city") or "").strip()
    if not name:
        return []
    try:
        text = _exa(f"{name} {city} communications marketing director head linkedin.com/in") + "\n" + _exa(f"{name} team staff communications director")
    except Exception:  # includes ExaLimit: no names is safe, the next refresh retries (people stays empty)
        return []
    chunks = []
    for ch in re.split(r"(?m)^Title: ", text)[1:]:
        url = (re.search(r"^URL: (\S+)", ch, re.M) or [None, ""])[1]
        if STALE.search(ch[:900]) or "/posts/" in url:
            continue
        pub = (re.search(r"^Published: (\S+)", ch, re.M) or [None, ""])[1]
        ym = re.search(r"/(20\d\d)-(\d\d)/", url)
        asof = pub[:10] if re.match(r"20\d\d", pub) else (f"{ym.group(1)}-{ym.group(2)}" if ym else "?")
        chunks.append((url, "Title: " + ch[:900], asof))
    if not chunks:
        return []
    snippets = "\n\n".join(f"[{i}] {c[1]}" for i, c in enumerate(chunks[:10]))
    try:
        out = chat(model, PEOPLE_SYSTEM, f"ORGANISATION: {name} ({city})\n\nSNIPPETS:\n{snippets}")
    except Exception:
        return []
    org = [w for w in re.findall(r"\w+", name.lower()) if len(w) > 2 and w not in {"jordan", "the", "for", "and"}]
    people = []
    for x in out.get("people") or []:
        try:
            i, pn, role = int(x.get("index")), str(x.get("name") or "").strip(), str(x.get("role") or "").strip()
        except (TypeError, ValueError):
            continue
        if not 0 <= i < min(len(chunks), 10) or len(pn) < 4 or not ROLE_OK.search(role):
            continue
        body = chunks[i][1]
        if pn not in body or not any(w in body.lower() for w in org):  # name verbatim + the organisation named in the same text
            continue
        mails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", body)  # an address printed in the same public text
        people.append({"name": pn, "role": role[:80], "url": chunks[i][0], "top": bool(ROLE_TOP.search(role)), "status": "unverified",
                       "as_of": chunks[i][2], "emails": mails[:5]})
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=548)).strftime("%Y-%m")  # sources older than ~18 months are dropped, not shown
    people = [p for p in people if p["as_of"] == "?" or p["as_of"][:7] >= cutoff]
    people = list({p["name"]: p for p in people}.values())
    people.sort(key=lambda p: not p["top"])
    return people[:limit]


def addressable(L, people):
    """A person we may greet by name: only when the email address itself carries their name (strong evidence it is theirs)."""
    local = re.sub(r"[^a-z]", "", (L.get("email") or "").split("@")[0].lower())
    if not local or emailcheck.check(L["email"]).get("role"):
        return None
    for pr in people:
        parts = [w for w in re.findall(r"[a-z]+", pr["name"].lower()) if len(w) >= 3]
        if parts and any(w in local for w in parts):
            return pr
    return None


def _org_domain(L):
    for v in (L.get("email") or "", L.get("website") or ""):
        d = (v.split("@")[-1] if "@" in v else re.sub(r"^https?://", "", v).split("/")[0]).lower().removeprefix("www.")
        if "." in d and d not in FREE_MAIL:
            return d
    return None


FREE_MAIL = {"gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com", "icloud.com", "me.com", "aol.com"}


def person_email(L, people, site_emails=None):
    """The decision maker's OWN address, only when it is printed publicly (their organisation's site or the search text about
    them), sits on the organisation's domain and carries their name. Never guessed from a pattern: a guess bounces and hurts us.
    Returns {name, role, email, url, as_of} or None."""
    dom = _org_domain(L)
    if not dom or not people:
        return None
    if site_emails is None and L.get("website"):
        try:
            site_emails = read_site({"name": L.get("name"), "website": L["website"]}).get("emails") or []
        except Exception:
            site_emails = []
    pool = {e.lower().strip(".") for e in (site_emails or [])}
    for pr in people:
        pool |= {e.lower().strip(".") for e in pr.get("emails") or []}
    for pr in people:  # people are already ordered: communications / marketing roles first
        parts = [w for w in re.findall(r"[a-z]+", pr["name"].lower()) if len(w) >= 3]
        for e in sorted(pool):
            local, _, d = e.partition("@")
            if not (d == dom or d.endswith("." + dom)) or emailcheck.check(e).get("role"):
                continue
            if parts and any(w in re.sub(r"[^a-z]", "", local) for w in parts) and emailcheck.check(e).get("ok") is not False:
                return {"name": pr["name"], "role": pr["role"], "email": e, "url": pr.get("url"), "as_of": pr.get("as_of")}
    return None


def tier_of(score, L, p):
    """A = worth hand-checking and sending first; B = normal; C = low touch. Decided in code, never by the model.
    A: strong fit AND a reachable person (named mailbox or phone) AND a concrete reason now (fresh news, live signal, or a personal mailbox)."""
    ec = p.get("email_check") or {}
    mail_ok = bool(L.get("email")) and ec.get("ok") is not False
    named = mail_ok and not ec.get("role") or bool((p.get("contact") or {}).get("email"))  # their own mailbox, or the decision maker's
    reachable = named or bool(L.get("phone")) or mail_ok
    if score >= 70 and (named or L.get("phone")) and (p.get("hook_source") == "news" or L.get("signal") or named):
        return "A"
    if score >= 45 and reachable:
        return "B"
    return "C"


def analyze(db, L, team, model):
    """Profile one lead. Returns the patch saved to the database."""
    patch, site_emails = {}, None
    if L.get("website") and not L.get("about"):
        site = read_site({"name": L["name"], "website": L["website"]})
        site_emails = site.get("emails") or []
        for k in ("about", "email", "instagram", "facebook", "linkedin", "youtube", "tiktok"):
            if site.get(k) and not L.get(k):
                patch[k] = site[k]
        L = {**L, **patch}
    recent = fresh(L)
    news_failed = recent is None  # rate limited: analyse without news and leave signal_checked empty so refresh retries later
    recent = recent or []
    if recent:
        L = {**L, "recent": recent}
    p = chat(model, SYSTEM, f"{us(team)}\n\n{LANG_HINT}\n\nCLIENT:\n{them(L)}\n\nReturn JSON exactly in this shape:\n{SCHEMA}")
    try:
        score = max(0, min(100, int(round(float(p.pop("score", 0))))))
    except (TypeError, ValueError):
        score = 0
    for k in ("interests", "content_needs", "other_services"):
        if not isinstance(p.get(k), list):
            p[k] = [p[k]] if p.get(k) else []
    if p.get("channel") not in ("email", "whatsapp", "instagram"):
        p["channel"] = "email" if L.get("email") else "whatsapp" if L.get("phone") else "instagram"
    if p.get("lang") not in ("ar", "en"):
        p["lang"] = "ar"
    if p.get("link_pick") not in ("personal", "team", "behance"):
        p["link_pick"] = "personal" if L.get("kind") in ("ngo", "org", "school") else "team"
    p["analysed_by"] = f"local:{model}"
    if L.get("email"):
        p["email_check"] = emailcheck.check(L["email"])
    if recent:
        p["recent"] = recent
        h = recent_hook(L, recent, p["lang"], model)
        if h:
            p["hook"] = h
            p["hook_source"] = "news"
    active = bool(L.get("signal")) and (not L.get("signal_until") or L["signal_until"] >= date.today().isoformat())
    if recent and not active:
        sig = buying_signal(L, recent, model)
        if sig:
            patch.update(signal=f"{sig['type']}: {sig['text']}", signal_url=sig["url"], signal_until=sig["until"])
            L = {**L, "signal": patch["signal"]}
            p["signal_type"] = sig["type"]
            p["score_base"] = score
            score = min(100, score + 10)  # something is happening now
    p.setdefault("score_base", score)
    if not news_failed:
        p["signal_checked"] = date.today().isoformat()
    if L.get("kind") in ORG_KINDS and score >= 60:
        people = find_people(L, model)
        if people:
            p["people"] = people
            p["decision_maker"] = f"{people[0]['name']} — {people[0]['role']} (مرشّح غير مؤكد، المصدر {people[0]['as_of']})"
            who = addressable(L, people) or person_email(L, people, site_emails)
            if who:
                p["contact"] = who
    p["tier"] = tier_of(score, L, p)
    patch.update(profile=p, score=score)
    db.patch("leads", {"id": L["id"]}, patch)
    return patch


def _signal_active(L):
    return bool(L.get("signal")) and (not L.get("signal_until") or L["signal_until"] >= date.today().isoformat())


def refresh(db, L, model):
    """Light re-check of an already analysed lead: fresh news, hook, buying signal, email check, decision makers, tier.
    Keeps the rest of the profile (who they are, angle, services) untouched — 2 to 4 model calls instead of a full analysis."""
    p = dict(L.get("profile") or {})
    patch = {}
    base = p.get("score_base", L.get("score") or 0)
    recent = fresh(L)
    if recent is None:
        raise ExaLimit("Exa rate limit")  # nothing is written: the lead stays due for the next refresh
    p.pop("recent", None)
    if recent:
        p["recent"] = recent
        h = recent_hook(L, recent, p.get("lang") or "ar", model)
        if h:
            p["hook"], p["hook_source"] = h, "news"
        if not _signal_active(L):
            sig = buying_signal(L, recent, model)
            if sig:
                patch.update(signal=f"{sig['type']}: {sig['text']}", signal_url=sig["url"], signal_until=sig["until"])
                p["signal_type"] = sig["type"]
    active = _signal_active({**L, **patch})
    if not active:
        p.pop("signal_type", None)
    score = min(100, base + 10) if active else base
    if L.get("email"):
        p["email_check"] = emailcheck.check(L["email"])
    if L.get("kind") in ORG_KINDS and score >= 60 and not p.get("people"):
        people = find_people(L, model)
        if people:
            p["people"] = people
            p["decision_maker"] = f"{people[0]['name']} — {people[0]['role']} (مرشّح غير مؤكد، المصدر {people[0]['as_of']})"
            who = addressable(L, people)
            if who:
                p["contact"] = who
    p["score_base"], p["signal_checked"] = base, date.today().isoformat()
    p["tier"] = tier_of(score, {**L, **patch}, p)
    patch.update(profile=p, score=score)
    db.patch("leads", {"id": L["id"]}, patch)
    return patch


# ---------------- Local writing (same voice rules as the site, read from its source file) ----------------
TS = Path(__file__).parent.parent.parent / "src" / "lib" / "ai.functions.ts"


def _tpl(src, name):
    """Pull a template literal `const NAME = ... \`...\`;` out of ai.functions.ts so both writers share one rulebook."""
    m = re.search(r"const " + name + r"\s*=\s*(?:\([^)]*\)\s*=>\s*)?`(.*?)`;", src, re.S)
    if not m:
        raise RuntimeError(f"{name} not found in ai.functions.ts")
    return m.group(1)


def rules(team):
    src = TS.read_text(encoding="utf-8")
    consts = dict(re.findall(r'const (PERSONAL_SITE|TEAM_SITE|BEHANCE) = "([^"]+)"', src))
    lang = _tpl(src, "LANGUAGE_RULES")
    voice = _tpl(src, "VOICE")
    editor = _tpl(src, "EDITOR")
    def fill(t):
        t = t.replace("${LANGUAGE_RULES}", lang)
        for k, v in consts.items():
            t = t.replace("${" + k + "}", v)
        return re.sub(r"\$\{t\.(\w+)\}", lambda m: str(team.get(m.group(1), "")), t)
    links = (f"LINKS — send exactly one, the full body of work, never a single project:\n"
             f"- {consts['PERSONAL_SITE']} — Ahmad's own site, the ONLY work site: use it for every client.\n"
             f"- {consts['BEHANCE']} — only for creative agencies/studios or when they ask for a portfolio.")
    return fill(voice), editor, links


TASKS = {
    "first": "Write the FIRST message to this client.",
    "followup": "They haven't answered — that's fine. Write ONE gracious, brief note (2–3 lines) that adds value: a different relevant work or a thoughtful observation. No reminder of the previous message, no 'following up', no pressure. This is the only follow-up we ever send.",
    "reply": "Answer their latest message exactly like a human would. Price question → no fixed number unless the price guide gives one; offer to understand the project first. Interested → suggest a short call or meeting at their convenience with two possible times. Not now / no → thank them graciously in one line and wish them well. Asked for work → send the site link with one line of context.",
}


def lang_for(L):
    """One language per message: their profile/site decides; local Arabic-named organisations default to Arabic."""
    p = (L.get("profile") or {}).get("lang")
    arabic_name = bool(re.search(r"[؀-ۿ]", L.get("name", "")))
    if L.get("kind") == "school" and intl_school(L):
        return "en"
    if arabic_name or L.get("kind") in ("restaurant", "brand", "pharmacy", "school", "roastery") and not re.search(r"international|global|un |unicef|usaid", L.get("name", ""), re.I):
        return "ar"
    return p if p in ("ar", "en") else "en"


def works_list(team):
    """Works as natural names with a short description (never 'title | tags' — models copy that format)."""
    out = []
    for l in team.get("portfolio", "").splitlines():
        parts = [x.strip() for x in l.split("|")]
        if len(parts) >= 3 and parts[0]:
            star = "★ " if parts[0].startswith("★") else ""
            out.append(f"- {star}{parts[0].lstrip('★ ').strip()} ({parts[2]})")
    return "\n".join(out)


CLOSES = {  # calm closes, rotated per lead so messages do not share one fingerprint
    "en": ["I'd be glad to discuss the possibility whenever time allows.",
           "If the idea fits, I'd be happy to talk it through.",
           "I'm glad to share more about the idea if it's useful.",
           "I'd welcome your thoughts on it.",
           "The idea is yours to shape; I'm happy to hear what you think.",
           "Happy to explain the idea further whenever suits you."],
    "ar": ["يسعدني مناقشة إمكانية ذلك عند توفّر الوقت.",
           "إن رأيتم أن الفكرة تناسبكم، يسعدني أن نتحدث عنها.",
           "يسرّني أن أشرح الفكرة أكثر إن أحببتم.",
           "يسعدني أن أسمع رأيكم فيها.",
           "الفكرة قابلة للتعديل بما يناسبكم، وأرحّب بملاحظاتكم.",
           "يسعدني الحديث عنها متى ناسبكم."],
}


PHARMACY_CLOSES = ["وإن وجدتم فيها ما يناسب صيدليتكم، يسعدني أن نتحدث متى ناسبكم.",
                   "وإن أعجبكم ما رأيتم، يسرّني أن نتحدث عنه متى شئتم.",
                   "وإن رأيتم أن أسلوبي يناسبكم، يسعدني الحديث معكم في الوقت الذي يريحكم."]


def close_for(L, lang, mode=None):
    import hashlib
    opts = (ROAST_CLOSES if mode == "first" and sector(L) == "roastery" else PHARMACY_CLOSES if mode == "first" and sector(L) == "pharmacy" else
            (SCHOOL_CLOSES if lang == "ar" else SCHOOL_EN_CLOSES) if mode == "first" and sector(L) == "education" else CLOSES["ar" if lang == "ar" else "en"])
    return opts[int(hashlib.md5(("close" + str(L.get("id") or L.get("name"))).encode()).hexdigest(), 16) % len(opts)]


# Any closing line the model writes is replaced by Ahmad's chosen close (exactly one close per message).
CLOSE_LIKE = re.compile(r"timing|conversation|discuss|talk|time allows|convenient|التوقيت|نتحدث|حديث|مناقشة|نناقش|نقاش|الحديث|الوقت|مناسب", re.I)
FLATTERY = re.compile(r"\b(truly|commendable|impressive|amazing|incredible|inspiring|remarkable)\b|رائع|مذهل|ملهم|مبهر|نثمّن|نقدّر جهودكم", re.I)


# Strongest signs of machine writing (after Wikipedia's "Signs of AI writing", via the humanizer skill): structure, not vocabulary.
AI_TELLS = [
    (re.compile(r"\bnot (just|only|merely|simply)\b[^.!?\n]{0,80}\bbut\b|\b(it|this|that)['’]?s not [^.!?\n]{1,60}[,;] (it|this|that)['’]?s\b", re.I), "تركيب «ليس كذا بل كذا»"),
    (re.compile(r"ليس(ت)? (مجرد|فقط)[^.؟!\n]{0,80}بل|لا يقتصر[^.؟!\n]{0,80}بل"), "تركيب «ليس مجرد… بل»"),
    (re.compile(r"\b(at its core|the real question|the heart of|here['’]?s the thing|let['’]?s dive|in today['’]?s|testament to|tapestry|resonates?)\b|في جوهره|الحقيقة أن|شهادة على", re.I), "عبارة تبدو مولّدة"),
    (re.compile(r"\b(pivotal|profound|transformative|seamless|unparalleled|game.?changer)\b|محوري|لا مثيل", re.I), "كلمة مبالغة"),
]


def ai_tells(text):
    """Names of the machine-writing patterns found (empty = reads like a person)."""
    return [name for rx, name in AI_TELLS if rx.search(text or "")]


OPT_OUT = {  # a gracious way out, never needy or apologetic; rotated per lead like the closes
    "en": ["And if the timing isn't right, no problem at all; I wish you well with the work.",
           "If it isn't something you need right now, I completely understand.",
           "If this isn't a priority for you at the moment, that's perfectly fine.",
           "And if it doesn't fit your plans, no worries at all; all the best with your work."],
    "ar": ["وإن لم يكن التوقيت مناسباً فلا بأس أبداً، وسامحونا على الإزعاج.",
           "وإن لم يكن هذا ضمن أولوياتكم الآن فأتفهّم ذلك تماماً، ويعطيكم العافية، وسامحونا على الإزعاج.",
           "وإن لم يكن الأمر مناسباً لكم حالياً فيعطيكم العافية، وسامحونا على الإزعاج.",
           "وإن لم يكن هذا ما تحتاجونه الآن فلا بأس، وكل التوفيق لكم، وسامحونا على الإزعاج."],
}


def opt_out_for(L, lang):
    import hashlib
    opts = OPT_OUT["ar" if lang == "ar" else "en"]
    return opts[int(hashlib.md5(("out" + str(L.get("id") or L.get("name"))).encode()).hexdigest(), 16) % len(opts)]


OFFER = re.compile(r"فيلم|أفلام|نصوّر|نصور|نوثّق بالصورة|film|shoot|video", re.I)  # not "تصوير": it is in the title "مدير تصوير"


PHARMACY_BODY = [  # no film idea on purpose: the portfolio itself is the argument, they look and decide for themselves
    "وبقية أعمالي في الرابط أدناه، تركتها تتحدث عن نفسها. تصفحوها متى شئتم وقرّروا بأنفسكم.",
    "وأعمالي كلها في الرابط أدناه، وأترك لكم الحكم عليها بعد أن تشاهدوها.",
    "وستجدون بقية أعمالي في الرابط أدناه. شاهدوها على مهلكم، فهي تعرّف بي أفضل من أي كلام.",
]
PHARMACY_EXAMPLE = "https://www.behance.net/gallery/243985595/_"  # Ahmad's strongest example, shot in Ramadan; one example, not the portfolio
EXAMPLE_LINES = ["هذا مثال على عمل صوّرته في رمضان:", "ومن أعمالي، مشروع صوّرته في رمضان:"]


def pharmacy_first(L, team):
    """First email to a pharmacy: who I am in one line + the portfolio link. Fixed template, no model, no proposed idea."""
    import hashlib
    h = int(hashlib.md5(("pb" + str(L.get("id") or L.get("name"))).encode()).hexdigest(), 16)
    body = intro_for(L, "ar") + "\n\n" + PHARMACY_BODY[h % len(PHARMACY_BODY)]
    paras = finish(body, L, team, "ar", "first").split("\n\n")
    # the example sits before the "rest of my work" paragraph (finish strips links from the body, so it is added here)
    paras.insert(len(paras) - 3, f"{EXAMPLE_LINES[(h >> 4) % len(EXAMPLE_LINES)]}\n{PHARMACY_EXAMPLE}")
    return f"محتوى مرئي: {short_name(L['name'])}", "\n\n".join(paras)


SCHOOL_WORKS = {  # one strong example per age group, chosen in code
    "older": "https://www.behance.net/gallery/242646259/Duroub-With-Alma",
    "young": "https://www.behance.net/gallery/237148893/Duroub-School",
}
YOUNG = re.compile(r"kinder|nursery|preschool|pre-school|early (years|childhood)|montessori|حضان|روضة|رياض الأطفال|طفول|تمهيدي|أطفال|اطفال", re.I)
SCHOOL_BODY = [
    "هذا مثال على عمل صوّرته لمدرسة:",
    "ومن أعمالي مع المدارس، هذا المشروع:",
    "مثال على ما صوّرته لمدرسة:",
]
SCHOOL_REST = [
    "وبقية أعمالي في الرابط أدناه، تصفحوها متى شئتم وقرّروا بأنفسكم.",
    "وأعمالي كلها في الرابط أدناه، وأترك لكم الحكم عليها بعد أن تشاهدوها.",
    "وستجدون بقية أعمالي في الرابط أدناه، شاهدوها على مهلكم.",
]
ROAST_WORKS = "https://www.behance.net/gallery/248490425/_"
ROAST_BODY = ["هذا مثال على عمل صوّرته لمحمصة قهوة:", "ومن أعمالي مع المحامص، هذا المشروع:", "مثال على ما صوّرته لمحمصة قهوة:"]
ROAST_CLOSES = ["وإن وجدتم فيها ما يناسب محمصتكم، يسعدني أن نتحدث متى ناسبكم.",
                "وإن أعجبكم ما رأيتم، يسرّني أن نتحدث عنه متى شئتم.",
                "وإن رأيتم أن أسلوبي يناسبكم، يسعدني الحديث معكم في الوقت الذي يريحكم."]
SCHOOL_CLOSES = ["وإن وجدتم فيها ما يناسبكم، يسعدني أن نتحدث متى ناسبكم.",
                 "وإن أعجبكم ما رأيتم، يسرّني أن نتحدث عنه متى شئتم.",
                 "وإن رأيتم أن أسلوبي يناسب مدرستكم، يسعدني الحديث معكم في الوقت الذي يريحكم."]


INTL_SCHOOL = re.compile(r"international|american|british|\bIB\b|igcse|cambridge|bilingual|\bacademy\b|دولية|الأمريكية|الامريكية|البريطانية|الإنجليزية", re.I)
SCHOOL_EN_BODY = ["Here is an example of a film I made for a school:", "One project I shot with a school:", "An example of what I filmed for a school:"]
SCHOOL_EN_REST = ["The rest of my work is at the link below; have a look whenever you like and judge for yourselves.",
                  "All my work is at the link below. I'll leave it to speak for itself.",
                  "You'll find the rest of my work at the link below, to look through at your own pace."]
SCHOOL_EN_CLOSES = ["If you find something there that suits your school, I'd be glad to talk whenever it suits you.",
                    "If you like what you see, I'd be happy to talk about it whenever you wish.",
                    "If you feel my style fits your school, I'd welcome a conversation at a time that suits you."]


def intl_school(L):
    """English-language school: Latin-only name, or the name/category says international, American, British, IB, bilingual…"""
    c = f"{L.get('name') or ''} {L.get('category') or ''}"
    return bool(INTL_SCHOOL.search(c)) or not re.search(r"[؀-ۿ]", L.get("name") or "")


def school_first(L, team):
    """First email to a school: who I am, ONE strong example matched to the age group (young children / older), the portfolio link.
    Fixed template, no model, no proposed idea. English for international / English-named schools, Arabic otherwise."""
    import hashlib
    lang = "en" if intl_school(L) else "ar"
    h = int(hashlib.md5(("sb" + str(L.get("id") or L.get("name"))).encode()).hexdigest(), 16)
    c = f"{L.get('name') or ''} {L.get('category') or ''}"
    url = SCHOOL_WORKS["young" if YOUNG.search(c) else "older"]
    rest = (SCHOOL_EN_REST if lang == "en" else SCHOOL_REST)[h % 3]
    lead = (SCHOOL_EN_BODY if lang == "en" else SCHOOL_BODY)[(h >> 4) % 3]
    body = intro_for(L, lang) + "\n\n" + rest
    paras = finish(body, L, team, lang, "first").split("\n\n")
    paras.insert(len(paras) - 3, f"{lead}\n{url}")
    return (f"Visual content: {short_name(L['name'])}" if lang == "en" else f"محتوى مرئي: {short_name(L['name'])}"), "\n\n".join(paras)


SCHOOL_JUDGE = """You decide whether a school in Jordan is PRIVATE (fee-paying: private schools, international/American/British/IB schools, private
nurseries and kindergartens) or PUBLIC (Ministry of Education government school, UNRWA school, or other state-run school).
Use ONLY the evidence given. Private needs real evidence: tuition/fees, 'private', an international curriculum, a private owner or company,
admissions marketing, several branches run by a company. Public needs real evidence: Ministry of Education / UNRWA / 'government', or a
state-style name (e.g. 'الأساسية للبنين', 'الثانوية للبنات') AND nothing pointing to fees or private ownership.
A name alone that merely sounds like a government school is weak evidence. If the evidence does not settle it, answer unknown. Never guess.
Return JSON only: {"type":"private|public|unknown","confidence":0-100,"evidence":"the exact fact or quote you relied on, in one short line"}"""


def judges():
    """Every distinct AI model that is available: NVIDIA hosted (big, small) and the local Ollama models."""
    out = []
    if _nv_key():
        out += ["nv:" + os.environ.get("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"), NV_SMALL]
    for m in ("qwen2.5:14b", "gemma3:12b", os.environ.get("OLLAMA_MODEL", "")):
        if m and m not in out and available(m):
            out.append(m)
    return out


def school_evidence(L):
    """What we can read about the school: Google category, its own site (fees / admissions words), and a web search."""
    parts = [f"Name: {L.get('name')}", f"Google category: {L.get('category')}", f"City/address: {L.get('city')} {L.get('address') or ''}",
             f"Website: {L.get('website')}", f"Instagram: {L.get('instagram')}", f"Facebook: {L.get('facebook')}"]
    about = (L.get("about") or "")[:2500]
    if about:
        parts.append("Text from its website:\n" + about)
    try:
        web = _exa(f"{L.get('name')} {L.get('city') or ''} Jordan school private OR government tuition fees admission مدرسة خاصة رسوم", n=5)
        if web:
            parts.append("Web search results:\n" + web[:2500])
    except Exception:
        pass
    return "\n".join(parts)


def school_type(L, models=None):
    """Private-or-public verdict by several AI models working independently on the same evidence.
    Two models agreeing decide it; a split goes to the next model; no majority or low confidence = unknown (a person decides).
    Returns {verdict: private|public|unknown, confidence, evidence, votes:[{model,type,confidence,evidence}]}."""
    models = models or judges()
    evidence = school_evidence(L)
    votes = []
    for m in models:
        try:
            out = chat(m, SCHOOL_JUDGE, evidence)
        except Exception:
            continue
        t = str(out.get("type") or "unknown").lower()
        try:
            conf = int(out.get("confidence") or 0)
        except (TypeError, ValueError):
            conf = 0
        votes.append({"model": str(m).replace("nv:nvidia/", ""), "type": t if t in ("private", "public") else "unknown",
                      "confidence": conf, "evidence": str(out.get("evidence") or "")[:200]})
        firm = [v for v in votes if v["type"] != "unknown" and v["confidence"] >= 55]
        for kind in ("private", "public"):
            agree = [v for v in firm if v["type"] == kind]
            if len(agree) >= 2 and len(agree) > len(firm) - len(agree):
                return {"verdict": kind, "confidence": round(sum(v["confidence"] for v in agree) / len(agree)),
                        "evidence": agree[0]["evidence"], "votes": votes}
    firm = [v for v in votes if v["type"] != "unknown" and v["confidence"] >= 55]
    if len(votes) == 1 and firm and firm[0]["confidence"] >= 80:  # only one judge available: it must be very sure
        return {"verdict": firm[0]["type"], "confidence": firm[0]["confidence"], "evidence": firm[0]["evidence"], "votes": votes}
    return {"verdict": "unknown", "confidence": 0, "evidence": "لا إجماع بين النماذج" if votes else "لا يوجد نموذج متاح", "votes": votes}


def roastery_first(L, team):
    """First email to a coffee roastery: one line about me, ONE strong example, the portfolio link. Fixed template, no model."""
    import hashlib
    h = int(hashlib.md5(("rb" + str(L.get("id") or L.get("name"))).encode()).hexdigest(), 16)
    body = intro_for(L, "ar") + "\n\n" + SCHOOL_REST[h % len(SCHOOL_REST)]
    paras = finish(body, L, team, "ar", "first").split("\n\n")
    paras.insert(len(paras) - 3, f"{ROAST_BODY[(h >> 4) % len(ROAST_BODY)]}\n{ROAST_WORKS}")
    return f"محتوى مرئي: {short_name(L['name'])}", "\n\n".join(paras)


def write(L, team, history, channel, mode, hint, model):
    """Write, and retry once if the model skipped the idea or cleanup left too little (never queue a hollow message)."""
    if mode == "first" and sector(L) == "roastery":
        return roastery_first(L, team)
    if mode == "first" and sector(L) == "pharmacy":
        return pharmacy_first(L, team)
    if mode == "first" and sector(L) == "education":
        return school_first(L, team)
    last = None
    for attempt in range(2):
        try:
            subject, final = _write_once(L, team, history, channel, mode,
                                         hint if attempt == 0 else ((hint or "") + " The idea sentence is mandatory: say plainly what short film we could shoot for them."), model)
            core = " ".join(final.split("\n\n")[1:-2])
            tells = ai_tells(final)
            if (mode != "first" or OFFER.search(core)) and (not tells or attempt == 1):
                return subject, final  # tells that survive a second try are caught by the send gate, never sent silently
            last = ValueError("the message has no clear film idea" if not tells else "reads machine-written: " + ", ".join(tells))
            if tells:
                hint = (hint or "") + " Write it plainly, like a person: no 'not just X but Y', no dramatic closing line, no inflated words."
        except ValueError as e:
            last = e
    raise last


# ---------------- Sector-matched proof (decided in code, never by the model) ----------------
NGO_PROOF = ["USAID", "UNICEF", "Mercy Corps", "UN Women", "QRTA", "Erasmus"]
FOOD_PROOF = ["Em Sherif", "Khan Zaid", "Astrolabe", "Arafah", "Arafa", "L'Occitane", "أم شريف", "خان زيد", "إسطرلاب", "اسطرلاب", "عرفة", "لوكسيتان"]


def sector(L):
    c = f"{L.get('category') or ''} {L.get('name') or ''}".lower()
    if L.get("kind") == "roastery":
        return "roastery"
    if L.get("kind") == "pharmacy" or re.search(r"pharmac|drugstore|صيدلي|دواء", c):
        return "pharmacy"
    if L.get("kind") == "school":
        return "education"
    if L.get("kind") in ("restaurant",) or re.search(r"restaurant|cafe|café|coffee|bakery|sweets|dessert|roaster|مطعم|كافيه|مقهى|مخبز|حلويات|محمص|فرن", c):
        return "food"
    if L.get("kind") == "brand" or re.search(r"store|shop|boutique|cosmetic|perfume|jewel|salon|متجر|عطور|مجوهرات|تجميل", c):
        return "brand"
    if L.get("kind") == "hotel":
        return "hotel"
    if re.search(r"school|university|academy|college|education|مدرسة|جامعة|أكاديمية|كلية|تعليم", c):
        return "education"
    if L.get("kind") == "event":
        return "event"
    return "ngo"


INTROS = {  # no client names: the site's logos speak. Rotated per lead so emails don't repeat the same line.
    "ngo": {
        "ar": ["أنا أحمد حدّاد، مخرج ومدير تصوير من الأردن، أعمل منذ سنوات مع منظمات ومؤسسات على أفلام تروي أثر عملها من خلال الناس.",
               "أنا أحمد حدّاد، مخرج ومدير تصوير، وجزء كبير من عملي أفلام وثائقية قصيرة لجهات تعمل في المجتمع.",
               "أنا أحمد حدّاد، مخرج ومدير تصوير من الأردن، أصنع أفلاماً قصيرة عن الناس الذين يقفون خلف البرامج والمبادرات."],
        "en": ["I'm Ahmad Haddad, a director and cinematographer in Jordan; for years I've worked with organisations on films that show their impact through people.",
               "I'm Ahmad Haddad, a director and cinematographer; much of my work is short documentaries for organisations working in the community.",
               "I'm Ahmad Haddad, a director and cinematographer based in Jordan, and I make short films about the people behind programmes and initiatives."],
    },
    "education": {
        "ar": ["أنا أحمد حدّاد، مخرج ومدير تصوير من الأردن، صنعت أفلاماً لمؤسسات تعليمية تروي قصص طلابها ومعلميها.",
               "أنا أحمد حدّاد، مخرج ومدير تصوير، وجزء من عملي أفلام قصيرة لمدارس ومؤسسات تعليمية."],
        "en": ["I'm Ahmad Haddad, a director and cinematographer in Jordan; I've made films for educational institutions about their students and teachers.",
               "I'm Ahmad Haddad, a director and cinematographer; part of my work is short films for schools and education programmes."],
    },
    "roastery": {
        "ar": ["أنا أحمد حدّاد، مخرج ومدير تصوير، أصنع أفلاماً وريلز لمحامص القهوة المختصة.",
               "أنا أحمد حدّاد، مخرج ومدير تصوير من إربد، صوّرت لمحامص قهوة، وأعرف كيف تُصوَّر الحبّة والمحمصة والكوب."],
        "en": ["I'm Ahmad Haddad, a director and cinematographer; I make films and reels for specialty coffee roasters."],
    },
    "pharmacy": {
        "ar": ["أنا أحمد حدّاد، مخرج ومدير تصوير من إربد، صوّرت عشرات الريلز لصيدلية محلية، وأحرص أن تبدو الصيدلية بصرياً بمستوى الثقة الذي تقدمه.",
               "أنا أحمد حدّاد، مخرج ومدير تصوير، أصنع محتوى ريلز للصيدليات يجمع بين نظافة الصورة وثقة القطاع الطبي."],
        "en": ["I'm Ahmad Haddad, a director and cinematographer from Irbid; I've shot dozens of reels for a local pharmacy.",
               "I'm Ahmad Haddad, a director and cinematographer; I make reels for pharmacies with clean light and colour that fit a trusted health brand."],
    },
    "food": {
        "ar": ["أنا أحمد حدّاد، مخرج ومدير تصوير، أصنع مع فريقي أفلاماً وإعلانات للمطاعم والمقاهي في الأردن.",
               "أنا أحمد حدّاد، مخرج ومدير تصوير من إربد، أعمل مع فريقي على أفلام وإعلانات للمطاعم والمقاهي."],
        "en": ["I'm Ahmad Haddad, a director and cinematographer; with my team I make films and ads for restaurants and cafés in Jordan.",
               "I'm Ahmad Haddad, a director and cinematographer based in Jordan, making films and ads with my team for restaurants and cafés."],
    },
    "brand": {
        "ar": ["أنا أحمد حدّاد، مخرج ومدير تصوير، أصنع مع فريقي إعلانات وأفلاماً للعلامات التجارية في الأردن.",
               "أنا أحمد حدّاد، مخرج ومدير تصوير من الأردن، أعمل مع فريقي على حملات وأفلام للعلامات التجارية."],
        "en": ["I'm Ahmad Haddad, a director and cinematographer; with my team I make ads and brand films in Jordan.",
               "I'm Ahmad Haddad, a director and cinematographer based in Jordan, working with my team on campaigns and brand films."],
    },
}
INTROS["hotel"] = INTROS["food"]
INTROS["event"] = INTROS["ngo"]
ALL_CLIENT_NAMES = NGO_PROOF + FOOD_PROOF + ["Sirr Al-Dawa", "Sir Al Dawa", "سر الدواء"] + ["Duroub", "دروب", "رانيا", "Mercy Corps", "UNICEF", "UN Women", "Jameel"]


def intro_for(L, lang):
    import hashlib
    opts = INTROS[sector(L)]["ar" if lang == "ar" else "en"]
    return opts[int(hashlib.md5(str(L.get("id") or L.get("name")).encode()).hexdigest(), 16) % len(opts)]


def wrong_proof(L, body):
    """Ahmad's rule: no client names in outreach — the website shows who he worked with."""
    body = re.sub(r"https?://\S+", " ", body)  # the allowed portfolio links may carry a project name; only prose counts
    return [n for n in ALL_CLIENT_NAMES if n.lower() in body.lower()]



def _write_once(L, team, history, channel, mode, hint, model):
    voice, editor, links = rules(team)
    lang = lang_for(L)
    # Past clients are NOT given to the model any more: the one proof line is chosen in code by sector (see PROOF).
    ctx = (f"Sender: {team.get('senderName')}, {team.get('company')}\nWho we are: {team.get('whoWeAre', '')}\n"
           "Never open with 'I would like to propose' / 'أود أن أقترح' — open with them.")
    user = (f"{ctx}\n\nCLIENT:\n{them(L)}\n\nWHAT WE KNOW ABOUT THEM:\n{json.dumps({k: v for k, v in (L.get('profile') or {}).items() if k not in ('people', 'email_check', 'contact', 'recent')}, ensure_ascii=False)}\n\n"
            f"CONVERSATION SO FAR:\n{history or '(none)'}\n\nCHANNEL: {channel}\nTASK: {TASKS[mode]}"
            + (f"\nEXTRA INSTRUCTION FROM AHMAD: {hint}" if hint else "")
            + f"\n\nLANGUAGE: write the whole message in {'Arabic (elegant, correct Modern Standard Arabic)' if lang == 'ar' else 'English'}."
            + "\nNO praise words at all (no 'truly', 'commendable', 'impressive', 'رائع', 'ملهم'). State facts, not compliments."
            + "\nABOUT OUR PAST WORK: say only the client name (e.g. 'USAID', 'QRTA') exactly as listed. NEVER add a city, topic, year or any detail "
              "about that past work — you don't know them. 'We have documented similar stories for USAID' is right; 'for USAID in Ramtha' is a lie."
            + "\nTHE OFFER MUST BE CLEAR: the idea sentence says plainly that WE would film/photograph it, e.g. 'a short film we would shoot, following…' / "
              "'فيلم قصير نصوّره يتابع…'. Never only vague words like 'توثيق' or 'highlight' — it must not read like a comment or a complaint about their work."
            + "\nThe idea is a POSSIBILITY, never something already happening: 'we could film…' / 'يمكن أن نصوّر…' — never 'we are working on' / 'نعمل على'. ONE idea only, no lists of extra films."
            + f"\nThe subject must be in {'Arabic' if lang == 'ar' else 'English'}."
            + "\nNEVER propose a title or name for a film (no 'titled', no 'بعنوان', no «…» names). Describe the idea in plain words."
            + "\nSTRUCTURE (mandatory): 1) greeting; 2) one specific observation about their work (the hook); "
              "3) this exact introduction line: " + repr(intro_for(L, lang)) + " "
              + "Mention NO past clients or projects by name. 4) the idea for their story in one or two sentences, fitting their world "
              + ("(a restaurant/brand: a short film or ad about their food/product/place, not a documentary about social impact)" if sector(L) in ("food", "brand", "hotel") else
                "(a pharmacy: a short reel about the branch, its team and a service or product, clean and trustworthy; never health claims, never criticise their current content)" if sector(L) == "pharmacy" else
                "(a school: an admission-campaign film, open day or event aftermovie about its students and teachers)" if sector(L) == "education" else "")
              + "; 5) one calm closing line. "
              "Never write 'I am available'. Do NOT write a signature or any link; they are added for you."
            + '\n\nReturn JSON: {"subject":"' + ("2-5 calm words about them" if channel == "email" else "") + '","body":"the full message"}')
    out = chat(model, voice + "\nReturn JSON only.", user)
    body = next((v for v in (out.get("body"), out.get("message"), out.get("text")) if isinstance(v, str) and len(v.strip()) > 20), None)
    if not body:
        raise ValueError("the local model wrote no message")
    subject = out.get("subject") or ""
    try:  # editor pass, same rules as the site
        ed = chat(model, editor + f"\nThe message must stay in {'Arabic' if lang == 'ar' else 'English'}. Remove any praise words.",
                  f"CLIENT:\n{them(L)}\n\nCHANNEL: {channel}\nSUBJECT: {subject}\nDRAFT:\n{body}")
        if isinstance(ed.get("body"), str) and len(ed["body"].strip()) > 20:
            body, subject = ed["body"], ed.get("subject") or subject
    except Exception:
        pass
    final = finish(body, L, team, lang, mode)
    core = final.split("\n\n")[1:-2]  # between greeting and close+signature
    if len(" ".join(core)) < max(80, len(body) * 0.4):
        raise ValueError("cleanup removed the message body — not queued")  # never send an empty-looking message
    return subject.strip() or None, final


SITES = {"personal": "https://ahmadhaddad.lovable.app", "team": "https://ahmadhaddad.lovable.app", "behance": "https://www.behance.net/ahmad00haddad"}


def short_name(name):
    """'International Rescue Committee (IRC) - Jordan' → 'IRC Jordan'; Arabic names stay as they are."""
    acr = re.search(r"\(([A-Za-z]{2,8})\)", name)
    if acr:
        return acr.group(1) + (" Jordan" if "jordan" in name.lower() else "")
    return re.sub(r"\s+[-–|]\s+[^-–|]*$", "", name).strip() or name


def finish(body, L, team, lang="en", mode="first"):
    """Deterministic polish: no em dashes, no stray links, no praise filler, a calm close, one signature with the one right site."""
    body = re.sub(r"\s*—\s*", "، " if re.search(r"[؀-ۿ]", body) else ", ", body.strip())
    body = re.sub(r"https?://\S+", "", body).strip()
    body = re.sub(r"^.*\|.*\|.*$", "", body, flags=re.M)  # a pasted 'title | url | tags' line
    body = re.sub(r"[ \t]*\b(truly|really)\s+", " ", body, flags=re.I)
    name = team.get("senderName") or "Ahmad Haddad"
    lines = body.splitlines()
    # only short trailing lines can be a signature the model wrote — never the body itself
    while lines and (not lines[-1].strip() or len(lines[-1]) < 60 and (name.split()[0] in lines[-1] or "حدّاد" in lines[-1] or "حداد" in lines[-1]
                                                                      or re.search(r"FAII|regards|تحياتي|مع التقدير|مع خالص|www\.|\.com|@|https?:", lines[-1], re.I))):
        lines.pop()  # drop any signature the model wrote itself
    text = "\n".join(lines).strip()
    # Remove only the weak closing SENTENCE (never a whole line — the model sometimes writes everything on one line)
    text = re.sub(r"[^.؟?!\n]*(\b(I am|I'm) available\b|متاح(ون)? ل|يسعدني التواصل|لا تتردد)[^.؟?!\n]*[.؟?!]?", "", text, flags=re.I).strip()
    # No proposed film titles (Ahmad's rule): drop 'بعنوان «…»' / 'titled "…"' and keep the plain description
    text = re.sub(r"\s*(بعنوان|تحت عنوان)\s*«[^»]{1,60}»", "", text)
    text = re.sub(r"\s*,?\s*(titled|entitled|called)\s*[\"“'‘][^\"”'’]{1,60}[\"”'’]", "", text, flags=re.I)

    def split_long(par):  # a wall of text → short paragraphs, one or two sentences each
        if len(par) <= 250:
            return par
        out, cur = [], ""
        for x in [x for x in re.split(r"(?<=[.؟?!])\s+", par) if x.strip()]:
            cur = (cur + " " + x).strip()
            if len(cur) > 140:
                out.append(cur); cur = ""
        return "\n\n".join(out + ([cur] if cur else []))
    text = "\n\n".join(split_long(p.strip()) for p in re.split(r"\n\s*\n", text) if p.strip())
    text = "\n".join(l for l in text.splitlines() if not re.fullmatch(r"\s*[\[\]{}()*_#>\-–]+\s*", l))  # stray brackets/markdown
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    paras = [p for p in text.split("\n\n") if p.strip()]
    # Drop the model's own closing SENTENCES only — it sometimes glues the intro and the close into one paragraph.
    while paras:
        sents = [x for x in re.split(r"(?<=[.؟?!])\s+", paras[-1].strip()) if x.strip()]
        kept = list(sents)
        while kept and len(kept[-1]) < 160 and CLOSE_LIKE.search(kept[-1]):
            kept.pop()
        if kept == sents:
            break
        if kept:
            paras[-1] = " ".join(kept)
            break
        paras.pop()
    # Our intro line replaces whatever intro the model wrote (no client names, rotated phrasing).
    intro = intro_for(L, lang)
    who = re.compile(r"(?:أنا\s+)?أحمد\s+حد+ّ?اد[^.؟!\n]*[.؟!]?|(?:I'm|I am)?\s*Ahmad Haddad,?[^.!\n]*[.!]?")
    placed = False
    for i, p_ in enumerate(paras):
        if who.search(p_):
            paras[i] = re.sub(r"\s{2,}", " ", who.sub(" " + intro + " ", p_, count=1)).strip()
            paras[i] = re.sub(r"([.؟!])(?=[^\s])", r"\1 ", paras[i])
            placed = True
            break
    if not placed and paras:
        if len(paras) >= 2:
            paras[1] = intro + " " + paras[1]
        else:  # one paragraph: observation sentence, then our intro, then the rest
            sents = [x for x in re.split(r"(?<=[.؟?!])\s+", paras[0]) if x.strip()]
            paras = [sents[0], " ".join([intro] + sents[1:])]
    # drop any sentence that still name-drops a client
    paras = [" ".join(x for x in re.split(r"(?<=[.؟?!])\s+", p_) if not any(n.lower() in x.lower() for n in ALL_CLIENT_NAMES)).strip() for p_ in paras]
    paras = [p_ for p_ in paras if p_]
    # First message only: an easy, polite way out. Someone who can simply say "no" does not press "spam", the strongest bad signal.
    close = close_for(L, lang, mode) + (" " + opt_out_for(L, lang) if mode == "first" else "")  # one closing paragraph, not two
    text = "\n\n".join(paras + [close])
    # Always one clean greeting: drop whatever greeting-ish lines the model wrote, then add ours.
    ls = text.splitlines()
    while ls and (not ls[0].strip() or len(ls[0]) < 70 and (re.match(r"\s*(dear|hello|hi|good (morning|evening|afternoon)|السادة|الأخوة|الإخوة|مرحب|تحية|السلام|إلى|مساء الخير|صباح الخير)", ls[0], re.I)
                                                          or ls[0].strip().endswith((",", "،")))):
        ls.pop(0)
    text = "\n".join(ls).strip()
    c = (L.get("profile") or {}).get("contact")  # a person whose name is in the email address itself; English only (gender unknown in Arabic)
    first = re.match(r"[A-Za-z]{3,}", c["name"]).group(0).capitalize() if c and re.match(r"[A-Za-z]{3,}", c["name"]) else None
    text = (f"السادة في {short_name(L['name'])} المحترمين،" if lang == "ar" else f"Dear {first}," if first else f"Dear {short_name(L['name'])} team,") + "\n\n" + text
    p = L.get("profile") or {}
    site = SITES.get(p.get("link_pick"), SITES["personal" if L.get("kind") in ("ngo", "org", "school") else "team"])
    if lang == "ar":
        sig = ["أحمد حدّاد", "مخرج ومدير تصوير، FAII HOUSE", f"بعض أعمالي ومن عملت معهم: {site}"]
    else:
        role = team.get("senderRole") or "Director & Cinematographer"
        sig = [name if re.match(r"[A-Za-z]", name) else "Ahmad Haddad", f"{role}, {team.get('company') or 'FAII HOUSE'}", f"Selected work: {site}"]
    return text + "\n\n" + "\n".join(sig)


def translate_ar(text, model=None):
    """Arabic translation of an English draft, shown to Ahmad only (never sent).
    Uses Gemma locally (Qwen sometimes drifts into Chinese). Any non-Arabic script → retry once, then give up silently."""
    if not is_nv(model):
        model = "gemma3:12b" if available("gemma3:12b") else model
    system = "أنت مترجم. ترجم الرسالة التالية إلى العربية الفصحى الواضحة. اكتب الترجمة فقط بالعربية، بدون أي شرح وبدون أي لغة أخرى. أبقِ أسماء الأشخاص والمنظمات والروابط كما هي."
    for _ in range(2):
        ar = complete(model, system, text, temperature=0.1, as_json=False).strip()
        if ar and not re.search(r"[぀-ヿ㐀-鿿가-힯Ѐ-ӿ]", ar):
            return ar
    return ""
