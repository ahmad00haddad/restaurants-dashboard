"""Telegram reports: a full morning report (/report) and a short end-of-day summary (/today).

Both are built from the database (what was really sent / received), never from counters on this PC, so they stay right
after a restart. Every function takes the running `agent` module so it can reuse its db, state and limits.
"""
from collections import Counter
from datetime import date, datetime, timedelta, timezone

KIND = {"ngo": "منظمات", "org": "مؤسسات", "restaurant": "مطاعم", "roastery": "محامص", "pharmacy": "صيدليات", "school": "مدارس",
        "brand": "براندات", "hotel": "فنادق", "event": "فعاليات", "other": "أخرى"}


def _local_day(iso):
    """'2026-10-11T19:40:00' (UTC unless it carries an offset) -> the local calendar day on this PC."""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().date().isoformat()


def _page(db, table, **params):
    out, off = [], 0
    while True:
        rows = db.get(table, limit="1000", offset=str(off), **params)
        out += rows
        if len(rows) < 1000 or off > 20000:
            return out
        off += 1000


def activity(agent, days=30):
    """Sent and received messages of the last `days` days: {"sent": [(day, channel, kind)], "in": [(day, kind, name)]}."""
    since = (datetime.now(timezone.utc) - timedelta(days=days + 1)).isoformat()
    out = _page(agent.db, "lead_messages", select="channel,sent_at,leads(kind)", direction="eq.out", review="eq.sent", sent_at=f"gte.{since}")
    inn = _page(agent.db, "lead_messages", select="created_at,body,leads(kind,name)", direction="eq.in", created_at=f"gte.{since}")
    return {
        "sent": [(_local_day(r["sent_at"]), r["channel"], (r.get("leads") or {}).get("kind")) for r in out if r.get("sent_at")],
        "in": [(_local_day(r["created_at"]), (r.get("leads") or {}).get("kind"), (r.get("leads") or {}).get("name") or "?") for r in inn],
    }


def _queue(agent):
    rows = _page(agent.db, "lead_messages", select="review,channel", draft="eq.true", review="in.(approved,pending,failed,write,sending)")
    c = Counter(r["review"] for r in rows)
    return c


def _real_replies_today(agent, today):
    """How many of today's replies are real (not automatic), from the lessons the agent saved; None when that table is not there."""
    try:
        rows = _page(agent.db, "reply_insights", select="category,created_at", created_at=f"gte.{today}T00:00:00")
    except Exception:
        return None
    return sum(1 for r in rows if not str(r["category"]).startswith("auto_reply") and r["category"] != "out_of_office")


def _health(agent):
    cap, rate = agent.current_cap()
    week = [(date.today() - timedelta(days=i)).isoformat() for i in range(7)]
    bounces = sum(1 for d in agent.STATE.get("bounces", {}).values() if d in week)
    return cap, rate, bounces


def daily(agent):
    """End of day: what really happened today and what waits for tomorrow."""
    today = date.today().isoformat()
    a = activity(agent, days=8)
    sent_today = [s for s in a["sent"] if s[0] == today]
    emails = sum(1 for s in sent_today if s[1] == "email")
    other = len(sent_today) - emails
    cap, rate, bounces = _health(agent)
    q = _queue(agent)
    replies_today = [r for r in a["in"] if r[0] == today]
    real = _real_replies_today(agent, today)
    by_kind = Counter(KIND.get(s[2] or "other", "أخرى") for s in sent_today)
    lines = [f"🌙 ملخص اليوم {today}",
             f"📤 أُرسل اليوم: {emails} إيميل من الحد اليومي {cap}" + (f" + {other} واتساب/إنستغرام" if other else ""),
             ("   " + " · ".join(f"{k} {n}" for k, n in by_kind.most_common())) if by_kind else "   (لم يُرسل شيء اليوم)",
             f"💬 ردود اليوم: {len(replies_today)}" + (f" (حقيقية {real})" if real is not None else "")
             + "".join(f"\n   • {n}" for _d, _k, n in replies_today[:5]),
             f"⏳ جاهزة للإرسال: {q.get('approved', 0)} · بانتظار موافقتك: {q.get('pending', 0)} · تُكتب الآن: {q.get('write', 0)}"
             + (f" · فشلت: {q.get('failed', 0)}" if q.get("failed") else ""),
             f"🛡 ارتدادات آخر 7 أيام: {bounces}" + (" ⚠️ مرتفعة" if rate > 0.04 else "")]
    if q.get("sending", 0):
        lines.append(f"⚠️ {q['sending']} إيميل عالق بحالة «تُرسل الآن»: افتح Gmail (Sent) وتأكد هل خرج، ولا تُعد إرساله قبل ذلك.")
    if q.get("pending", 0):
        lines.append("افتح الموقع (✅ اليوم) لمراجعة المسودات التي تنتظرك.")
    return "\n\n".join(lines)


def full(agent, leads):
    """Morning report: sending, queue, replies, sectors, opportunities, health, pipeline."""
    today = date.today().isoformat()
    y = (date.today() - timedelta(days=1)).isoformat()
    week = {(date.today() - timedelta(days=i)).isoformat() for i in range(7)}
    a = activity(agent, days=30)
    sent = a["sent"]
    n_today, n_y = sum(1 for s in sent if s[0] == today), sum(1 for s in sent if s[0] == y)
    n_week = sum(1 for s in sent if s[0] in week)
    cap, rate, bounces = _health(agent)
    q = _queue(agent)
    # per sector, last 30 days: sent / replied
    sent_k, reply_k = Counter(s[2] or "other" for s in sent), Counter(r[1] or "other" for r in a["in"])
    sectors = [f"   {KIND.get(k, k)}: أُرسل {n}" + (f" · ردّ {reply_k[k]}" if reply_k.get(k) else "") for k, n in sent_k.most_common(6)]
    replies_week = [r for r in a["in"] if r[0] in week]
    waiting = [l for l in leads if l["needs_reply"]]
    follow = [l for l in leads if l["status"] == "contacted" and l["next_action_at"] and l["next_action_at"] <= today and l["followups"] < 1]
    signals = sorted([l for l in leads if l["signal"] and (not l["signal_until"] or l["signal_until"] >= today) and l["status"] not in ("won", "lost", "skip")],
                     key=lambda l: l["signal_until"] or "9")
    best = sorted([l for l in leads if l["status"] == "new" and l["score"] is not None and (l["email"] or l["phone"])], key=lambda l: -l["score"])
    pipe = sum(float(l["deal_value"] or 0) for l in leads if l["status"] in ("replied", "meeting"))
    won = sum(float(l["deal_value"] or 0) for l in leads if l["status"] == "won")
    radar = ""
    try:
        opp = agent.db.get("opportunities", select="title,deadline,status", status="in.(new,saved,applying)", deadline=f"lte.{(date.today() + timedelta(days=14)).isoformat()}",
                           order="deadline", limit="50")
        opp = [o for o in opp if o.get("deadline") and o["deadline"] >= today]
        if opp:
            radar = f"🏆 مسابقات ومنح تُغلق خلال 14 يوماً: {len(opp)}" + "".join(f"\n   • {o['title'][:50]} ({o['deadline']})" for o in opp[:3])
    except Exception:
        pass
    lines = [f"☀️ صباح الخير — تقرير {today} (شامل)",
             f"📤 الإرسال: اليوم {n_today} · أمس {n_y} · آخر 7 أيام {n_week} · الحد اليومي {cap}",
             f"⏳ جاهزة للإرسال {q.get('approved', 0)} · بانتظار موافقتك {q.get('pending', 0)} · فشلت {q.get('failed', 0)}",
             f"💬 ردود آخر 7 أيام: {len(replies_week)}  ·  🔥 تنتظر جوابك: {len(waiting)}" + "".join(f"\n   • {l['name']}" for l in waiting[:5]),
             ("📊 حسب القطاع (30 يوماً):\n" + "\n".join(sectors)) if sectors else "📊 لا إرسال في آخر 30 يوماً",
             f"↩️ متابعات مستحقة: {len(follow)}",
             f"🔔 فرص عملاء مفتوحة: {len(signals)}" + "".join(f"\n   • {l['name']} — {l['signal'][:60]} ({l['signal_until'] or ''})" for l in signals[:4]),
             radar or None,
             "🎯 أفضل جدد: " + "، ".join(f"{l['name']} ({l['score']})" for l in best[:5]),
             f"🛡 ارتدادات 7 أيام: {bounces}" + (" ⚠️ مرتفعة: جمّد النظام رفع الحد" if rate > 0.04 else " (سليم)"),
             f"💰 {len(leads)} عميل · تواصلنا مع {sum(1 for l in leads if l['status'] not in ('new', 'skip'))} · قيد التفاوض {pipe:.0f} د.أ · صفقات {won:.0f} د.أ"]
    return "\n\n".join(x for x in lines if x)
