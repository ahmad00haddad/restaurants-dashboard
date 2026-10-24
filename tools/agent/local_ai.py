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
# Free NVIDIA models tried in order when the chosen one fails (tested 2026-10-17 on an Arabic writing task: fast, clean Arabic, valid JSON).
# nemotron-3-ultra was overloaded (503); deepseek-v4.1-flash and gemma-4 timed out; glm-5.3 is good but takes ~2 min, so it is last.
NV_CHAIN = ["nv:nvidia/nemotron-3.5-super-vl-120b-a12b", NV_SMALL, "nv:openai/gpt-oss-20b", "nv:stepfun-ai/step-5-preview", "nv:z-ai/glm-5.3"]


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
        for m in dict.fromkeys([model] + NV_CHAIN):  # the chosen model first, then the other free NVIDIA ones, then local
            if _down.get(m, 0) > time.time():
                continue  # failed recently: don't wait another 2 minutes on it
            try:
                return _nv_chat(m, messages, temperature)
            except Exception as e:
                err = e
                _down[m] = time.time() + 300  # a 503 "overloaded" passes quickly: rest 5 min, not 30
                print(f"{m} failed ({type(e).__name__}) — skipping it for 5 min", flush=True)
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
    return json.loads(m.group(0), strict=False)  # models put raw line breaks inside JSON strings


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


def best_channel(L, p):
    """Outreach goes by email only (Ahmad's rule, 2026-10-13): a lead without an address gets one found (find_emails), never a
    WhatsApp / Instagram message instead. WhatsApp stays for answering people who wrote to us there."""
    return "email"


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
        p["channel"] = "email"
    if p.get("lang") not in ("ar", "en"):
        p["lang"] = "ar"
    if p.get("link_pick") not in ("personal", "team", "behance"):
        p["link_pick"] = "personal" if L.get("kind") in ("ngo", "org", "school") else "team"
    p["analysed_by"] = f"local:{model}"
    if L.get("email"):
        p["email_check"] = emailcheck.check(L["email"])
    p["channel"] = best_channel(L, p)
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
    p["channel"] = best_channel(L, p)
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


REPLY_CATEGORIES = ("interested", "question", "meeting_request", "referral", "not_now", "no_internal_capacity", "no_budget", "not_relevant", "stop_contact",
                    "wrong_person", "auto_reply_support_desk", "auto_reply_generic", "out_of_office", "not_a_reply", "other")
REPLY_SYSTEM = """You study replies to cold outreach sent by Ahmad Haddad, a director / cinematographer in Jordan, so the sending system can improve.
You get OUR last message to this organisation and THEIR reply. Return JSON only:
{"category":"interested|question|meeting_request|referral|not_now|no_internal_capacity|no_budget|not_relevant|stop_contact|wrong_person|auto_reply_support_desk|auto_reply_generic|out_of_office|not_a_reply|other",
"objection":"what stands in the way, using their words, one short line in Arabic (empty if none)",
"lesson":"what this ONE reply shows about WHO we target, WHAT we wrote, or WHICH ADDRESS we used, one line in Arabic. Say 'ربما' when one reply cannot prove it",
"suggestion":"ONE concrete change (a targeting rule, a wording change, how an address is chosen), in Arabic; EMPTY unless the reply itself clearly supports it",
"confidence":0-100}
Definitions:
- interested = they say they like it and want to continue; meeting_request = they ask for a meeting, call or our phone number; question = they ask about price, terms or details.
- referral = they tell us to contact a named person / another desk / colleague (even politely, even with a phone number): the right person is now known.
- not_now = a polite brush-off that commits to nothing ("we will look at your work and contact you if an opportunity comes", "we keep your details"). This is NOT interest.
- no_internal_capacity = they do this work in-house; no_budget = no money; not_relevant = outside their work or sensitive for them (procurement plan, privacy rules).
- auto_reply_support_desk = automatic answer from a donor / supporter / customer-service desk or ticket system (the address reaches the wrong team);
  auto_reply_generic = other automatic acknowledgement, including "we received your message and will reply soon"; out_of_office = away notice.
- not_a_reply = a notification or system mail (Facebook, Hugging Face, Google, newsletters, security alerts) that is not an answer to our message.
- wrong_person = they say to write to someone else AND give no way to reach them; stop_contact = asks not to be contacted again.
Ahmad's fixed decisions: the first email never contains a price or price range (cost is quoted after a meeting and five scoping questions); his phone is given only after
they ask; no client names in a first email; messages are in the language of the organisation's own site. NEVER suggest anything that breaks these.
Judge only what the text says; one reply is an anecdote, not a rule. Never invent facts about them. Write Arabic only (names of tools and organisations may stay Latin);
never use Chinese, Japanese, Russian or any other script."""

REPLY_BAD_SUGGESTION = re.compile(r"سعر|أسعار|باقات|الكلفة|التكلفة|نطاق سعري|price|pricing|رقم (الهاتف|الواتس|جوال)|اسماء العملاء|أسماء العملاء")


def review_reply(model, L, ours, theirs, auto=False):
    """Classify one reply and say what the system should learn. Returns a dict (category always valid) or raises."""
    user = (f"ORGANISATION: {L.get('name')} (type {L.get('kind')}, {L.get('city') or ''})\nAUTOMATIC REPLY FLAG: {auto}\n\n"
            f"OUR LAST MESSAGE:\n{(ours or '(none found)')[:1500]}\n\nTHEIR REPLY:\n{(theirs or '')[:2500]}")
    out = chat(model, REPLY_SYSTEM, user)
    cat = str(out.get("category") or "other").lower()
    try:
        conf = int(out.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0
    stray = re.compile(r"[぀-ヿ㐀-鿿가-힯Ѐ-ӿ]")  # a model slip into another script: such a line is dropped, not shown
    def text(k):
        v = str(out.get(k) or "").strip()
        return None if not v or stray.search(v) else v[:400]
    suggestion = text("suggestion")
    if suggestion and (REPLY_BAD_SUGGESTION.search(suggestion) or conf < 60):
        suggestion = None  # contradicts a decision of Ahmad's, or the model itself is unsure: do not nag with it
    return {"category": cat if cat in REPLY_CATEGORIES else "other", "objection": (text("objection") or None) and text("objection")[:300],
            "lesson": text("lesson"), "suggestion": suggestion, "confidence": conf}


# ---------------- First email to an organisation: fixed template, the idea is chosen in code from a vetted library ----------------
NGO_TOPICS = [  # (key, pattern); the name and category are tested first, then the site text is COUNTED (most matches wins)
    ("disability", r"إعاقة|الاعاقة|معاق|مكفوف|الصم\b|ذوي الاحتياجات|disabilit|blind|deaf|special needs"),
    ("children", r"أيتام|يتيم|طفل|أطفال|children|orphan|kids|\bchild"),
    ("women", r"نساء|المرأة|سيدات|women|female|gender"),
    ("health", r"صحي|صحة|طبي|مستشفى|سرطان|medical|health|clinic|cancer|hospital"),
    ("education", r"تعليم|طلاب|طالب|مدرس|تدريب|educat|student|school|training|scholar|learning"),
    ("youth", r"شباب|youth|young"),
    ("environment", r"بيئ|مياه|مناخ|تدوير|environment|green|climate|recycl|water|wildlife|conservation"),
    ("arts", r"ثقاف|مسرح|تراث|متحف|cultur|\barts?\b|museum|theat|heritage|music|gallery"),
    ("economic", r"ريادة|تمكين اقتصادي|مشاريع صغيرة|entrepreneur|livelihood|microfinance|business development|\bskills\b"),
    ("rights", r"حقوق|ديمقراط|مجتمع مدني|\brights\b|democra|advocacy|civic|governance"),
    ("research", r"أبحاث|بحث علمي|research|science|institute"),
    ("relief", r"لاجئ|إغاثة|خير|زكاة|صدقة|طعام|غزة|refugee|relief|humanitarian|charit|zakat|food bank|gaza|human development"),
]
NGO_IDEAS = {
    "ar": {
        "disability": "يمكننا تصوير فيلم وثائقي قصير يتابع شخصاً استفاد من خدماتكم، يروي قصته بصوته ويُظهر قدراته واستقلاليته.",
        "children": "يمكننا تصوير فيلم وثائقي قصير يتابع يوماً في حياة طفل أو أسرة تدعمونها، بما يحفظ خصوصية الأطفال وكرامتهم.",
        "women": "يمكننا تصوير فيلم وثائقي قصير يتابع امرأة استفادت من برامجكم، يروي رحلتها وأثر هذا الدعم في حياتها وأسرتها بصوتها.",
        "health": "يمكننا تصوير فيلم وثائقي قصير يتابع أحد المستفيدين أو أحد أفراد فريقكم، ويُظهر الجهد الإنساني خلف خدماتكم.",
        "education": "يمكننا تصوير فيلم وثائقي قصير يتابع طالباً أو معلماً في أحد برامجكم، ويُظهر ما يتغيّر في يومه بفضلها.",
        "youth": "يمكننا تصوير فيلم وثائقي قصير يتابع شاباً أو شابة في أحد برامجكم، من أول خطوة حتى ما حققه بعدها.",
        "environment": "يمكننا تصوير فيلم وثائقي قصير يتابع العاملين على أحد مشاريعكم في الميدان، ويُظهر أثر العمل على الأرض.",
        "arts": "يمكننا تصوير فيلم وثائقي قصير يتابع فناناً أو مشاركاً في أحد برامجكم، من التحضير حتى العرض.",
        "economic": "يمكننا تصوير فيلم وثائقي قصير يتابع مشاركاً في أحد برامج التدريب لديكم حتى يطلق مشروعه الصغير.",
        "rights": "يمكننا تصوير فيلم وثائقي قصير يتابع أحد المشاركين في أنشطتكم، ويروي كيف أصبح فاعلاً في مجتمعه.",
        "research": "يمكننا تصوير فيلم وثائقي قصير يتابع باحثاً أو مستفيداً من عملكم، ويُظهر أثر العمل العلمي في الحياة اليومية.",
        "relief": "يمكننا تصوير فيلم وثائقي قصير يتابع أسرة استفادت من برامجكم، ويروي بصوتها ما غيّره هذا الدعم.",
        "general": "يمكننا تصوير فيلم وثائقي قصير يتابع أحد المستفيدين من برامجكم، ويروي أثرها من خلال قصته.",
        "company": "يمكننا تصوير فيلم وثائقي قصير يتابع فريقكم وهو ينجز أحد مشاريعكم، ويُظهر الناس الذين يقفون خلف الخدمة.",
    },
    "en": {
        "disability": "We could film a short documentary following someone who has benefited from your services, telling their own story and showing their abilities and independence.",
        "children": "We could film a short documentary following a day in the life of a child or family you support, with full respect for the children's privacy and dignity.",
        "women": "We could film a short documentary following a woman who has benefited from your programmes, telling in her own voice how this support changed her life and her family's.",
        "health": "We could film a short documentary following one of the people you serve, or a member of your team, showing the human effort behind your services.",
        "education": "We could film a short documentary following a student or a teacher in one of your programmes, showing what changes in their day because of it.",
        "youth": "We could film a short documentary following a young person in one of your programmes, from the first step to what they achieved afterwards.",
        "environment": "We could film a short documentary following the people working on one of your projects in the field, showing the impact on the ground.",
        "arts": "We could film a short documentary following an artist or a participant in one of your programmes, from preparation to the performance.",
        "economic": "We could film a short documentary following a participant in one of your training programmes until they launch their own small business.",
        "rights": "We could film a short documentary following a participant in your activities, telling how they became an active voice in their community.",
        "research": "We could film a short documentary following a researcher or a beneficiary of your work, showing how the research reaches everyday life.",
        "relief": "We could film a short documentary following a family that has benefited from your programmes, telling in their own voice what this support changed.",
        "general": "We could film a short documentary following one of the people your programmes serve, telling their impact through their story.",
        "company": "We could film a short documentary following your team as it delivers one of your projects, showing the people behind the service.",
    },
}
NGO_WORKS = {  # one strong example per topic, chosen in code
    "women": "https://www.behance.net/gallery/126287243/_", "children": "https://www.behance.net/gallery/225987725/_",
    "disability": "https://www.behance.net/gallery/225987725/_", "health": "https://www.behance.net/gallery/225987725/_",
    "youth": "https://www.behance.net/gallery/131010035/-Ezwitti", "education": "https://www.behance.net/gallery/226584981/QRTA",
    "economic": "https://www.behance.net/gallery/206048153/Rajaa-USAID", "relief": "https://www.behance.net/gallery/206048153/Rajaa-USAID",
}
NGO_DEFAULT_WORK = "https://www.behance.net/gallery/226584981/QRTA"
NGO_LEAD = {
    "ar": ["هذا مثال على فيلم صوّرته في مجال قريب من عملكم:", "ومن أعمالي في مجال قريب من عملكم:", "مثال على ما صوّرته في هذا المجال:"],
    "en": ["Here is an example of a film I made in a field close to yours:", "One of my films in a related field:", "An example of what I filmed in this field:"],
}
NGO_REST = {
    "ar": ["وبقية أعمالي في الرابط أدناه، شاهدوها على مهلكم.", "وأعمالي كلها في الرابط أدناه، وأترك لكم الحكم عليها.", "وستجدون بقية أعمالي في الرابط أدناه."],
    "en": ["The rest of my work is at the link below, to look through at your own pace.", "All my work is at the link below. I'll leave it to speak for itself.", "You'll find the rest of my work at the link below."],
}


def ngo_topic(L):
    """What the organisation does, from its name, category and the text of its site; decided by keywords, never by a model."""
    p = L.get("profile") or {}
    text = f"{L.get('name') or ''} {L.get('category') or ''} {(L.get('about') or '')[:1500]} {p.get('summary') or ''}".lower()
    name_text = f"{L.get('name') or ''} {L.get('category') or ''}".lower()
    own_name = (L.get("name") or "").lower()  # the category often says "NGO" even for a business found by an NGO search: judge by the name only
    ngo_like = re.search(r"جمعية|مؤسسة|منظمة|مركز|صندوق|رابطة|اتحاد|association|foundation|society|\bngo\b|charit|fund|cent(er|re)|council|commission|institute|initiative|academy|union|network|group", own_name)
    if re.search(r"\bl\.?l\.?c\b|\bltd\b|\bco\.|\binc\b|شركة|solutions|technolog|consult|software|services", own_name) and not ngo_like:
        return "company"  # a business, not an organisation with beneficiaries
    for key, rx in NGO_TOPICS:  # the name and category decide first
        if re.search(rx, name_text):
            return key
    counts = [(len(re.findall(rx, text)), -i, key) for i, (key, rx) in enumerate(NGO_TOPICS)]
    best = max(counts)
    return best[2] if best[0] >= 3 else "general"  # the site must clearly say it (3+ mentions); otherwise the safe general idea


NGO_HOOK_SYSTEM = """You help a film director write the opening of a first email to ONE organisation, so it shows he really read about them.
From the SOURCE text (their own website and recent news about them) pick ONE concrete, specific thing: a named programme or project,
a recent launch, an event, a figure, a place they work in. Then write:
- "quote": the exact words from SOURCE that contain that thing (copy them character for character, 5 to 25 words).
- "hook": ONE plain sentence in LANG saying that specific thing about them, as a fact (no praise, no "I was impressed", no adjectives
  like inspiring/amazing/رائع/ملهم, no question). It must name the specific programme/project/event/figure.
- "idea": ONE sentence in LANG that MUST start exactly with "IDEA_START" and continues with a short documentary that follows real
  people of THAT SAME programme/project (a participant, a beneficiary, a team member), ending with the change it shows.
  Never invent personal names, numbers or places that are not in SOURCE. No film titles.
In Arabic write every word in Arabic (for "showing" write "ويُظهر"); inside the JSON values use «» for quotation marks, never ".
Return JSON only: {"quote":"...","hook":"...","idea":"..."}. If SOURCE has nothing specific about this organisation, return {"quote":"","hook":"","idea":""}."""
IDEA_START = {"ar": "يمكننا تصوير فيلم وثائقي قصير", "en": "We could film a short documentary"}


def _norm_ws(t):
    return re.sub(r"\s+", " ", re.sub(r"[ً-ْـ«»\"“”'‘’]", "", t or "")).strip().lower()


def org_sources(L):
    """What we can quote about an organisation: its own site text and fresh news that names it."""
    p = L.get("profile") or {}
    parts = [L.get("about") or "", p.get("summary") or ""]
    if len(L.get("about") or "") < 600 and L.get("website"):
        try:
            import find_emails
            parts.append(find_emails.fetch(L["website"] if L["website"].startswith("http") else "https://" + L["website"])[0][:4000])
        except Exception:
            pass
    news = p.get("recent") or []
    if not news:
        try:
            news = fresh(L) or []
        except Exception:
            news = []
    parts += [f"{x.get('title', '')}. {x.get('text', '')}" for x in news]
    return "\n".join(x for x in parts if x).strip()[:7000]


HOOK_WHY = []  # why the last ngo_hook() attempts were rejected (debugging, shown in the failure note)


def ngo_hook(L, lang, model):
    """(hook, idea) about THIS organisation, checked in code: the quote must be in what we read, the hook must name what the quote names,
    the idea must be a short documentary. ('', '') when nothing specific and verifiable was found."""
    src = org_sources(L)
    if len(src) < 80 or not model:
        return "", ""
    lang_name = "Arabic" if lang == "ar" else "English"
    system = NGO_HOOK_SYSTEM.replace("LANG", lang_name).replace("IDEA_START", IDEA_START[lang])
    note = ""
    HOOK_WHY.clear()
    for attempt in range(4):  # the model sometimes leaks a foreign word or paraphrases the quote: ask again, a little warmer, with the reason
        try:
            txt = complete(model, system, f"ORGANISATION: {L.get('name')}\nLANG: {lang_name}{note}\n\nSOURCE:\n{src}", temperature=0.2 + 0.2 * attempt)
            out = json.loads(re.search(r"\{.*\}", txt, re.S).group(0), strict=False)
        except Exception as e:
            HOOK_WHY.append(f"json: {e}")
            continue
        if lang == "ar":  # a model habit: one Spanish/English verb in the middle of Arabic
            for k in ("hook", "idea"):
                out[k] = re.sub(r"(mostrando|showing|demostrando|mientras)", "ويُظهر", str(out.get(k) or ""), flags=re.I)
        bad = foreign_words(str(out.get("hook") or "") + " " + str(out.get("idea") or ""), L) if lang == "ar" else []
        if bad:
            HOOK_WHY.append(f"foreign: {bad[:3]}")
            note = f"\nWrite ONLY in Arabic. Do not use these words: {', '.join(bad[:4])}."
            continue
        quote, hook, idea = (str(out.get(k) or "").strip() for k in ("quote", "hook", "idea"))
        hook, idea = (x if not x or x[-1] in ".؟?!" else x + "." for x in (hook, idea))  # a missing full stop is not a reason to drop it
        if not (quote and hook and idea) or _norm_ws(quote) not in _norm_ws(src):
            HOOK_WHY.append("quote not in source")
            continue  # an invented or paraphrased "fact"
        key = [w for w in re.findall(r"[\w؀-ۿ]{4,}", _norm_ws(quote)) if w not in STOP_HOOK]
        translated = lang == "ar" and len(re.findall(r"[A-Za-z]", quote)) > len(re.findall(r"[؀-ۿ]", quote))
        if not translated and not any(w in _norm_ws(hook) for w in key):  # an English source told in Arabic cannot share words
            HOOK_WHY.append("hook does not name the quote")
            continue  # the hook does not name what the quote says
        if not idea.startswith(IDEA_START[lang]) or not (15 <= len(hook) <= 260) or len(idea) > 320 or hook[-1] not in ".؟?!" or idea[-1] not in ".؟?!":
            HOOK_WHY.append(f"shape: {idea[:40]!r} {len(hook)}/{len(idea)}")
            continue
        if any(n not in src for n in re.findall(r"\d[\d,.]*", hook + " " + idea)):
            HOOK_WHY.append("number not in source")
            continue  # a number that is not in what we read
        if ai_tells(hook + " " + idea) or FLATTERY.search(hook) or (lang == "ar" and foreign_words(hook + " " + idea, L)):
            HOOK_WHY.append("tells/flattery")
            continue
        return hook, idea
    return "", ""


STOP_HOOK = {"that", "this", "with", "from", "their", "they", "have", "will", "which", "about", "jordan", "amman", "الذي", "التي", "هذا", "هذه",
             "على", "إلى", "الى", "عن", "من", "في", "الأردن", "الاردن", "عمان"}


WRITER_EXAMPLES = {  # Ahmad's own first emails (they got replies): the voice the model must imitate, not quote
    "ar": ["""السادة في جمعية نور الخير المحترمين،

جمعية نور الخير تعمل منذ عام 2017 لتوفير الدعم للأسر الفقيرة والأيتام وطلبة العلم.

أنا أحمد حدّاد، مخرج ومدير تصوير من الأردن، أصنع أفلاماً قصيرة عن الناس الذين يقفون خلف البرامج والمبادرات.

يمكننا تصوير فيلم قصير يتابع قصصاً حقيقية لأشخاص استفادوا من برامج الجمعية.

[[WORK]]

ويسعدني أن نلتقي أونلاين لقاءً بسيطاً نتحدث فيه عن الفكرة ونعدّلها بما يناسبكم. وإن لم يكن هذا وقته فلا بأس أبداً، وبالتوفيق لكم.""",
           """السادة في جمعية معهد تضامن النساء الأردني المحترمين،

أنا أحمد حدّاد، مخرج ومدير تصوير من الأردن، أصنع أفلاماً قصيرة عن الناس الذين يقفون خلف البرامج والمبادرات.

يمكننا تصوير فيلم قصير يتابع امرأة استفادت من برامجكم، ويروي رحلتها وأثر هذا الدعم في حياتها وأسرتها بصوتها.

[[WORK]]

إن رأيتم أن الفكرة تناسبكم، يسعدني أن نتحدث عنها في لقاء بسيط أونلاين. وإن لم يكن التوقيت مناسباً فلا بأس، ويعطيكم العافية.""",
           """السادة في مركز عمّان لدراسات حقوق الإنسان المحترمين،

أعلن المركز مؤخراً عن دعوة للتسجيل في دورة «حقوق التضامن» بالشراكة مع الحركة الدولية لحقوق الإنسان في جنيف.

أنا أحمد حدّاد، مخرج ومدير تصوير، وجزء كبير من عملي أفلام وثائقية قصيرة لجهات تعمل في المجتمع.

يمكننا تصوير فيلم قصير يتبع مجموعة من الشباب المشاركين في الدورة ويُظهر كيف يتحولون من متدربين إلى ناشطين.

[[WORK]]

يسعدني أن أسمع رأيكم، ولو في لقاء بسيط أونلاين. وإن لم يكن هذا ما تحتاجونه الآن فلا بأس، وكل التوفيق لكم."""],
    "en": ["""Dear Human Development Fund team,

HDF has served over 5.2 million hot meals in Gaza over three years of continuous emergency response.

I'm Ahmad Haddad, a director and cinematographer in Jordan; for years I've worked with organisations on films that show their impact through people.

We could film a short documentary following the aid workers and families behind those hot meals.

[[WORK]]

I'd be glad to talk it through in a simple online meeting and shape the idea with you. If this isn't a priority right now, that's perfectly fine."""],
}
WRITER_SYSTEM = """You are Ahmad Haddad, a Jordanian documentary director and cinematographer, writing the FIRST email to ONE organisation. Write like a calm, warm
person writing to a stranger he respects, not like a marketer and not like an assistant. You get a VERIFIED FACT (use it, never add other facts), a suggested IDEA, and
EXAMPLES of Ahmad's real emails. Imitate their voice, length and plainness, but do NOT copy their sentences: say it in your own words for THIS organisation.
Rules:
- Order: the greeting line (exactly as GREETING), one plain sentence about their work (from the fact), one sentence on who Ahmad is, the film idea (one or two sentences:
  whom the film follows and what changes for them, tied to the SAME programme as the fact), a line containing ONLY the token [[WORK]], a short invitation to a simple
  online meeting to talk the idea through, and a gentle way out.
- 70 to 130 words in total. Short sentences. No bullet lists, headings, bold, emoji, or dashes used as punctuation.
- No praise or flattery (no impressive, inspiring, رائع, ملهم, نثمّن). No "I hope this finds you well". No "not just X but Y". No dramatic closing line.
- Never mention a price, a client name, a film title, or any number or place that is not in the FACT. Never promise a date.
- The idea is a possibility ("we could film"), never something already happening.
- Vary the wording each time; do not reuse the exact closing lines of the examples.
- Dates and numbers are written in digits, never spelled out. Write the name as أحمد حدّاد (with the shadda) in Arabic.
- Never end the idea with a clause like "ending with how X changes Y"; stop when the idea is told.
- Arabic: every word in Arabic (no Latin words except FAII HOUSE). English: plain, natural English.
- Do not write a signature or any link; they are added for you.
Return JSON only: {"subject":"2 to 5 words naming their specific programme or topic, no 'opportunity', no 'collaboration'","body":"the email"}"""
CRITIC_SYSTEM = """You are a sharp editor who hates text that sounds machine-written. You get an email draft from a Jordanian filmmaker to an organisation. Find any phrase a real
person would not say (stock phrases, inflated words, symmetrical constructions, padding, translated-sounding grammar) and rewrite ONLY those spots plainly.
Keep the facts, the order, the token [[WORK]] on its own line, the greeting line, and the length (70 to 130 words). Add nothing. Same language as the draft.
Return JSON only: {"subject":"same or slightly better","body":"the full email after your edits"}"""
WAY_OUT = re.compile(r"فلا بأس|لا بأس|أتفهّم|أتفهم|بالتوفيق|التوفيق|يعطيكم العافية|no problem|perfectly fine|completely understand|no worries|all the best|wish you well|that's fine", re.I)
MEETING = re.compile(r"أونلاين|اونلاين|عبر الإنترنت|لقاء|اجتماع|مكالمة|online|meeting|call|chat|talk", re.I)
OTHER_SCRIPT = re.compile("[぀-ヿ㐀-鿿가-힯Ѐ-ӿ]")


def work_for(L):
    return NGO_WORKS.get(ngo_topic(L), NGO_DEFAULT_WORK)


def check_human(body, subject, L, lang, src, facts):
    """Why a model-written first email must be rejected (empty list = fine). All deterministic."""
    bad = []
    if body.count("[[WORK]]") != 1:
        bad.append("the token [[WORK]] must appear exactly once on its own line")
    plain = body.replace("[[WORK]]", " ")
    n = len(re.findall(r"\w+", plain))
    if not 55 <= n <= 160:
        bad.append(f"length {n} words, need 70 to 130")
    if re.search(r"https?://|www\.|\*\*|^#|^\s*[-•]\s", plain, re.M):
        bad.append("no links or markdown")
    if ai_tells(plain) or FLATTERY.search(plain):
        bad.append("machine-sounding or flattering phrase")
    if lang == "ar" and foreign_words(plain, L):
        bad.append("Latin words in Arabic: " + ",".join(foreign_words(plain, L)[:3]))
    if OTHER_SCRIPT.search(plain):
        bad.append("another script slipped in")
    if wrong_proof(L, plain):
        bad.append("a client name")
    if any(x not in src + facts for x in re.findall(r"\d[\d,.]*", plain)):
        bad.append("a number not in the fact")
    if re.search(r"سعر|تكلفة|كلفة|\$|دينار|price|cost|fee", plain, re.I):
        bad.append("a price word")
    if not WAY_OUT.search(plain) or not MEETING.search(plain):
        bad.append("needs the online meeting invitation and a gentle way out")
    if not (2 <= len(re.findall(r"\w+", subject)) <= 7) or re.search(r"opportunity|collaborat|فرصة|تعاون", subject, re.I):
        bad.append("subject must be 2 to 5 words about their programme")
    qa = qa_flags(plain + "\n\nx", L)
    if qa:
        bad.append(qa[0])
    return bad


WRITER_WHY = []  # why the last model-written drafts were rejected (debugging)


def human_first(L, team, lang, hook, idea, model):
    """A model writes the whole first email in Ahmad's voice from his real emails, a second pass removes machine-sounding spots, and code
    rejects anything with a foreign word, an invented number, a price, a client name, or the wrong shape. None = use the fixed template."""
    if not model:
        return None
    src = org_sources(L)
    facts = hook + " " + idea
    greeting = f"السادة في {short_name(L['name'])} المحترمين،" if lang == "ar" else f"Dear {short_name(L['name'])} team,"
    ex = "\n\n=====\n\n".join(WRITER_EXAMPLES["ar" if lang == "ar" else "en"])
    user = (f"GREETING: {greeting}\nORGANISATION: {L.get('name')}\nVERIFIED FACT ABOUT THEM: {hook}\n"
            f"SUGGESTED IDEA (rephrase, keep its meaning): {idea}\n\nEXAMPLES OF AHMAD'S REAL EMAILS:\n\n{ex}")
    WRITER_WHY.clear()
    for attempt in range(3):
        try:
            note = ("\n\nYour previous attempt was rejected: " + WRITER_WHY[-1] + ". Fix that.") if WRITER_WHY else ""
            out = chat(model, WRITER_SYSTEM, user + note)
            body, subject = str(out.get("body") or "").strip(), str(out.get("subject") or "").strip()
            try:  # second pass: remove what still sounds machine-written
                ed = chat(model, CRITIC_SYSTEM, f"SUBJECT: {subject}\nDRAFT:\n{body}")
                if isinstance(ed.get("body"), str) and "[[WORK]]" in ed["body"]:
                    body, subject = ed["body"].strip(), str(ed.get("subject") or subject).strip()
            except Exception:
                pass
            body = re.sub(r"\s*—\s*|\s+–\s+", "، " if lang == "ar" else ", ", body)
            if lang == "ar":
                body = body.replace("حدّاد", "حداد").replace("حداد", "حدّاد")
            body = re.sub(r"^\s*(السادة|Dear)[^\n]*\n+", "", body).strip()  # our own greeting replaces whatever greeting it wrote
            why = check_human(body, subject, L, lang, src, facts)
            if why:
                WRITER_WHY.append("; ".join(why))
                continue
            return subject, greeting + "\n\n" + body
        except Exception as e:
            WRITER_WHY.append(f"error {type(e).__name__}")
    return None


def ngo_first(L, team, model=None):
    """First email to an organisation: a specific fact about THEM (read from their site / recent news, verified in code), who I am,
    a short documentary built on that same fact. Written by a model in Ahmad's voice from his real emails and checked in code; if the
    model cannot produce a clean draft, the fixed template is used. No verified fact = no email (never a generic template)."""
    import hashlib
    lang = lang_for(L)
    lang = "ar" if lang == "ar" else "en"
    h = int(hashlib.md5(("nb" + str(L.get("id") or L.get("name"))).encode()).hexdigest(), 16)
    hook, idea = ngo_hook(L, lang, model)
    if not hook:
        raise ValueError("لم أجد معلومة محددة وموثّقة عن المنظمة في موقعها أو أخبارها: لن أرسل رسالة عامة. أضف موقعهم أو اكتب توجيهاً.")
    made = human_first(L, team, lang, hook, idea, model)
    if made:
        subject, text = made
        site = SITES["personal"]
        sig = (["أحمد حدّاد", "مخرج ومدير تصوير، FAII HOUSE", f"بعض أعمالي ومن عملت معهم: {site}"] if lang == "ar" else
               ["Ahmad Haddad", f"{team.get('senderRole') or 'Director & Cinematographer'}, {team.get('company') or 'FAII HOUSE'}", f"Selected work: {site}"])
        return subject, text.replace("[[WORK]]", NGO_LEAD[lang][h % 3] + "\n" + work_for(L)) + "\n\n" + "\n".join(sig)
    body = hook + "\n\n" + intro_for(L, lang) + "\n\n" + idea + "\n\n" + NGO_REST[lang][h % 3]
    subject = f"عن عمل {short_name(L['name'])}" if lang == "ar" else f"On the work of {short_name(L['name'])}"
    return subject, finish(body, L, team, lang, "first")


def roastery_first(L, team):
    """First email to a coffee roastery: one line about me, ONE strong example, the portfolio link. Fixed template, no model."""
    import hashlib
    h = int(hashlib.md5(("rb" + str(L.get("id") or L.get("name"))).encode()).hexdigest(), 16)
    body = intro_for(L, "ar") + "\n\n" + SCHOOL_REST[h % len(SCHOOL_REST)]
    paras = finish(body, L, team, "ar", "first").split("\n\n")
    paras.insert(len(paras) - 3, f"{ROAST_BODY[(h >> 4) % len(ROAST_BODY)]}\n{ROAST_WORKS}")
    return f"محتوى مرئي: {short_name(L['name'])}", "\n\n".join(paras)


# ---------------- How Ahmad answers a reply (learned from his own edits of the Civil Party and Nour Al-Khair replies) ----------------
REPLY_WORKS = {
    "social": ("https://www.behance.net/gallery/240973859/_", "يوجد به عدة فيديوهات قصيرة مناسبة لوسائل التواصل."),
    "long": ("https://www.behance.net/gallery/226584981/QRTA", "فيلم QRTA الطويل:"),
    "women": ("https://www.behance.net/gallery/206048153/Rajaa-USAID", "فيلم رجاء:"),
}


INTERNATIONAL_NAME = re.compile(r"international|global|united nations|\bUN\b|\bUN[A-Z]+\b|USAID|embassy|european|\bEU\b|world |oxfam|red cross|red crescent|rescue|mercy corps|care |save the children", re.I)
LOCAL_KINDS = {"school", "pharmacy", "roastery", "restaurant", "brand", "hotel", "event"}


def is_local(L):
    """Local first: an Arabic name, an Arabic-language profile, a .jo address, or a local business; never a big international body."""
    name = L.get("name") or ""
    arabic = bool(re.search("[؀-ۿ]", name))
    if not arabic and L.get("kind") in ("ngo", "org") and INTERNATIONAL_NAME.search(name):
        return False
    if arabic or (L.get("profile") or {}).get("lang") == "ar" or re.search(r"\.jo(/|$)", (L.get("website") or "") + "/") or (L.get("email") or "").lower().endswith(".jo"):
        return True
    return L.get("kind") in LOCAL_KINDS


def scoping_questions(women):
    """Ahmad's five questions that speed the process up (duration, who/which programme, where it is shown, translation, delivery date)."""
    q2 = "عدد النساء اللواتي ستُروى قصصهنّ، وهل هنّ في عمّان أم في أكثر من محافظة؟" if women else "أي برنامج من برامجكم تودّون إبرازه"
    return ("1. مدة الفيلم التي تتصورونها (من ثلاث إلى خمس دقائق، أم أطول؟)\n"
            f"2. {q2}\n3. أين سيُعرض الفيلم: وسائل التواصل، أم فعاليات الجهة، أم جهات داعمة؟\n"
            "4. هل تحتاجون ترجمة أو نسخة بلغتين للفيلم؟\n5. الموعد الذي تريدونه لتسليم الفيلم.")


def phone_reply(L, theirs, wa):
    """They asked for his number (to call or to set a meeting): give it, ask THEM to call (he never calls first), and list what he
    wants to know in the conversation so it is short and useful. Fixed text, no model."""
    t = f"{theirs}\n{L.get('name') or ''}"
    salam = bool(re.search(r"السلام عليكم", theirs or "")) or bool(re.search(r"جمعية|خير|إغاثة|الاغاثة|zakat|charity|islamic", t, re.I))
    women = bool(re.search(r"نساء|المرأة|النساء|women", t, re.I))
    return "\n\n".join([
        "السلام عليكم ورحمة الله وبركاته،" if salam else "تحية طيبة،",
        f"السادة في {short_name(L['name'])} المحترمين،",
        "شكراً لردّكم، ويسعدني التعاون معكم.",
        f"رقمي {wa} (واتساب أيضاً)، ويسعدني أن تتصلوا بي في الوقت الذي يناسبكم.",
        "ولتكون المكالمة قصيرة ومفيدة، سأحتاج أن أعرف منكم في أثنائها (أو قبلها كتابةً إن تيسّر):\n\n" + scoping_questions(women),
        "ثم أرسل لكم عرضاً مفصّلاً بالكلفة خلال يوم إلى يومي عمل، لأن الكلفة تتحدد بحسب الفيلم نفسه.",
        "مع خالص التقدير،\nأحمد حدّاد"])


def reply_playbook(L, theirs, price_asked):
    """The answer to an interested reply (a price question or a request to meet), in Ahmad's own manner:
    greet like they did, thank, a quick online meeting, one concrete commitment if they raised a concern, five scoping questions,
    a quote within a day or two AFTER those answers (never a price in writing), two relevant works with a line each,
    WhatsApp, and his name only. Fixed text: no model, nothing invented."""
    t = f"{theirs}\n{L.get('name') or ''}"
    salam = bool(re.search(r"السلام عليكم", theirs or "")) or bool(re.search(r"جمعية|خير|إغاثة|الاغاثة|zakat|charity|islamic", t, re.I))
    women = bool(re.search(r"نساء|المرأة|النساء|women", t, re.I))
    lines = ["السلام عليكم ورحمة الله وبركاته،" if salam else "تحية طيبة،",
             f"السادة في {short_name(L['name'])} المحترمين،",
             "شكراً لردّكم الكريم واهتمامكم." + (" وقبل أن أتحدث عن الكلفة، أحتاج أن أفهم الفيلم نفسه." if price_asked else " ويسعدني أن نحدد معاً الفيلم الذي يناسبكم."),
             "يسعدني عقد اجتماع بسيط وسريع أونلاين لمناقشة الفيلم معاً، بحسب ما يناسبكم، وأتكيّف مع الموعد الذي تختارونه."]
    if re.search(r"خصوصي|كرام", theirs or ""):
        lines.append("وما أشرتم إليه من خصوصية المستفيدين وكرامتهم أمر أراعيه في هذا النوع من الأفلام: لا يُصوَّر أحد دون موافقته الواضحة، وصاحب القصة هو من يقرر ما يظهر منها.")
    lines.append("ولتكون الجلسة مفيدة، سأكون شاكراً إن أخبرتموني قبلها:\n\n" + scoping_questions(women))
    lines.append("ثم أرسل لكم عرضاً مفصّلاً بالكلفة خلال يوم إلى يومي عمل، لأن الكلفة تتحدد بحسب الفيلم نفسه.")
    works = (["women"] if women else []) + ["social", "long"]
    block = "ومن أقرب الأعمال السابقة في هذا الخط:\n\n" + "\n\n".join(
        (f"{REPLY_WORKS[k][1]}\n{REPLY_WORKS[k][0]}" if k != "social" else f"{REPLY_WORKS[k][0]}\n{REPLY_WORKS[k][1]}") for k in works)
    lines.append(block)
    lines.append("يسعدني أن أحدد معكم موعداً يناسبكم هذا الأسبوع.")
    return "\n\n".join(lines)


LAST_REVIEW = {"issues": []}  # read by the agent right after write(): shown on the approval card, never sent


PROOF_SYSTEM = """You are a meticulous native {lang_name} copy editor. You receive a short first-contact email from Ahmad Haddad, a Jordanian film
director, to an organisation, plus the CLIENT TEXT the facts must come from. Fix ONLY real mistakes and return the corrected email.
Fix: grammar and agreement (verb gender, case endings, plural/singular), calques and passive 'تم ...' constructions, broken or garbled words
(a stray letter before a Latin word), a name transliterated into Arabic letters when its real Arabic or Latin name exists (use the Arabic name
the client uses, or keep the Latin name), a sentence with no verb, an address or phone number or menu text pasted into the body, a sentence
whose subject is wrong (e.g. 'we implement the client's programme' when the CLIENT implements it), word repetitions and duplicate sentences,
mixed languages (the whole email in one language), awkward or funny wording.
Forbidden: adding any fact, number, name, place or claim that is not in the CLIENT TEXT; removing the film idea; making the idea a certainty
(it stays a possibility: 'يمكننا' / 'we could'); changing the greeting line, the signature lines, or any link; adding praise words or exclamation marks.
If a sentence states a specific scene or detail that the CLIENT TEXT does not support (a named factory, a city, a number), rewrite it generically.
Keep the length similar. If nothing needs fixing return the text unchanged.
Return JSON only: {"body":"the corrected full email","issues":["short Arabic note per fix"]}"""


def proofread(model, L, subject, body, lang):
    """A second model pass over a finished draft (found by reading 89 sent emails: garbled words, wrong subjects, invented details).
    The result is accepted only when links, greeting and signature are untouched and no new Latin words appear."""
    try:
        out = chat(model, PROOF_SYSTEM.replace("{lang_name}", "Arabic" if lang == "ar" else "English"),
                   f"CLIENT TEXT (the only source of facts):\n{(L.get('about') or '')[:2500]}\n{json.dumps(L.get('profile') or {}, ensure_ascii=False)[:1200]}\n\nEMAIL:\n{body}")
    except Exception:
        return subject, body, []
    new, issues = out.get("body"), [str(i)[:140] for i in (out.get("issues") or [])][:6]
    if not isinstance(new, str) or new.strip() == body.strip():
        return subject, body, []
    old_l, new_l = [x.strip() for x in body.strip().splitlines() if x.strip()], [x.strip() for x in new.strip().splitlines() if x.strip()]
    ok = (old_l[0] == new_l[0] and old_l[-3:] == new_l[-3:]                                   # greeting and signature untouched
          and sorted(re.findall(r"https?://\S+", body)) == sorted(re.findall(r"https?://\S+", new))   # links untouched
          and 0.7 <= len(new) / max(1, len(body)) <= 1.2
          and not (set(re.findall(r"[A-Za-z]{4,}", new.lower())) - set(re.findall(r"[A-Za-z]{4,}", body.lower())) - ALLOWED_LATIN))  # no new Latin words
    LAST_REVIEW["issues"] = issues  # even when the model could not fix them, the person who approves sees what it noticed
    return (subject, new.strip(), issues) if ok else (subject, body, issues)


ALLOWED_LATIN = {"faii", "house", "behance", "qrta", "usaid", "whatsapp", "unicef", "undp", "unhcr", "instagram", "youtube", "online", "email", "http", "https"}


def foreign_words(body, L):
    """Latin words inside an Arabic message that are not part of the client's own name (models sometimes leak words of other languages:
    'organizzata', 'mostrando' were found in sent emails). English-majority messages are not checked."""
    text = re.sub(r"https?://\S+", " ", body or "")
    toks = re.findall(r"[A-Za-z]{4,}", text)  # hyphenated names split into their parts, like the name tokens below
    if len(re.findall(r"[؀-ۿ]+", text)) < len(toks):
        return []
    allowed = ALLOWED_LATIN | {w.lower() for w in re.findall(r"[A-Za-z]{3,}", f"{L.get('name') or ''} {L.get('category') or ''}")}
    return sorted({t for t in toks if t.lower() not in allowed and not t.isupper()})  # ALL-CAPS tokens are acronyms (UNFPA, BPWA), not stray words


def qa_flags(body, L):
    """Deterministic checks for the writing mistakes found in the agent's drafts. Returns short Arabic reasons (empty = nothing found)."""
    out = []
    paras = [p_.strip() for p_ in (body or "").split("\n\n") if p_.strip()]
    text = "\n\n".join(paras[:-1]) if paras else ""  # without the signature block
    if re.search(r"(?<![؀-ۿ])[؀-ۿ] [A-Za-z]{3,}", text):
        out.append("كلمة مقطوعة أو مشوّهة (حرف عربي وحيد قبل كلمة لاتينية)")
    for p_ in paras[1:-1]:
        if re.search(r"(شارع|منطقة|P\.?O\.? ?Box|ص\.ب|Street)", p_) and len(re.findall(r"\s[-–]\s", p_)) >= 2:
            out.append("فقرة تبدو عنواناً منسوخاً من موقعهم وليست جملة")
        if len(p_) < 120 and not re.search(r"[.؟?!:،,]$|https?://|^\d\.", p_) and not p_.startswith(("السادة", "Dear", "أحمد", "Ahmad")):
            out.append("فقرة مقطوعة بلا نهاية")
    first = paras[1] if len(paras) > 1 else ""
    if re.match(r"\s*(ننفّذ|نقدّم|نقدم|نعمل|نوفّر|نوفر|نطلق|أطلقنا|نحن)\b", first):
        out.append("الجملة الأولى تنسب عمل الجهة إلينا (يبدو أن الكاتب خلط بين «نحن» و«هم»)")
    if re.search(r"(مخرج ومدير تصوير)[^\n]{0,40}\1", text):
        out.append("تكرار «مخرج ومدير تصوير» في نفس الفقرة")
    if re.search(r"\b(تم|تمّ) (إنشاء|انشاء|تنفيذ|إطلاق|اطلاق|تقديم)", text):
        out.append("صيغة مبنية للمجهول مترجمة حرفياً («تم …»)")
    return list(dict.fromkeys(out))


PHONE_ASK = re.compile(r"رقم (هاتف|جوال|الهاتف|الجوال|تلفون)|رقمك|هاتفك|جوالك|ارسل لي رقم|أرسل لي رقم|اتصل بك|للاتصال بك|phone number|your number|call you|give you a call", re.I)


def last_inbound(history):
    """The newest 'THEM' message in the conversation text the agent builds ('[THEM · email · date]\\n...')."""
    parts = re.split(r"\n\n(?=\[(?:THEM|US) ·)", history or "")
    them = [p for p in parts if p.startswith("[THEM")]
    return re.sub(r"^\[THEM[^\]]*\]\n?", "", them[-1]).strip() if them else ""


def dm_version(text):
    """WhatsApp / Instagram: 2-3 short lines. The email template without the 'rest of my work' paragraph, the close and the signature
    block; only the portfolio link line stays."""
    paras = [p for p in text.split("\n\n") if p.strip()]
    link = paras[-1].splitlines()[-1]
    keep = paras[:-1]
    keep = [p for p in keep if not re.search(r"الرابط أدناه|link below|يسعدني|يسرّني|glad|happy to|welcome a conversation", p)]
    keep = [p for p in keep if p.splitlines()[0] != paras[-1].splitlines()[0]]
    return "\n\n".join(keep + [link])


FREE_ASK = re.compile(r"مجان|ببلاش|تبرع|تطوع|بدون مقابل|مقابل (نقود|مادي|أجر|اجر|مبلغ)|بأجر|باجر|for free|free of charge|pro bono|volunteer", re.I)
# Ahmad's own answer to "is it free or paid?", as he wrote it to Al-Gharaa on 2026-10-17: paid, why, what it brings them, and only if they have a budget.
FREE_ANSWER = ("تحية طيبة وبعد،\n\n"
               "أود التوضيح أن هذا العمل يتم تنفيذه عبر فريق إنتاج وصناعة أفلام متخصص وبمعايير احترافية عالية، وبالتالي يتطلب تكاليف إنتاجية وتغطية لنفقات الفريق والتجهيزات.\n\n"
               "الهدف من طرح الفكرة هو تقديم محتوى وثائقي سينمائي يبرز الأثر الإنساني الكبير لجهودكم والمبادرات التي تقدمونها، بطريقة مؤثرة تخدم أهداف الجمعية وتساعد في تسليط الضوء على قصص النجاح والمستفيدين.\n\n"
               "في حال كان لدى الجمعية ميزانية مخصصة للإنتاج الإعلامي أو التوثيق الميداني، يسعدني جداً التنسيق معكم لمناقشة التفاصيل والتكلفة التقديرية للعمل بما يتناسب مع تطلعاتكم.\n\n"
               "وافر الاحترام والتقدير،\nأحمد حداد\nمخرج ومدير تصوير | FAII HOUSE")


# ---------------- «ناس إربد»: sponsors of the documentary (own voice, own checks) ----------------
NAS_SITE = "https://nas-irbid.lovable.app"
NAS_PHONE = "0799256345"
NAS_SYSTEM = """You are Ahmad Haddad, from Irbid, maker of the documentary «ناس إربد», writing ONE short email in Arabic to a person or institution tied to Irbid, to ask them to support the programme.
Facts about the programme (the ONLY facts you may state): a documentary series recording Irbid's living memory (crafts, cafés, families, places that are disappearing); 11 episodes, 2.5 مليون مشاهدة;
independent, no politics; a new season of 8 episodes is being prepared; the archive is open to researchers.
Rules:
- You get GREETING, WHO, LOVE (their real tie to Irbid), EPISODE (one episode with its views) and ASK. Use only those and the programme facts. Invent nothing: no numbers, names, dates, partners.
- Paragraph 1 (1-2 sentences): their real tie to Irbid, taken from LOVE/WHO, said plainly and respectfully. No praise or flattery words (رائع، مذهل، ملهم، نثمّن), no guessing their feelings.
- Paragraph 2 (2 sentences): what «ناس إربد» is, and that the episode named in EPISODE reached that many views, so people of Irbid do watch their own city. Name the episode exactly as given.
- Paragraph 3 (1-2 sentences): the ASK in plain words ("نبحث عن شريك من أهل إربد يرعى حلقة من موسمنا القادم"). No amounts, prices or packages. Then one line inviting a short online meeting or a reply, and a gentle way out ("وإن لم يكن التوقيت مناسباً فلا بأس").
- 80 to 130 words in total. Short plain sentences. No bullets, bold, emoji, exclamation marks, dashes as punctuation, no "ليس مجرد… بل", no inflated words (رحلة، محوري، عميق).
- Arabic only. Do not write the greeting, the link or the signature: they are added for you.
Return JSON only: {"subject":"2 to 5 words naming Irbid or the episode; never رعاية or طلب دعم or فرصة","body":"paragraphs separated by a blank line"}"""
NAS_FOLLOWUP = """You are Ahmad Haddad, maker of «ناس إربد». They did not answer our first email, which is fine. Write ONE very short Arabic note (2 sentences) that adds something: a new reason Irbid's people watch the series
(use only EPISODE and the programme facts), then leave the door open without pressure. No reminder words ("أتابع", "للتذكير"), no thanks in advance, no price. Arabic only.
Return JSON only: {"subject":"Re: same subject","body":"the two sentences"}"""


def nas_first(L, model, mode="first", subject_prev=None):
    n = ((L.get("profile") or {}).get("nas")) or {}
    if not n.get("love") or not n.get("episode"):
        raise ValueError("ناس إربد: لا توجد بيانات (ما يحبه وحلقة مناسبة) لهذا العميل")
    facts = f"GREETING: {n.get('greeting')}\nWHO: {n.get('who')}\nLOVE: {n.get('love')}\nEPISODE: {n['episode']}\nASK: {n.get('ask')}"
    ep = re.sub(r"\s*\(.*", "", n["episode"]).strip()
    last = "no attempt"
    for attempt in range(3):
        out = chat(model, NAS_FOLLOWUP if mode == "followup" else NAS_SYSTEM, facts + ("\nWrite it differently from earlier attempts." if attempt else ""))
        body = str(out.get("body") or "").strip()
        words = len(body.split())
        if mode == "first" and not (60 <= words <= 150):
            last = f"{words} words"; continue
        if ep not in body:
            last = "episode not named"; continue
        if re.search(r"https?://|\d+\s*(د\.?أ|دينار)|[A-Za-z]{4,}", body) or ai_tells(body):
            last = "link, price, Latin word or machine tell"; continue
        subject = str(out.get("subject") or "").strip() or "إربد وناسها"
        if re.search(r"رعاية|طلب دعم|فرصة|collaborat", subject):
            subject = "إربد وناسها"
        if mode == "followup":
            return subject_prev or subject, f"{n.get('greeting')}،\n\n{body}\n\nأحمد حدّاد\nصانع «ناس إربد»\n{NAS_PHONE}\n{NAS_SITE}"
        return subject, (f"{n.get('greeting')}، تحية طيبة\n\n{body}\n\nحلقات البرنامج كلها هنا:\n{NAS_SITE}\n\n"
                         f"أحمد حدّاد\nصانع «ناس إربد»\n{NAS_PHONE}")
    raise ValueError(f"ناس إربد: لم تنجح الكتابة بعد 3 محاولات ({last})")


def write(L, team, history, channel, mode, hint, model):
    """Write, and retry once if the model skipped the idea or cleanup left too little (never queue a hollow message)."""
    if L.get("program") == "nas":
        if mode == "reply":
            raise ValueError("ناس إربد: الرد على الرعاة (أرقام وأسعار) تكتبه أنت من صفحة العميل")
        subject, text = nas_first(L, model, mode)
        return subject, (text if channel == "email" else dm_version(text))
    if mode == "reply":
        theirs = last_inbound(history)
        try:
            cat = review_reply(model, L, "", theirs)["category"] if theirs else "other"
        except Exception:
            cat = "other"
        wa_ = os.environ.get("WHATSAPP_NUMBER", "").strip()
        if theirs and PHONE_ASK.search(theirs) and wa_:  # they asked for his number: give it + the questions that speed the process up
            body = phone_reply(L, theirs, wa_)
            return "رقم التواصل", (body if channel == "email" else dm_version(body))
        if theirs and FREE_ASK.search(theirs):  # "free / donation, or paid?" gets Ahmad's own answer (Al-Gharaa, 2026-10-17)
            return "عن كلفة العمل", (FREE_ANSWER if channel == "email" else dm_version(FREE_ANSWER))
        if cat in ("question", "meeting_request", "interested", "referral"):  # an interested reply gets Ahmad's own playbook, not a model's guess
            wa = os.environ.get("WHATSAPP_NUMBER", "").strip()
            price = bool(re.search(r"تكلف|سعر|كلفة|أسعار|مجان|ببلاش|تبرع|تطوع|مقابل|نقود|فلوس|مصاري|cost|price|quot|budget|free|fee|paid", theirs, re.I))
            body = reply_playbook(L, theirs, price) + "\n\n" + (f"واتساب : {wa}\n\n" if wa else "") + "مع خالص التقدير،\nأحمد حدّاد"
            return ("الكلفة وموعد اللقاء" if price else "موعد اللقاء"), (body if channel == "email" else dm_version(body))
    if mode == "first" and sector(L) in ("roastery", "pharmacy", "education", "ngo"):
        subject, text = (ngo_first(L, team, model) if sector(L) == "ngo" else
                         {"roastery": roastery_first, "pharmacy": pharmacy_first, "education": school_first}[sector(L)](L, team))
        return subject, (text if channel == "email" else dm_version(text))
    last = None
    for attempt in range(2):
        try:
            subject, final = _write_once(L, team, history, channel, mode,
                                         hint if attempt == 0 else ((hint or "") + " The idea sentence is mandatory: say plainly what short film we could shoot for them."), model)
            core = " ".join(final.split("\n\n")[1:-2])
            tells = ai_tells(final) + (["كلمات أجنبية داخل رسالة عربية: " + ", ".join(foreign_words(final, L)[:4])] if foreign_words(final, L) else [])
            if (mode != "first" or OFFER.search(core)) and (not tells or attempt == 1):
                try:  # a second model proofreads the finished draft before it reaches Telegram
                    LAST_REVIEW["issues"] = []
                    subject, final, fixes = proofread(model, L, subject, final, lang_for(L))
                    if fixes:
                        print("  ✎ proofread:", "; ".join(fixes)[:200], flush=True)
                except Exception:
                    pass
                return subject, final  # tells that survive a second try are caught by the send gate, never sent silently
            last = ValueError("the message has no clear film idea" if not tells else "reads machine-written: " + ", ".join(tells))
            if tells:
                hint = (hint or "") + " Write it plainly, like a person: no 'not just X but Y', no dramatic closing line, no inflated words. Use ONLY the message's own language: no words from any other language."
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
    for own in {(L or {}).get("name") or "", short_name((L or {}).get("name") or "")}:  # the client's own name is not name-dropping ("UNICEF Jordan")
        if own:
            body = re.sub(re.escape(own), " ", body, flags=re.I)
    # whole words only (an optional one-letter Arabic prefix is allowed): "عرفة" must not match inside "معرفة"
    return [n for n in ALL_CLIENT_NAMES if re.search(r"(?<!\w)[وبلكف]?" + re.escape(n.lower()) + r"(?!\w)", body.lower())]



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
    name = re.sub(r"\.(org|com|net|jo|edu)\b", "", name or "", flags=re.I)  # "ACHR.ORG" reads as a web address in a greeting
    if "|" in name:  # "Cultures Village | قرية الثقافات|CVskills|KidsMBA": one brand per segment, greet the Arabic one (else the first)
        parts = [x.strip() for x in name.split("|") if x.strip()]
        name = next((x for x in parts if re.search("[؀-ۿ]", x)), parts[0] if parts else name)
    name = re.sub(r"[‎‏_]+", " ", name)  # invisible direction marks and underscores in Google names ("FOCCEC_سواعد التغيير_ Amman")
    acr = re.search(r"\(([A-Za-z]{2,8})\)", name)
    if acr:
        return acr.group(1) + (" Jordan" if "jordan" in name.lower() else "")
    name = re.sub(r"\s*\([^)]{12,}\)", "", name)  # a long parenthetical is the name in a second language
    out = re.sub(r"\s+[-–|]\s+[^-–|]*$", "", name).strip() or name
    out = re.sub(r"\s+(country\s+|regional\s+)?office$", "", out, flags=re.I).strip() or out  # "Mercy Corps Jordan Office" → "Mercy Corps Jordan"
    if re.search(r"[؀-ۿ]", out):  # an Arabic greeting keeps the Arabic part: "FOCCEC سواعد التغيير Amman" → "سواعد التغيير"
        ar = re.findall(r"[؀-ۿ][؀-ۿ\s]*[؀-ۿ]", out)
        if ar and len(re.findall(r"[A-Za-z]{3,}", out)) <= 3:
            out = max(ar, key=len).strip()
    return re.sub(r"\s{2,}", " ", out)


GENERIC_FIRST = {"office", "team", "info", "contact", "admin", "support", "media", "press", "communications", "hello", "mail", "sales", "service", "enquiries"}


def _dedupe_sentences(paras):
    """Drop a sentence that repeats an earlier one (the writer's own intro surviving next to ours: 'I make short films about the people
    behind programmes… I make short films about the people behind programmes…')."""
    seen, out = [], []
    for p_ in paras:
        keep = []
        for s_ in [x for x in re.split(r"(?<=[.؟?!])\s+", p_) if x.strip()]:
            w = set(re.findall(r"\w{3,}", s_.lower()))
            if w and any(len(w & o) / max(1, min(len(w), len(o))) >= 0.7 and min(len(w), len(o)) >= 4 for o in seen):
                continue
            seen.append(w)
            keep.append(s_)
        if keep:
            out.append(" ".join(keep))
    return out


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
    placed = mode != "first"  # the "I am Ahmad Haddad" introduction belongs to the FIRST message only; a reply or follow-up keeps its own words
    for i, p_ in enumerate(paras if mode == "first" else []):
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
    paras = _dedupe_sentences([p_ for p_ in paras if p_])
    # First message only: an easy, polite way out. Someone who can simply say "no" does not press "spam", the strongest bad signal.
    close = close_for(L, lang, mode) + (" " + opt_out_for(L, lang) if mode == "first" else "")  # one closing paragraph, not two
    text = "\n\n".join(paras + ([] if mode == "reply" else [close]))  # a reply ends in its own words, not a stock close
    # Always one clean greeting: drop whatever greeting-ish lines the model wrote, then add ours.
    ls = text.splitlines()
    while ls and (not ls[0].strip() or len(ls[0]) < 140 and (re.match(r"\s*(dear|hello|hi|good (morning|evening|afternoon)|السادة|الأخوة|الإخوة|مرحب|تحية|السلام|إلى|مساء الخير|صباح الخير)", ls[0], re.I)
                                                          or ls[0].strip().endswith((",", "،")))):
        ls.pop(0)
    text = "\n".join(ls).strip()
    c = (L.get("profile") or {}).get("contact")  # a person whose name is in the email address itself; English only (gender unknown in Arabic)
    first = re.match(r"[A-Za-z]{3,}", c["name"]).group(0).capitalize() if c and re.match(r"[A-Za-z]{3,}", c["name"]) else None
    if first and first.lower() in GENERIC_FIRST:
        first = None  # "Hi Office team": a desk is not a person's first name
    text = (f"السادة في {short_name(L['name'])} المحترمين،" if lang == "ar" else f"Dear {first}," if first else f"Dear {short_name(L['name'])} team,") + "\n\n" + text
    p = L.get("profile") or {}
    site = SITES.get(p.get("link_pick"), SITES["personal" if L.get("kind") in ("ngo", "org", "school") else "team"])
    if mode == "reply":  # Ahmad's own replies end: WhatsApp line, a short closing, his name only (no title, company or site link)
        wa = os.environ.get("WHATSAPP_NUMBER", "").strip()
        wa_line = (f"واتساب : {wa}" if lang == "ar" else f"WhatsApp: {wa}") if wa else ""
        sig = ["مع خالص التقدير،", "أحمد حدّاد"] if lang == "ar" else ["Best regards,", "Ahmad Haddad"]
        return text + "\n\n" + ((wa_line + "\n\n") if wa_line else "") + "\n".join(sig)
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
