"""Local analysis on your GPU (Ollama) — no Lovable credit.

Reads each new lead's website, builds the same profile the site's AI builds (who they are, interests,
content needs, best service, angle, hook, closest flagship work, which site to link, language, score)
and saves it, so "best new leads" and message writing work from it.
"""
import json, re, sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "harvester"))
from harvest import read_site  # same website reader the collector uses (email, socials, text)

OLLAMA = "http://127.0.0.1:11434"

SYSTEM = """You research potential clients for Ahmad Haddad, a director/photographer with a team (FAII House) in Jordan,
before anyone contacts them. Figure out what kind of client this is, what they care about, and what visual content would
genuinely help them. Be honest: weak signals = low score. Organisations with programmes, beneficiaries, donors, campaigns
or anniversaries are strong documentary fits; brands, restaurants and cafés fit brand films, ads and social content.
Write the profile in Arabic, except names. Return JSON only."""

SCHEMA = """{"summary":"who they are, one line","interests":["what they care about"],"content_needs":["visual content they likely need"],
"best_service":"one of our services","other_services":["..."],"angle":"one concrete film/photo idea made for them",
"hook":"a real specific detail from their info to open with (empty if none)","portfolio_pick":"name of the closest ★ work (no url)",
"link_pick":"personal | team | behance","tone":"formal|warm|casual","lang":"ar|en","channel":"email|whatsapp|instagram",
"decision_maker":"role to address","score":0-100,"why":"one short line"}"""

LANG_HINT = """Language for the future message: UN agencies, international NGOs/donors, EU programmes, embassies, international brands and
tech companies → en; Jordanian institutions, local charities and initiatives, restaurants, cafés, shops and local brands → ar.
Their own website's main language wins. link_pick: personal for organisations/NGOs/culture/documentary; team for brands,
restaurants, companies, campaigns; behance only for creative agencies."""


def available(model):
    try:
        names = [m["name"] for m in httpx.get(f"{OLLAMA}/api/tags", timeout=5).json()["models"]]
        return model in names or f"{model}:latest" in names
    except Exception:
        return False


def chat(model, system, user):
    r = httpx.post(f"{OLLAMA}/api/chat", timeout=300, json={
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0.2, "num_ctx": 8192},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    r.raise_for_status()
    txt = r.json()["message"]["content"]
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("model returned no JSON")
    return json.loads(m.group(0))


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


def analyze(db, L, team, model):
    """Profile one lead. Returns the patch saved to the database."""
    patch = {}
    if L.get("website") and not L.get("about"):
        site = read_site({"name": L["name"], "website": L["website"]})
        for k in ("about", "email", "instagram", "facebook", "linkedin", "youtube", "tiktok"):
            if site.get(k) and not L.get(k):
                patch[k] = site[k]
        L = {**L, **patch}
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


CLOSE = {"en": "If the timing is right on your side, I'd enjoy a conversation about it.",
         "ar": "إن كان التوقيت مناسباً لديكم، يسعدني أن نتحدث."}
FLATTERY = re.compile(r"\b(truly|commendable|impressive|amazing|incredible|inspiring|remarkable)\b|رائع|مذهل|ملهم|مبهر|نثمّن|نقدّر جهودكم", re.I)


def write(L, team, history, channel, mode, hint, model):
    voice, editor, links = rules(team)
    lang = lang_for(L)
    ctx = (f"Sender: {team.get('senderName')}, {team.get('company')}\nWho we are: {team.get('whoWeAre', '')}\n"
           f"PAST CLIENTS (the only names you may mention):\n{team.get('pastClients', '')}\n\n"
           f"OUR WORKS you may NAME as proof (★ = flagship, prefer them; respect 'ONLY …'). Write the name naturally in a sentence. Never open with 'I would like to propose' / 'أود أن أقترح' — open with them, "
           f"e.g. 'we told a similar story for USAID in Rajaa' — never copy the brackets:\n{works_list(team)}")
    user = (f"{ctx}\n\nCLIENT:\n{them(L)}\n\nWHAT WE KNOW ABOUT THEM:\n{json.dumps(L.get('profile') or {}, ensure_ascii=False)}\n\n"
            f"CONVERSATION SO FAR:\n{history or '(none)'}\n\nCHANNEL: {channel}\nTASK: {TASKS[mode]}"
            + (f"\nEXTRA INSTRUCTION FROM AHMAD: {hint}" if hint else "")
            + f"\n\nLANGUAGE: write the whole message in {'Arabic (elegant, correct Modern Standard Arabic)' if lang == 'ar' else 'English'}."
            + "\nNO praise words at all (no 'truly', 'commendable', 'impressive', 'رائع', 'ملهم'). State facts, not compliments."
            + "\nSTRUCTURE (mandatory): 1) greeting; 2) one specific observation about their work (the hook); "
              "3) ONE quiet line introducing the sender with the proof, e.g. 'I'm Ahmad Haddad, a director and photographer based in Jordan; "
              "I've documented similar stories for USAID and QRTA.' / 'أنا أحمد حدّاد، مخرج ومصوّر من الأردن، وثّقت قصصاً مشابهة لـ USAID وQRTA.' "
              "(only past clients/★ works close to them); 4) the idea for their story in one or two sentences; 5) one calm closing line. "
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
    return subject.strip() or None, finish(body, L, team, lang)


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
    while lines and (name.split()[0] in lines[-1] or not lines[-1].strip()):
        lines.pop()  # drop any signature the model wrote itself
    text = "\n".join(lines).strip()
    # Remove only the weak closing SENTENCE (never a whole line — the model sometimes writes everything on one line)
    text = re.sub(r"[^.؟?!\n]*(\b(I am|I'm) available\b|متاح(ون)? ل|يسعدني التواصل|لا تتردد)[^.؟?!\n]*[.؟?!]?", "", text, flags=re.I).strip()
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
    if not re.search(r"timing|conversation|talk|التوقيت|نتحدث|حديث", text[-200:], re.I):
        text += "\n\n" + CLOSE[lang]
    # Always one clean greeting: drop whatever greeting-ish lines the model wrote, then add ours.
    ls = text.splitlines()
    while ls and (not ls[0].strip() or len(ls[0]) < 70 and (re.match(r"\s*(dear|hello|hi|السادة|الأخوة|الإخوة|مرحب|تحية|السلام|إلى)", ls[0], re.I)
                                                          or L["name"][:12] in ls[0] or ls[0].strip().endswith((",", "،")))):
        ls.pop(0)
    text = "\n".join(ls).strip()
    text = (f"السادة في {short_name(L['name'])} المحترمين،" if lang == "ar" else f"Dear {short_name(L['name'])} team,") + "\n\n" + text
    p = L.get("profile") or {}
    site = SITES.get(p.get("link_pick"), SITES["personal" if L.get("kind") in ("ngo", "org") else "team"])
    if lang == "ar":
        sig = ["أحمد حدّاد", "مخرج ومصوّر، FAII HOUSE", f"بعض أعمالي: {site}"]
    else:
        role = team.get("senderRole") or "Director & Photographer"
        sig = [name if re.match(r"[A-Za-z]", name) else "Ahmad Haddad", f"{role}, {team.get('company') or 'FAII HOUSE'}", f"Selected work: {site}"]
    return text + "\n\n" + "\n".join(sig)


def translate_ar(text, model):
    """Arabic translation of an English draft, shown to Ahmad only (never sent)."""
    out = chat(model, "Translate the message into clear, natural Arabic for the sender to understand it. Keep names as they are. Return JSON only: {\"ar\": \"...\"}", text)
    return (out.get("ar") or "").strip()
