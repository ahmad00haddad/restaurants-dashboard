import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useRef, useState, type ReactNode } from "react";
import { useAgentStatus, useApprovals, useLastMessages, useLeadActions, useLeads, useTouchedLeads, type LastMessage } from "@/hooks/useLeads";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import { LeadPanel } from "@/components/LeadPanel";
import { Approvals } from "@/components/Approvals";
import { AddLead } from "@/components/AddLead";
import { Funnel } from "@/components/Funnel";
import { Radar } from "@/components/Radar";
import { ReplyLessons } from "@/components/ReplyLessons";
import { useOpportunities } from "@/hooks/useOpportunities";
import { daysLeft, isActiveOpp } from "@/lib/opportunities";
import { KIND_LABEL, NAS_ASK_LABEL, NAS_SITE, STATUS_LABEL, emailBad, irbidFirst, localFirst, tierRank, type Lead, type LeadStatus } from "@/lib/leads";

export const Route = createFileRoute("/_authenticated/")({
  head: () => ({ meta: [{ title: "FAII — Sales" }] }),
  component: Home,
});

/** Four places, one question each: what do I do now / who did we write to / who is next / which tenders are open. */
type View = "today" | "convos" | "new" | "opps" | "approvals" | "stats" | "nas";
const today = (plus = 0) => new Date(Date.now() + plus * 864e5).toLocaleDateString("en-CA"); // local date, not UTC
const daysAgo = (iso: string) => Math.floor((Date.now() - new Date(iso).getTime()) / 864e5);
const STAGES: { status: LeadStatus; label: string }[] = [
  { status: "contacted", label: "⏳ بانتظار الرد" },
  { status: "replied", label: "💬 ردّوا" },
  { status: "meeting", label: "🤝 اجتماع / عرض" },
  { status: "won", label: "🏆 صفقة" },
  { status: "lost", label: "✖ لم تنجح" },
];
const btn = "px-3 py-1.5 rounded border border-border text-sm";

function Home() {
  const { data: allLeads = [], isLoading, error } = useLeads();
  const leads = allLeads;
  const { data: last = {} } = useLastMessages();
  const act = useLeadActions();
  const toast = useToast();
  const { signOut } = useAuth();
  const { data: approvals = [] } = useApprovals();
  const { data: touched = new Set<string>() } = useTouchedLeads();
  const { data: agent } = useAgentStatus();
  const { data: radarOpps = [] } = useOpportunities();
  const radarOpen = radarOpps.filter(isActiveOpp).length;
  const radarClosing = radarOpps.filter((o) => isActiveOpp(o) && (daysLeft(o.deadline) ?? 99) <= 14);
  const fileRef = useRef<HTMLInputElement>(null);
  const [view, setView] = useState<View>("today");
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [limit, setLimit] = useState(100);
  /** Emails we already wrote to (on any lead record) — a duplicate record with the same address must not get a first message. */
  const contactedEmails = useMemo(() => new Set(leads.filter((l) => l.email && ["contacted", "replied", "meeting", "won", "lost"].includes(l.status)).map((l) => l.email!.trim().toLowerCase())), [leads]);
  const alreadyMailed = (l: Lead) => !!l.email && contactedEmails.has(l.email.trim().toLowerCase());

  const nasLeads = useMemo(() => leads.filter((l) => l.program === "nas").sort((a, b) => (a.profile?.tier ?? "C").localeCompare(b.profile?.tier ?? "C") || (b.score ?? 0) - (a.score ?? 0)), [leads]);
  const groups = useMemo(() => {
    const t = today();
    const leads = allLeads.filter((l) => l.program !== "nas"); // Nas Irbid sponsors have their own tab and their own voice
    const reply = leads.filter((l) => l.needs_reply);
    const followup = leads.filter((l) => l.status === "contacted" && l.next_action_at && l.next_action_at <= t && l.followups < 1);
    const nextStep = leads.filter((l) => ["replied", "meeting"].includes(l.status) && !l.needs_reply && l.next_action_at && l.next_action_at <= t);
    // Only leads nobody has written to yet: once contacted they live in the conversations tab, not here.
    const signals = leads.filter((l) => l.signal && (!l.signal_until || l.signal_until >= t) && l.status === "new" && !alreadyMailed(l))
      .sort((a, b) => (a.signal_until ?? "9").localeCompare(b.signal_until ?? "9"));
    const closing = signals.filter((l) => l.status === "new" && l.signal_until && l.signal_until <= today(7));
    // "New" = never written to. Analysed first (tier A, then score), then the not-yet-analysed; a proven-bad email is not a way in.
    const fresh = leads.filter((l) => l.status === "new" && !alreadyMailed(l) && ((l.email && !emailBad(l)) || l.phone || l.instagram))
      .sort((a, b) => Number(a.score == null) - Number(b.score == null) || localFirst(a) - localFirst(b) || tierRank(a) - tierRank(b) || irbidFirst(a) - irbidFirst(b) || (b.score ?? 0) - (a.score ?? 0));
    const convos = leads.filter((l) => ["contacted", "replied", "meeting", "won", "lost"].includes(l.status));
    return { reply, followup, nextStep, signals, closing, fresh, convos };
  }, [allLeads, contactedEmails]);

  const filtered = (L: Lead[]) => L.filter((l) => !kind || l.kind === kind);
  const found = useMemo(() => {
    if (!q.trim()) return null;
    const s = q.toLowerCase();
    return leads.filter((l) => [l.name, l.category, l.city, l.email, l.profile?.summary].some((x) => x?.toLowerCase().includes(s)));
  }, [leads, q]);

  /** Written on the PC (free): signals first, then the best analysed, then not-yet-analysed (the PC analyses each before writing). */
  const localBatch = async (n: number) => {
    if (!agent?.online) toast.push("⚠️ الوكيل متوقف — ستُكتب عند تشغيل run.bat", "info");
    const queued = new Set(approvals.map((a) => a.lead_id));
    const targets = [...groups.signals.filter((l) => l.status === "new"), ...groups.fresh]
      .filter((l, i, a) => a.indexOf(l) === i && !queued.has(l.id) && !touched.has(l.id) && !alreadyMailed(l) && !!l.email && (!kind || l.kind === kind)).slice(0, n);
    for (const l of targets) await act.requestLocalWrite(l.id, "email");
    toast.push(`💻 ${targets.length} رسائل في طابور جهازك — تصلك على Telegram تباعاً`);
  };

  const importFile = async (f: File) => {
    try {
      const rows = JSON.parse(await f.text());
      const r = await act.importRows(Array.isArray(rows) ? rows : rows.leads);
      toast.push(`أُضيف ${r.inserted} جديد، ودُمج ${r.merged} مكرر`);
    } catch (e) {
      toast.push((e as Error).message, "error");
    }
  };

  const won = leads.filter((l) => l.status === "won");
  const stats = {
    contacted: groups.convos.length,
    replied: leads.filter((l) => ["replied", "meeting", "won"].includes(l.status)).length,
    revenue: won.reduce((s, l) => s + (Number(l.deal_value) || 0), 0),
    pipeline: leads.filter((l) => ["replied", "meeting"].includes(l.status)).reduce((s, l) => s + (Number(l.deal_value) || 0), 0),
  };
  const todayCount = groups.reply.length + approvals.length + groups.followup.length + groups.nextStep.length + groups.closing.length;
  const go = (v: View) => { setView(v); setLimit(100); setQ(""); };
  const tab = (v: View, label: string, n?: number) => (
    <button onClick={() => go(v)} className={`px-3 py-1.5 rounded text-sm ${view === v && !found ? "bg-primary text-primary-foreground" : "border border-border"}`}>
      {label}{n != null ? ` (${n})` : ""}
    </button>
  );

  /** "Done" on a Today item: it leaves the list (a reply answered elsewhere, a follow-up not needed). */
  const done = (l: Lead) => act.update(l.id, l.needs_reply ? { needs_reply: false } : { next_action_at: null })
    .then(() => toast.push(`✓ ${l.name}`), (e) => toast.push((e as Error).message, "error"));
  const row = (l: Lead, extra?: ReactNode, doneBtn = false) => (
    <tr key={l.id} onClick={() => setSel(l.id)} className={`cursor-pointer border-b border-border hover:bg-muted ${sel === l.id ? "bg-muted" : ""}`}>
      <td className="p-2">
        <div className="font-medium">{l.name}</div>
        {extra}
        <div className="text-xs text-muted-foreground">{KIND_LABEL[l.kind]}{l.city ? ` · ${l.city}` : ""}</div>
      </td>
      <td className="p-2 text-xs w-24 text-muted-foreground">{STATUS_LABEL[l.status]}</td>
      {doneBtn && <td className="p-2 w-16"><button className={btn} onClick={(e) => { e.stopPropagation(); done(l); }}>✓ تم</button></td>}
    </tr>
  );
  const lastLine = (l: Lead) => {
    const m = last[l.id];
    return m ? <div className="text-xs text-muted-foreground">{m.direction === "in" ? "💬 ردّوا" : "📤 أرسلنا"} عبر {m.channel} · قبل {daysAgo(m.created_at)} يوم</div> : null;
  };
  const table = (L: Lead[], extra?: (l: Lead) => ReactNode, doneBtn = false) => (
    <>
      <table className="w-full text-sm"><tbody>{L.slice(0, limit).map((l) => row(l, extra?.(l), doneBtn))}</tbody></table>
      {L.length > limit && <button className="m-3 underline text-sm" onClick={() => setLimit(limit + 200)}>عرض المزيد ({L.length - limit})</button>}
    </>
  );
  const section = (title: string, L: Lead[], extra?: (l: Lead) => ReactNode, doneBtn = true) =>
    L.length > 0 && (
      <div key={title}>
        <h3 className="px-3 pt-4 pb-1 text-sm font-semibold">{title} ({L.length})</h3>
        {table(L, extra, doneBtn)}
      </div>
    );
  const signalLine = (l: Lead) => l.signal && <div className="text-xs text-amber-600">{l.signal}{l.signal_until ? ` — ${l.signal_until}` : ""}</div>;

  const main = (() => {
    if (found) return (<><h3 className="px-3 pt-3 text-sm text-muted-foreground">نتائج البحث عن «{q}» في كل البيانات ({found.length})</h3>{table(found, lastLine)}</>);
    if (view === "today") {
      const radarNote = radarClosing.length > 0 && (
        <div className="m-3 rounded border border-amber-500/50 bg-amber-500/10 p-3 flex items-center justify-between gap-2 text-sm">
          <span>🏆 {radarClosing.length} مسابقة أو منحة تُغلق خلال 14 يوماً، أقربها: {radarClosing.sort((a, b) => (daysLeft(a.deadline) ?? 99) - (daysLeft(b.deadline) ?? 99))[0].title}</span>
          <button className={btn} onClick={() => go("opps")}>افتح الفرص</button>
        </div>
      );
      return todayCount === 0 ? <>{radarNote}<p className="p-6 text-muted-foreground">✨ لا شيء ينتظرك اليوم. اذهب إلى «🎯 الجدد» لتكتب لأفضل 10.</p></> : (
        <>
          {radarNote}
          {section("🔥 ردود تنتظر جوابك", groups.reply, lastLine)}
          {approvals.length > 0 && (
            <div className="m-3 rounded border border-amber-500/50 bg-amber-500/10 p-3 flex items-center justify-between gap-2 text-sm">
              <span>📤 {approvals.length} مسودة بانتظار موافقتك (أو على Telegram)</span>
              <button className={btn} onClick={() => go("approvals")}>راجعها</button>
            </div>
          )}
          {section("↩️ متابعات حان موعدها", groups.followup, lastLine)}
          {section("🤝 خطوة تالية مع من ردّوا", groups.nextStep, lastLine)}
          {section("⚠️ فرص تُغلق خلال 7 أيام", groups.closing, signalLine, false)}
        </>
      );
    }
    if (view === "opps") return (
      <>
        <h3 className="px-3 pt-4 pb-1 text-sm font-semibold">🔔 منظمات وعطاءات تحتاج تصويراً ({groups.signals.length})</h3>
        {groups.signals.length ? table(groups.signals, signalLine) : <p className="px-3 text-sm text-muted-foreground">لا شيء مفتوح الآن.</p>}
        <h3 className="px-3 pt-6 pb-1 text-sm font-semibold">🏆 منح وجوائز وإقامات ومسابقات ({radarOpen})</h3>
        <Radar />
      </>
    );
    if (view === "nas") {
      const queued = new Set(approvals.map((a) => a.lead_id));
      const todo = nasLeads.filter((l) => l.status === "new" && !queued.has(l.id) && !touched.has(l.id));
      const sent = nasLeads.filter((l) => l.status !== "new");
      const nasLine = (l: Lead) => (
        <>
          <div className="text-xs text-muted-foreground">{l.category}</div>
          <div className="text-xs">{l.profile?.nas ? `يطلب منه: ${NAS_ASK_LABEL[l.profile.nas.ask] ?? l.profile.nas.ask} · ما يحبه: ${l.profile.nas.love}` : null}</div>
          <div className="text-xs">{l.email ? `✉️ ${l.email}` : "⚠️ لا إيميل بعد، سيبحث عنه الوكيل عند الكتابة"}</div>
        </>
      );
      return (
        <>
          <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
            <button className="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm" onClick={async () => {
              const targets = todo.filter((l) => l.profile?.tier !== "C").slice(0, 5);
              if (!agent?.online) toast.push("⚠️ الوكيل متوقف — ستُكتب عند تشغيل run.bat", "info");
              for (const l of targets) await act.requestLocalWrite(l.id, "email");
              toast.push(`💻 ${targets.length} رسائل ناس إربد في طابور جهازك — تصلك على Telegram`);
            }}>✍️ اكتب لأقوى 5 رعاة</button>
            <a className="underline text-sm" href={NAS_SITE} target="_blank" rel="noreferrer">موقع البرنامج</a>
            <span className="text-xs text-muted-foreground">كل رسالة تحمل رابط الموقع وحلقة تناسب صاحبها، ولا يُرسل شيء قبل موافقتك</span>
          </div>
          {section("🔥 ردّوا وينتظرون جوابك", nasLeads.filter((l) => l.needs_reply), lastLine)}
          {section("🎯 لم نراسلهم بعد", todo, nasLine, false)}
          {section("📤 راسلناهم", sent.filter((l) => !l.needs_reply), lastLine, false)}
        </>
      );
    }
    // view === "new"
    const L = filtered(groups.fresh);
    return (
      <>
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
          <select className="rounded border border-border bg-background px-2 py-1.5 text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">كل الأنواع</option>
            {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <button className="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm" onClick={() => localBatch(10)}>
            ✍️ اكتب لأفضل 10 لم نراسلهم
          </button>
          <span className="text-xs text-muted-foreground">تصلك المسودات على Telegram، ولا يُرسل شيء قبل موافقتك</span>
        </div>
        {table(L.filter((l) => l.email))}
      </>
    );
  })();

  /** Conversations: one column per stage, the newest exchange first. */
  const board = (
    <div className="flex gap-3 p-3 overflow-x-auto md:h-[calc(100vh-100px)]">
      {STAGES.map(({ status, label }) => {
        const L = groups.convos.filter((l) => l.status === status)
          .sort((a, b) => (last[b.id]?.created_at ?? "").localeCompare(last[a.id]?.created_at ?? ""));
        return (
          <div key={status} className="min-w-[230px] w-[230px] shrink-0 flex flex-col rounded border border-border">
            <div className="p-2 text-sm font-semibold border-b border-border">{label} ({L.length})</div>
            <div className="overflow-auto p-2 space-y-2">
              {L.map((l) => <Card key={l.id} l={l} m={last[l.id]} active={sel === l.id} onOpen={() => setSel(l.id)} />)}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div dir="rtl" className="min-h-screen bg-background text-foreground">
      <header className="flex flex-wrap items-center gap-4 border-b border-border px-4 py-2 text-sm">
        <b>FAII Sales</b>
        <div className="flex-1" />
        <span title="وكيل الجهاز: يكتب ويحلّل ويرسل">{agent?.online ? "🟢 الوكيل شغّال" : "🔴 الوكيل متوقف"}</span>
        <Link to="/settings" className="underline">الإعدادات</Link>
        <button className="underline" onClick={() => signOut()}>خروج</button>
      </header>

      <div className="flex flex-wrap items-center gap-2 px-4 py-2 border-b border-border">
        {tab("today", "✅ اليوم", todayCount)}
        {tab("convos", "💬 المحادثات", groups.convos.length)}
        {tab("new", "🎯 الجدد", groups.fresh.length)}
        {tab("opps", "🔔 الفرص", groups.signals.length + radarOpen)}
        {tab("nas", "🎬 ناس إربد", nasLeads.length)}
        <div className="flex-1" />
        <input className="rounded border border-border bg-background px-2 py-1.5 text-sm w-48" placeholder="🔍 بحث في كل البيانات" value={q} onChange={(e) => setQ(e.target.value)} />
        {tab("stats", "📊 القياس")}
        <details className="relative">
          <summary className={`${btn} cursor-pointer list-none`}>⋯ أدوات</summary>
          <div className="absolute left-0 z-10 mt-1 flex w-64 flex-col gap-2 rounded border border-border bg-background p-2 shadow">
            <AddLead onAdded={(name) => setQ(name)} />
            <button className={btn} onClick={() => fileRef.current?.click()}>⬆️ استيراد من الجامع</button>
          </div>
        </details>
        <input ref={fileRef} type="file" accept=".json" hidden onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])} />
      </div>

      {view === "stats" && !found ? (
        <>
          <p className="px-4 pt-3 text-sm text-muted-foreground">تواصلنا مع {stats.contacted} · ردّ {stats.replied} · صفقات {won.length} ({stats.revenue} د.أ) · قيد التفاوض {stats.pipeline} د.أ</p>
          <Funnel leads={leads} /><ReplyLessons />
        </>
      )
      : view === "approvals" && !found ? (
        <>
          <button className="m-3 underline text-sm" onClick={() => go("today")}>→ رجوع إلى اليوم</button>
          <Approvals items={approvals} onOpen={(id) => { setSel(id); go("convos"); }} />
        </>
      ) : (
        <div className={`grid ${sel ? "md:grid-cols-[1fr_520px]" : ""}`}>
          <div className="overflow-auto md:h-[calc(100vh-100px)]">
            {isLoading && <p className="p-4 text-muted-foreground">...</p>}
            {error && <p className="p-4 text-red-600">خطأ في قراءة البيانات: {(error as Error).message}</p>}
            {view === "convos" && !found ? board : main}
          </div>
          {sel && (
            <aside className="border-r border-border md:h-[calc(100vh-100px)] overflow-auto">
              <button className="m-2 text-xs underline" onClick={() => setSel(null)}>✕ إغلاق</button>
              <LeadPanel key={sel} id={sel} onDeleted={() => setSel(null)} />
            </aside>
          )}
        </div>
      )}
    </div>
  );
}

function Card({ l, m, active, onOpen }: { l: Lead; m?: LastMessage; active: boolean; onOpen: () => void }) {
  const t = today();
  const due = l.next_action_at && l.next_action_at <= t;
  return (
    <button onClick={onOpen} className={`w-full text-start rounded border p-2 text-xs space-y-0.5 hover:bg-muted ${active ? "bg-muted" : ""} ${l.needs_reply ? "border-red-500/60" : due ? "border-amber-500/60" : "border-border"}`}>
      <div className="font-medium text-sm">{l.needs_reply && "🔥 "}{l.name}</div>
      <div className="text-muted-foreground">{KIND_LABEL[l.kind]}</div>
      {m && <div>{m.direction === "in" ? "💬 ردّوا" : "📤 أرسلنا"} · {m.channel} · قبل {daysAgo(m.created_at)} يوم</div>}
      {l.needs_reply ? <div className="text-red-600">ينتظر جوابك</div>
        : l.next_action_at && <div className={due ? "text-amber-600" : "text-muted-foreground"}>الخطوة التالية: {l.next_action_at}</div>}
      {l.deal_value ? <div>💰 {l.deal_value} د.أ</div> : null}
    </button>
  );
}
