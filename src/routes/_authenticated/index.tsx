import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useRef, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { researchLead } from "@/lib/ai.functions";
import { useLeadActions, useLeads } from "@/hooks/useLeads";
import { useToast } from "@/hooks/useToast";
import { useAuth } from "@/hooks/useAuth";
import { LeadPanel } from "@/components/LeadPanel";
import { KIND_LABEL, STATUS_LABEL, type Lead } from "@/lib/leads";

export const Route = createFileRoute("/_authenticated/")({
  head: () => ({ meta: [{ title: "FAII — Sales" }] }),
  component: Home,
});

type View = "today" | "reply" | "followup" | "best" | "all";
const today = () => new Date().toISOString().slice(0, 10);

function Home() {
  const { data: leads = [], isLoading } = useLeads();
  const act = useLeadActions();
  const toast = useToast();
  const { signOut } = useAuth();
  const research = useServerFn(researchLead);
  const fileRef = useRef<HTMLInputElement>(null);
  const [view, setView] = useState<View>("today");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const [limit, setLimit] = useState(100);
  const [bulk, setBulk] = useState<string | null>(null);

  const groups = useMemo(() => {
    const t = today();
    const reply = leads.filter((l) => l.needs_reply);
    const followup = leads.filter((l) => l.status === "contacted" && l.next_action_at && l.next_action_at <= t && l.followups < 2);
    const meeting = leads.filter((l) => l.status === "meeting" || (l.status === "replied" && l.next_action_at && l.next_action_at <= t && !l.needs_reply));
    const best = leads.filter((l) => l.status === "new" && l.score != null && (l.email || l.phone || l.instagram));
    return { reply, followup, meeting, best };
  }, [leads]);

  const list = useMemo(() => {
    let L: Lead[] =
      view === "reply" ? groups.reply
      : view === "followup" ? groups.followup
      : view === "best" ? groups.best
      : view === "today" ? [...groups.reply, ...groups.meeting, ...groups.followup, ...groups.best.slice(0, 30)]
      : leads;
    if (kind) L = L.filter((l) => l.kind === kind);
    if (status) L = L.filter((l) => l.status === status);
    if (q) {
      const s = q.toLowerCase();
      L = L.filter((l) => [l.name, l.category, l.city, l.profile?.summary].some((x) => x?.toLowerCase().includes(s)));
    }
    return L;
  }, [leads, groups, view, kind, status, q]);

  const analyseBatch = async (n: number) => {
    const targets = leads
      .filter((l) => !l.profile && (kind ? l.kind === kind : true) && (l.email || l.phone || l.instagram))
      .sort((a, b) => Number(b.kind === "ngo") - Number(a.kind === "ngo") || Number(!!b.website) - Number(!!a.website))
      .slice(0, n);
    for (let i = 0; i < targets.length; i++) {
      setBulk(`تحليل ${i + 1}/${targets.length}: ${targets[i].name}`);
      try {
        await research({ data: { id: targets[i].id, refetch: false } });
      } catch (e) {
        toast.push((e as Error).message, "error");
        if (/رصيد|حد الاستخدام/.test((e as Error).message)) break;
      }
      if (i % 5 === 4) act.refresh();
    }
    setBulk(null);
    act.refresh();
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

  const stats = {
    total: leads.length,
    ngo: leads.filter((l) => l.kind === "ngo").length,
    analysed: leads.filter((l) => l.profile).length,
    contacted: leads.filter((l) => !["new", "skip"].includes(l.status)).length,
    replied: leads.filter((l) => ["replied", "meeting", "won"].includes(l.status)).length,
    won: leads.filter((l) => l.status === "won").length,
  };
  const tab = (v: View, label: string, n?: number) => (
    <button onClick={() => { setView(v); setLimit(100); }} className={`px-3 py-1.5 rounded text-sm ${view === v ? "bg-primary text-primary-foreground" : "border border-border"}`}>
      {label}{n != null ? ` (${n})` : ""}
    </button>
  );

  return (
    <div dir="rtl" className="min-h-screen bg-background text-foreground">
      <header className="flex flex-wrap items-center gap-4 border-b border-border px-4 py-2 text-sm">
        <b>FAII Sales</b>
        <span className="text-muted-foreground">
          {stats.total} عميل · {stats.ngo} منظمة · {stats.analysed} محلَّل · تواصلنا {stats.contacted} · ردّ {stats.replied} · صفقات {stats.won}
        </span>
        <div className="flex-1" />
        <Link to="/settings" className="underline">الإعدادات</Link>
        <button className="underline" onClick={() => signOut()}>خروج</button>
      </header>

      <div className="flex flex-wrap items-center gap-2 px-4 py-2 border-b border-border">
        {tab("today", "اليوم")}
        {tab("reply", "🔥 يحتاج رد", groups.reply.length)}
        {tab("followup", "↩️ متابعات", groups.followup.length)}
        {tab("best", "🎯 أفضل جدد", groups.best.length)}
        {tab("all", "الكل", leads.length)}
        <input className="rounded border border-border bg-background px-2 py-1.5 text-sm" placeholder="بحث" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="rounded border border-border bg-background px-2 py-1.5 text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">كل الأنواع</option>
          {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className="rounded border border-border bg-background px-2 py-1.5 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">كل الحالات</option>
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <div className="flex-1" />
        <button disabled={!!bulk} className="px-3 py-1.5 rounded border border-border text-sm" onClick={() => analyseBatch(20)}>
          {bulk ?? "🧠 حلّل 20 عميل"}
        </button>
        <button className="px-3 py-1.5 rounded border border-border text-sm" onClick={() => fileRef.current?.click()}>⬆️ استيراد من الجامع</button>
        <input ref={fileRef} type="file" accept=".json" hidden onChange={(e) => e.target.files?.[0] && importFile(e.target.files[0])} />
      </div>

      <div className="grid md:grid-cols-[1fr_520px]">
        <div className="overflow-auto md:h-[calc(100vh-100px)]">
          {isLoading && <p className="p-4 text-muted-foreground">...</p>}
          {!isLoading && list.length === 0 && (
            <p className="p-4 text-muted-foreground">لا شيء هنا. استورد عملاء من الجامع أو اضغط "حلّل 20 عميل".</p>
          )}
          <table className="w-full text-sm">
            <tbody>
              {list.slice(0, limit).map((l) => (
                <tr key={l.id} onClick={() => setSel(l.id)} className={`cursor-pointer border-b border-border hover:bg-muted ${sel === l.id ? "bg-muted" : ""}`}>
                  <td className="p-2">
                    <div className="font-medium">{l.needs_reply && "🔥 "}{l.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {KIND_LABEL[l.kind]} · {l.category ?? ""} · {l.city ?? ""}
                    </div>
                    {l.profile?.angle && <div className="text-xs text-muted-foreground">💡 {l.profile.best_service}: {l.profile.angle}</div>}
                  </td>
                  <td className="p-2 text-center w-12">{l.score != null ? <b>{l.score}</b> : "—"}</td>
                  <td className="p-2 text-xs w-16 whitespace-nowrap">{l.email && "✉"} {l.phone && "☎"} {l.instagram && "IG"}</td>
                  <td className="p-2 text-xs w-20">{STATUS_LABEL[l.status]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {list.length > limit && <button className="m-3 underline text-sm" onClick={() => setLimit(limit + 200)}>عرض المزيد ({list.length - limit})</button>}
        </div>
        <aside className="border-r border-border md:h-[calc(100vh-100px)] overflow-auto">
          {sel ? <LeadPanel key={sel} id={sel} /> : <p className="p-6 text-muted-foreground">اختر عميلاً.</p>}
        </aside>
      </div>
    </div>
  );
}
