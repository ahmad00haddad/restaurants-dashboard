"""Opportunity radar: photo / film competitions, festivals, grants, fellowships, open calls, tenders and jobs.

Two jobs, both feeding the `opportunities` table (the site's 🏆 tab):
  scan()    web search (Exa) for open calls, in English and Arabic, worldwide / regional / Jordan, plus public LinkedIn job and post
            pages that the search engine already indexes (we never scrape LinkedIn itself).
  refresh() re-reads the official page of each seeded programme and fills in the CURRENT deadline, prize and fee.

Nothing is invented: the model only extracts. Code decides: the url must appear in the text we read, the organiser must be named
there, the deadline must parse and lie in the future (and not absurdly far), and a call that says it is closed is dropped.
Everything the model claimed is kept as `evidence` so a person can verify before applying.
"""
import html
import json
import re
from datetime import date, datetime, timedelta

import httpx

import local_ai

Y = date.today().year
QUERIES = [
    # international photography
    ("photo", "international", "photography competition open for entries {y} deadline"),
    ("photo", "international", "photography awards call for entries {y} professional photographers"),
    ("photo", "international", "documentary photography grant open call {y} deadline"),
    ("photo", "international", "photojournalism award submissions open {y}"),
    # international film / cinematography
    ("film", "international", "short film festival call for entries {y} submission deadline"),
    ("film", "international", "documentary film festival open call submissions {y}"),
    ("film", "international", "cinematography award competition {y} submissions open"),
    ("film", "international", "film fund grant open call filmmakers {y} deadline"),
    ("film", "international", "commercial advertising film awards entries open {y}"),
    ("both", "international", "emerging filmmakers fellowship programme applications open {y}"),
    ("both", "international", "artist residency photography film application deadline {y}"),
    # regional (Arab world / MENA)
    ("film", "regional", "Arab filmmakers grant open call {y} deadline"),
    ("film", "regional", "MENA short film festival call for entries {y}"),
    ("both", "regional", "Middle East photography award open for submissions {y}"),
    ("both", "regional", "AFAC OR Doha Film Institute OR Red Sea Fund open call {y}"),
    ("film", "regional", "مسابقة أفلام قصيرة التقديم مفتوح {y} الوطن العربي"),
    ("photo", "regional", "مسابقة تصوير فوتوغرافي عربية التقديم حتى {y}"),
    # Jordan
    ("both", "local", "Jordan photography competition {y}"),
    ("film", "local", "Jordan film competition OR festival call for entries {y}"),
    ("film", "local", "Royal Film Commission Jordan open call grant {y}"),
    ("both", "local", "مسابقة تصوير الأردن {y}"),
    ("film", "local", "مسابقة أفلام الأردن الهيئة الملكية للأفلام {y}"),
    ("both", "local", "Jordan youth media award photography video {y} application"),
    # jobs / commissions seen on public pages (LinkedIn pages the search engine indexes; never scraped by us)
    ("both", "local", "videographer cinematographer hiring Jordan site:linkedin.com"),
    ("both", "local", "video producer photographer vacancy Amman site:linkedin.com"),
    ("both", "local", "freelance videographer wanted Jordan {y}"),
]
KINDS = {"competition", "festival", "grant", "fellowship", "residency", "open_call", "tender", "job"}

EXTRACT_SYSTEM = """You extract opportunities for a freelance film director / cinematographer / photographer in Jordan from web search snippets.
An opportunity = a photo or film COMPETITION, festival call for entries, grant, fellowship, residency, open call, tender, or a paid job/commission.
Return JSON only: {"items":[{"index":<snippet number>,"title":"","organizer":"","kind":"competition|festival|grant|fellowship|residency|open_call|tender|job",
"field":"photo|film|both","deadline":"YYYY-MM-DD or null","prize":"","fee":"","open_to_jordan":"yes|no|unknown","eligibility":"one short line",
"description":"one line","evidence":"a short exact quote from the snippet that shows the deadline or that the call is open"}]}
Rules: only what the snippet says; never guess a date; if the snippet only shows an old edition or a closed call, skip it; if the deadline is not
in the snippet use null. The organiser must be named in the snippet. Skip news articles that are not an open call, and skip anything not about
photography, film, video or media production."""
PAGE_SYSTEM = """You read the official page of a recurring photo/film programme and report its CURRENT state.
Return JSON only: {"status":"open|closed|upcoming|unknown","deadline":"YYYY-MM-DD or null","prize":"","fee":"","eligibility":"one short line",
"evidence":"a short exact quote from the page"}. Use only what the page says. If the page shows only a past edition, status is closed and deadline null.
If there are several deadlines (early / regular / late), give the latest one that is still ahead. Never guess a date."""


def _chunks(text):
    out = []
    for ch in re.split(r"(?m)^Title: ", text)[1:]:
        url = (re.search(r"^URL: (\S+)", ch, re.M) or [None, ""])[1]
        out.append((url.strip(), "Title: " + ch[:1400]))
    return out


def _parse_date(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _deadline_ok(d):
    """In the future (today counts) but not absurdly far: a hallucinated or misread year is dropped."""
    return d is not None and date.today() <= d <= date.today() + timedelta(days=550)


NOT_A_CALL = re.compile(r"volunteer|wolontariusz|ticket|bilet|accreditation|press pass|careers?|vacanc|job opening|newsletter|cookie", re.I)


def supports_deadline(evidence, dl):
    """A deadline is believed only when the quote the model gave actually contains that date (its year or day number) and is not about
    volunteers, tickets or jobs. Found by testing: Camerimage's volunteer recruitment was read as the film submission deadline."""
    if not evidence or dl is None or NOT_A_CALL.search(evidence):
        return False
    return str(dl.year) in evidence or re.search(r"(?<!\d)0?%d(?!\d)" % dl.day, evidence) is not None


def fit_score(it):
    """0-100, decided in code: how well the opportunity fits a Jordanian cinematographer-photographer."""
    s = 40
    s += {"local": 25, "regional": 18, "international": 8}.get(it.get("scope"), 0)
    s += {"grant": 15, "fellowship": 12, "competition": 10, "festival": 8, "open_call": 12, "residency": 8, "tender": 12, "job": 10}.get(it.get("kind"), 0)
    if it.get("field") in ("film", "both"):
        s += 8
    fee = (it.get("fee") or "").lower()
    if not fee or re.search(r"free|no fee|بدون|مجان", fee):
        s += 8
    elif re.search(r"\d", fee):
        s -= 6
    if it.get("open_to_jordan") == "unknown":
        s -= 5
    d = _parse_date(it.get("deadline"))
    if d:
        left = (d - date.today()).days
        s += 10 if left <= 21 else 5 if left <= 60 else 0
    return max(5, min(99, s))


def _extract(model, field, scope, query, text):
    chunks = _chunks(text)[:10]
    if not chunks:
        return []
    snippets = "\n\n".join(f"[{i}] {c[1]}" for i, c in enumerate(chunks))
    try:
        out = local_ai.chat(model, EXTRACT_SYSTEM, f"Today is {date.today().isoformat()}.\n\nSNIPPETS:\n{snippets}")
    except Exception:
        return []
    items = []
    for x in out.get("items") or []:
        try:
            i = int(x.get("index"))
        except (TypeError, ValueError):
            continue
        if not 0 <= i < len(chunks):
            continue
        url, body = chunks[i]
        title, org = str(x.get("title") or "").strip(), str(x.get("organizer") or "").strip()
        if not url or len(title) < 6 or len(org) < 2 or org.lower().split()[0] not in body.lower():
            continue  # the organiser must be named in the text we read
        kind = str(x.get("kind") or "").lower()
        if kind not in KINDS or str(x.get("open_to_jordan")).lower() == "no":
            continue
        dl = _parse_date(x.get("deadline"))
        if x.get("deadline") and not _deadline_ok(dl):
            continue  # a stated deadline that is past or implausible: the call is closed or misread
        if dl is not None and not supports_deadline(x.get("evidence"), dl):
            dl = None  # the quote does not show that date: keep the opportunity, drop the unproven deadline
        f = str(x.get("field") or field).lower()
        it = {"title": title[:200], "organizer": org[:120], "kind": kind, "field": f if f in ("photo", "film", "both") else field,
              "scope": scope, "url": url, "deadline": dl.isoformat() if dl else None,
              "prize": str(x.get("prize") or "")[:160] or None, "fee": str(x.get("fee") or "")[:120] or None,
              "eligibility": str(x.get("eligibility") or "")[:200] or None, "description": str(x.get("description") or "")[:300] or None,
              "evidence": str(x.get("evidence") or "")[:300] or None, "open_to_jordan": str(x.get("open_to_jordan") or "unknown").lower(),
              "source": "radar"}
        it["fit"] = fit_score(it)
        items.append(it)
    return items


def scan(db, model, log=print, limit_queries=None):
    """Run the searches; return the NEW rows that were inserted (duplicates by url are ignored by the database)."""
    found, seen_urls = [], set()
    for n, (field, scope, q) in enumerate(QUERIES):
        if limit_queries and n >= limit_queries:
            break
        try:
            text = local_ai._exa(q.format(y=Y), n=8)
        except local_ai.ExaLimit:
            log("radar: search limit reached, will continue next time")
            break
        except Exception as e:
            log("radar: search failed:", str(e)[:80])
            continue
        for it in _extract(model, field, scope, q, text):
            if it["url"] not in seen_urls:
                seen_urls.add(it["url"])
                found.append(it)
    if not found:
        return []
    rows = [{k: v for k, v in it.items() if k != "open_to_jordan"} for it in found]
    new = db.req("POST", "opportunities", {"on_conflict": "url"}, rows, prefer="resolution=ignore-duplicates,return=representation") or []
    log(f"radar: {len(found)} candidates, {len(new)} new")
    return new


def _page_text(url):
    r = httpx.get(url, timeout=25, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128 Safari/537.36"})
    if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
        return ""
    h = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer)[^>]*>.*?</\1>", " ", r.text[:600_000])
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()


def refresh(db, model, log=print, max_pages=3):
    """Read the official pages of seeded / unchecked programmes and fill in the current deadline (oldest check first)."""
    cutoff = (date.today() - timedelta(days=10)).isoformat()
    rows = db.get("opportunities", select="*", source="eq.seed", status="neq.skip",
                  **{"or": f"(last_checked.is.null,last_checked.lt.{cutoff})"}, order="last_checked.nullsfirst", limit=str(max_pages))
    done = 0
    for r in rows:
        patch = {"last_checked": date.today().isoformat()}
        try:
            text = _page_text(r["url"])
            if len(text) > 300:
                out = local_ai.chat(model, PAGE_SYSTEM, f"Today is {date.today().isoformat()}.\nProgramme: {r['title']}\nPAGE TEXT:\n{text[:7000]}")
                st, dl = str(out.get("status") or "unknown").lower(), _parse_date(out.get("deadline"))
                if st in ("open", "upcoming") and _deadline_ok(dl) and supports_deadline(out.get("evidence"), dl):
                    patch.update(deadline=dl.isoformat())
                elif st == "closed":
                    patch.update(deadline=None, notes=((r.get("notes") or "") + " [الدورة الحالية مغلقة حسب الصفحة]").strip())
                for k in ("prize", "fee", "eligibility"):
                    if out.get(k):
                        patch[k] = str(out[k])[:200]
                if out.get("evidence") and "deadline" in patch:
                    patch["evidence"] = str(out["evidence"])[:300]
                patch["fit"] = fit_score({**r, **patch})
                done += 1
        except Exception as e:
            log("radar: page check failed:", r["title"][:40], str(e)[:60])
        db.patch("opportunities", {"id": r["id"]}, patch)
    return done


def digest(new, limit=8):
    """Telegram text for the new finds, best fit first."""
    if not new:
        return None
    new = sorted(new, key=lambda r: -(r.get("fit") or 0))[:limit]
    lines = ["🏆 فرص جديدة في الرادار:"]
    for r in new:
        dl = f" — تُغلق {r['deadline']}" if r.get("deadline") else ""
        lines.append(f"• {r['title']} ({r.get('organizer') or ''}){dl}\n  {r['url']}")
    lines.append("افتح تبويب 🏆 في الموقع للتفاصيل والحفظ.")
    return "\n".join(lines)
