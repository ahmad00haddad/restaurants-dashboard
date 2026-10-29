"""Import lookalike harvest files and tag them: a place that was already in the database (merged by domain/phone/name) and never
contacted also gets the lookalike source, so its first email shows the matching film.
Usage: python import_lookalike.py ../harvester/leads-lookalike-*.json
"""
import glob, json, re, sys
sys.path.insert(0, ".")
import agent

db = agent.db


def find(r):
    d = re.sub(r"\D", "", r.get("phone") or "")
    if len(d) >= 8:
        hit = db.get("leads", select="id,status,source", phone_key=f"eq.{d[-9:]}")
        if hit:
            return hit[0]
    m = re.match(r"^(?:https?://)?(?:www\.)?([^/:?#]+)", (r.get("website") or "").lower())
    if m:
        hit = db.get("leads", select="id,status,source", domain=f"eq.{m.group(1)}")
        if hit:
            return hit[0]
    return None


for path in [p for a in sys.argv[1:] for p in glob.glob(a)]:
    rows = agent.clean(json.load(open(path, encoding="utf-8")))
    res = db.req("POST", "rpc/ingest_leads", None, {"rows": rows})
    tagged = 0
    for r in rows:
        L = find(r)
        if L and L["status"] == "new" and not str(L.get("source") or "").startswith("lookalike:"):
            db.patch("leads", {"id": L["id"]}, {"source": r["source"]})
            tagged += 1
    print(f"{path}: {len(rows)} rows, {sum(1 for r in rows if r.get('email'))} with email, inserted {res['inserted']}, merged {res['merged']}, re-tagged {tagged}")
