"""Local analysis on your GPU (Ollama) — no Lovable credit.

Reads each new lead's website, builds the same profile the site's AI builds (who they are, interests,
content needs, best service, angle, hook, closest flagship work, which site to link, language, score)
and saves it, so "best new leads" and message writing work from it.
"""
import json, os, re, sys, time
from pathlib import Path
import httpx
import emailcheck

sys.path.insert(0, str(Path(__file__).parent.parent / "harvester"))
from harvest import read_site  # same website reader the collector uses (email, socials, text)

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
restaurants, companies, campaigns; behance only for creative agencies."""


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


def complete(model, system, user, temperature=0.2, as_json=True):
    """One call to the chosen model. 'nv:<id>' = NVIDIA; if it fails, the local Ollama model (OLLAMA_MODEL) takes over."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if is_nv(model):
        err = None
        for m in dict.fromkeys([model, NV_SMALL]):  # big model first, then the faster NVIDIA one, then local
            try:
                return _nv_chat(m, messages, temperature)
            except Exception as e:
                err = e
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
        r = httpx.post(EXA, timeout=40, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
                       json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                             "params": {"name": "web_search_exa", "arguments": {"query": q, "numResults": 8}}})
        data = next((json.loads(l[5:]) for l in r.text.splitlines() if l.startswith("data:")), {})
        text = "".join(c.get("text", "") for c in data.get("result", {}).get("content", []))
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


PEOPLE_SYSTEM = """You find who to address at an organisation, from web search snippets. Rules:
- Only people the snippet says CURRENTLY work at that exact organisation (same country office if the snippet says so).
- Skip anyone described as former / ex- / left / "after N years" / "new job", people at other organisations or other country offices, and posts about someone else.
- name must be copied EXACTLY as written in the snippet. Never guess, never complete a name.
- role = their title as written. Prefer communications / media / marketing / outreach / partnerships / fundraising, then director / head / owner / founder / general manager.
Return JSON only: {"people":[{"name":"...","role":"...","url":"...","index":<snippet number>}]}. Empty list when unsure."""
ROLE_OK = re.compile(r"communicat|comms|media|marketing|outreach|advocacy|public information|brand|content|social media|fundrais|partnership|resource mobili|director|head of|manager|owner|founder|ceo|chief|president|coordinator|officer", re.I)
ROLE_TOP = re.compile(r"communicat|comms|media|marketing|outreach|advocacy|public information|brand|content|social media|fundrais|partnership", re.I)
STALE = re.compile(r"\b(former|formerly|ex-|previously|past)\b|\bafter \d+ years\b|new job|i'?m now|officially (left|leaving)", re.I)
ORG_KINDS = {"ngo", "org", "hotel", "brand", "event"}


def _exa(query, n=8):
    r = httpx.post(EXA, timeout=40, headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
                   json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "web_search_exa", "arguments": {"query": query, "numResults": n}}})
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
    except Exception:
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
        people.append({"name": pn, "role": role[:80], "url": chunks[i][0], "top": bool(ROLE_TOP.search(role)), "status": "unverified", "as_of": chunks[i][2]})
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


def tier_of(score, L, p):
    """A = worth hand-checking and sending first; B = normal; C = low touch. Decided in code, never by the model.
    A: strong fit AND a reachable person (named mailbox or phone) AND a concrete reason now (fresh news, live signal, or a personal mailbox)."""
    ec = p.get("email_check") or {}
    mail_ok = bool(L.get("email")) and ec.get("ok") is not False
    named = mail_ok and not ec.get("role")
    reachable = named or bool(L.get("phone")) or mail_ok
    if score >= 70 and (named or L.get("phone")) and (p.get("hook_source") == "news" or L.get("signal") or named):
        return "A"
    if score >= 45 and reachable:
        return "B"
    return "C"


def analyze(db, L, team, model):
    """Profile one lead. Returns the patch saved to the database."""
    patch = {}
    if L.get("website") and not L.get("about"):
        site = read_site({"name": L["name"], "website": L["website"]})
        for k in ("about", "email", "instagram", "facebook", "linkedin", "youtube", "tiktok"):
            if site.get(k) and not L.get(k):
                patch[k] = site[k]
        L = {**L, **patch}
    recent = fresh(L)
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
        p["link_pick"] = "personal" if L.get("kind") in ("ngo", "org") else "team"
    p["analysed_by"] = f"local:{model}"
    if L.get("email"):
        p["email_check"] = emailcheck.check(L["email"])
    if recent:
        p["recent"] = recent
        h = recent_hook(L, recent, p["lang"], model)
        if h:
            p["hook"] = h
            p["hook_source"] = "news"
    if L.get("kind") in ORG_KINDS and score >= 60:
        people = find_people(L, model)
        if people:
            p["people"] = people
            p["decision_maker"] = f"{people[0]['name']} — {people[0]['role']} (مرشّح غير مؤكد، المصدر {people[0]['as_of']})"
            who = addressable(L, people)
            if who:
                p["contact"] = who
    p["tier"] = tier_of(score, L, p)
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
             f"- {consts['PERSONAL_SITE']} — default; organisations, NGOs, institutions, culture, documentaries.\n"
             f"- {consts['TEAM_SITE']} — brands, restaurants, cafés, companies, campaigns, larger productions.\n"
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
    if arabic_name or L.get("kind") in ("restaurant", "brand") and not re.search(r"international|global|un |unicef|usaid", L.get("name", ""), re.I):
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


def close_for(L, lang):
    import hashlib
    opts = CLOSES["ar" if lang == "ar" else "en"]
    return opts[int(hashlib.md5(("close" + str(L.get("id") or L.get("name"))).encode()).hexdigest(), 16) % len(opts)]


# Any closing line the model writes is replaced by Ahmad's chosen close (exactly one close per message).
CLOSE_LIKE = re.compile(r"timing|conversation|discuss|talk|time allows|convenient|التوقيت|نتحدث|حديث|مناقشة|نناقش|نقاش|الحديث|الوقت|مناسب", re.I)
FLATTERY = re.compile(r"\b(truly|commendable|impressive|amazing|incredible|inspiring|remarkable)\b|رائع|مذهل|ملهم|مبهر|نثمّن|نقدّر جهودكم", re.I)


OFFER = re.compile(r"فيلم|أفلام|نصوّر|نصور|نوثّق بالصورة|film|shoot|video", re.I)  # not "تصوير": it is in the title "مدير تصوير"


def write(L, team, history, channel, mode, hint, model):
    """Write, and retry once if the model skipped the idea or cleanup left too little (never queue a hollow message)."""
    last = None
    for attempt in range(2):
        try:
            subject, final = _write_once(L, team, history, channel, mode,
                                         hint if attempt == 0 else ((hint or "") + " The idea sentence is mandatory: say plainly what short film we could shoot for them."), model)
            core = " ".join(final.split("\n\n")[1:-2])
            if mode != "first" or OFFER.search(core):
                return subject, final
            last = ValueError("the message has no clear film idea")
        except ValueError as e:
            last = e
    raise last


# ---------------- Sector-matched proof (decided in code, never by the model) ----------------
NGO_PROOF = ["USAID", "UNICEF", "Mercy Corps", "UN Women", "QRTA", "Erasmus"]
FOOD_PROOF = ["Em Sherif", "Khan Zaid", "Astrolabe", "Arafah", "Arafa", "L'Occitane", "أم شريف", "خان زيد", "إسطرلاب", "اسطرلاب", "عرفة", "لوكسيتان"]


def sector(L):
    c = f"{L.get('category') or ''} {L.get('name') or ''}".lower()
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
ALL_CLIENT_NAMES = NGO_PROOF + FOOD_PROOF + ["Duroub", "دروب", "رانيا", "Mercy Corps", "UNICEF", "UN Women", "Jameel"]


def intro_for(L, lang):
    import hashlib
    opts = INTROS[sector(L)]["ar" if lang == "ar" else "en"]
    return opts[int(hashlib.md5(str(L.get("id") or L.get("name")).encode()).hexdigest(), 16) % len(opts)]


def wrong_proof(L, body):
    """Ahmad's rule: no client names in outreach — the website shows who he worked with."""
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
              + ("(a restaurant/brand: a short film or ad about their food/product/place, not a documentary about social impact)" if sector(L) in ("food", "brand", "hotel") else "")
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
    final = finish(body, L, team, lang)
    core = final.split("\n\n")[1:-2]  # between greeting and close+signature
    if len(" ".join(core)) < max(80, len(body) * 0.4):
        raise ValueError("cleanup removed the message body — not queued")  # never send an empty-looking message
    return subject.strip() or None, final


SITES = {"personal": "https://ahmadhaddad.lovable.app", "team": "https://faiihouse.lovable.app", "behance": "https://www.behance.net/ahmad00haddad"}


def short_name(name):
    """'International Rescue Committee (IRC) - Jordan' → 'IRC Jordan'; Arabic names stay as they are."""
    acr = re.search(r"\(([A-Za-z]{2,8})\)", name)
    if acr:
        return acr.group(1) + (" Jordan" if "jordan" in name.lower() else "")
    return re.sub(r"\s+[-–|]\s+[^-–|]*$", "", name).strip() or name


def finish(body, L, team, lang="en"):
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
    text = "\n\n".join(paras + [close_for(L, lang)])
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
    site = SITES.get(p.get("link_pick"), SITES["personal" if L.get("kind") in ("ngo", "org") else "team"])
    if lang == "ar":
        sig = ["أحمد حدّاد", "مخرج ومدير تصوير، FAII HOUSE", f"بعض أعمالي ومن عملت معهم: {site}"]
    else:
        role = team.get("senderRole") or "Director & Cinematographer"
        sig = [name if re.match(r"[A-Za-z]", name) else "Ahmad Haddad", f"{role}, {team.get('company') or 'FAII HOUSE'}", f"Selected work and past clients: {site}"]
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
