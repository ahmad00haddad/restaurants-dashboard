"""Cloud sender: sends the emails you approved even when the agent on your PC is off.

Runs from GitHub Actions every 5 minutes (.github/workflows/send.yml). Each run:
  1. rebuilds today's count and the last weeks' history from the database (nothing is kept on a PC),
  2. reads Gmail for bounces (so the daily limit and the bad-address list stay honest),
  3. takes ONE approved email (urgent ones first: ⚡, tender closing soon, answers to people who replied) and sends it through
     the very same safety gate and daily limit as the agent (agent.approve),
so approved emails leave about 5 minutes apart. Normal emails go only inside SEND_HOURS on working days; urgent ones any time.
Nothing here prints addresses or message text: the Actions log of a public repository is public.
"""
import sys
from datetime import date, datetime, timedelta, timezone

import agent
from agent import STATE, db, E


def seed_state():
    """The agent keeps its counters in state.json on the PC; here they come from the database."""
    today = date.today().isoformat()
    since = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    per_day, off = {}, 0
    while True:
        rows = db.get("lead_messages", select="sent_at", review="eq.sent", channel="eq.email", direction="eq.out",
                      sent_at=f"gte.{since}", order="sent_at", limit="1000", offset=str(off))
        for r in rows:
            try:
                dt = datetime.fromisoformat(str(r["sent_at"]).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)  # the agent stores UTC
                d = dt.astimezone().date().isoformat()  # local day (TZ is Asia/Amman in the workflow)
                per_day[d] = per_day.get(d, 0) + 1
            except (KeyError, ValueError):
                continue
        if len(rows) < 1000:
            break
        off += 1000
    STATE["sent_log"] = per_day
    STATE["sent_day"], STATE["sent_count"] = today, per_day.get(today, 0)


def main():
    if not (E.get("GMAIL_USER") and E.get("GMAIL_APP_PASSWORD")):
        print("GMAIL_USER / GMAIL_APP_PASSWORD secrets are missing")
        return 1
    seed_state()
    try:
        agent.check_bounces()
    except Exception as e:
        print("bounce check failed:", type(e).__name__)
    rows = db.get("lead_messages", select="id,channel,review_note,leads(status,signal,signal_until,needs_reply)",
                  review="eq.approved", channel="eq.email", order="created_at", limit="50")
    urgent = [m for m in rows if agent.is_rush(m, m.get("leads") or {})]
    normal = [m for m in rows if m not in urgent] if agent.in_send_window() else []
    batch = urgent + normal[:1]
    print(f"approved emails waiting: {len(rows)} (urgent {len(urgent)}); sending {len(batch)}; sent today so far {STATE['sent_count']}")
    for m in batch:
        if not agent.claim(m["id"]):
            continue  # the PC agent took it
        try:
            res = agent.approve(m["id"], None, own_claim=True)
            print("result:", res.split("\n")[0][:2])  # only the status icon, never an address
        except agent.Capped:
            agent.hold_capped(m["id"], "مؤجلة: وصلت للحد اليومي — تُرسل تلقائياً غداً")
            print("daily limit reached")
            break
        except Exception as e:
            db.patch("lead_messages", {"id": m["id"]}, {"review": "failed", "review_note": str(e)[:300]})
            print("send failed:", type(e).__name__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
