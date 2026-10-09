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
