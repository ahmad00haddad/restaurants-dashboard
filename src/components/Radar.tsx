import { useMemo, useState } from "react";
import { useOpportunities, useOpportunityActions } from "@/hooks/useOpportunities";
import { useToast } from "@/hooks/useToast";
import {
  OPP_FIELD_LABEL, OPP_KIND_LABEL, OPP_SCOPE_LABEL, OPP_STATUS_LABEL, daysLeft, isActiveOpp, sortOpps,
  type OppKind, type OppStatus, type Opportunity,
} from "@/lib/opportunities";

const ACTION_LABEL: Record<OppStatus, string> = { new: "↺ جديد", saved: "⭐ احفظ", applying: "✍️ أقدّم", submitted: "📨 قدّمت", won: "🏆 فزت", skip: "✖ تجاهل" };
const sel = "rounded border border-border bg-background px-2 py-1.5 text-sm";
const btn = "px-2 py-1 rounded border border-border text-xs hover:bg-muted";

function Deadline({ o }: { o: Opportunity }) {
  const d = daysLeft(o.deadline);
  if (d == null) return <span className="text-xs text-muted-foreground">الموعد غير معروف: تحقق من الموقع</span>;
  const color = d < 0 ? "text-muted-foreground line-through" : d <= 7 ? "text-red-600 font-semibold" : d <= 21 ? "text-amber-600 font-semibold" : "text-foreground";
  return <span className={`text-xs ${color}`}>{d < 0 ? "انتهى" : d === 0 ? "يُغلق اليوم" : `يُغلق بعد ${d} يوم`} · {o.deadline}</span>;
}

function Row({ o, open, onToggle }: { o: Opportunity; open: boolean; onToggle: () => void }) {
  const act = useOpportunityActions();
  const toast = useToast();
  const [notes, setNotes] = useState(o.notes ?? "");
  const set = (s: OppStatus) => act.setStatus(o.id, s).catch((e) => toast.push((e as Error).message, "error"));
  return (
    <div className={`border-b border-border p-3 text-sm ${o.status === "skip" ? "opacity-50" : ""}`}>
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <button className="text-start font-medium hover:underline" onClick={onToggle}>
            {o.fit != null && o.fit >= 75 && "⭐ "}{o.title}
          </button>
          <div className="text-xs text-muted-foreground">
            {OPP_KIND_LABEL[o.kind]} · {OPP_SCOPE_LABEL[o.scope]} · {OPP_FIELD_LABEL[o.field]}{o.organizer ? ` · ${o.organizer}` : ""}
          </div>
          <div className="mt-0.5"><Deadline o={o} /></div>
          {(o.prize || o.fee) && (
            <div className="text-xs">{o.prize ? `🏅 ${o.prize}` : ""}{o.prize && o.fee ? " · " : ""}{o.fee ? `💳 ${o.fee}` : ""}</div>
          )}
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {o.fit != null && <span className="text-xs text-muted-foreground" title="ملاءمة لك (0-100)">ملاءمة {o.fit}</span>}
          <span className="text-xs rounded bg-muted px-2 py-0.5">{OPP_STATUS_LABEL[o.status]}</span>
        </div>
      </div>
      {open && (
        <div className="mt-2 space-y-2 rounded bg-muted/40 p-2">
          {o.description && <p>{o.description}</p>}
          {o.eligibility && <p className="text-xs">🎯 الأهلية: {o.eligibility}</p>}
          {o.evidence && <p className="text-xs text-muted-foreground">دليل من المصدر: «{o.evidence}»</p>}
          <p className="text-[11px] text-muted-foreground">
            {o.source === "seed" ? "برنامج دوري معروف" : o.source === "manual" ? "أضفته أنت" : "وجده الرادار"}
            {o.last_checked ? ` · فُحصت الصفحة ${o.last_checked}` : ""} · تحقّق دائماً من الصفحة الرسمية قبل التقديم
          </p>
          <textarea className={`${sel} w-full`} rows={2} placeholder="ملاحظاتك: أي عمل أقدّم؟ ما الناقص؟" value={notes}
            onChange={(e) => setNotes(e.target.value)} onBlur={() => notes !== (o.notes ?? "") && act.setNotes(o.id, notes)} />
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {o.url && <a className={btn} href={o.url} target="_blank" rel="noreferrer">🔗 الصفحة الرسمية</a>}
        {(["saved", "applying", "submitted", "won", "skip"] as OppStatus[]).filter((s) => s !== o.status).map((s) => (
          <button key={s} className={btn} onClick={() => set(s)}>{ACTION_LABEL[s]}</button>
        ))}
        {o.status !== "new" && <button className={btn} onClick={() => set("new")}>↺ أعد للجدد</button>}
      </div>
    </div>
  );
}

function AddManual() {
  const act = useOpportunityActions();
  const toast = useToast();
  const [f, setF] = useState({ title: "", url: "", deadline: "", kind: "competition" as OppKind });
  return (
    <details className="relative">
      <summary className={`${btn} cursor-pointer list-none`}>＋ أضف فرصة</summary>
      <div className="absolute right-0 z-10 mt-1 flex w-72 flex-col gap-2 rounded border border-border bg-background p-2 shadow">
        <input className={sel} placeholder="الاسم" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} />
        <input className={sel} placeholder="رابط الصفحة" value={f.url} onChange={(e) => setF({ ...f, url: e.target.value })} />
        <input className={sel} type="date" value={f.deadline} onChange={(e) => setF({ ...f, deadline: e.target.value })} />
        <select className={sel} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as OppKind })}>
          {Object.entries(OPP_KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <button className="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm" disabled={!f.title.trim()} onClick={() =>
          act.add({ title: f.title.trim(), url: f.url.trim() || null, deadline: f.deadline || null, kind: f.kind, field: "both", scope: "international" })
            .then(() => { setF({ title: "", url: "", deadline: "", kind: "competition" }); toast.push("أُضيفت الفرصة"); }, (e) => toast.push((e as Error).message, "error"))}>
          حفظ
        </button>
      </div>
    </details>
  );
}

export function Radar() {
  const { data: opps = [], isLoading, error } = useOpportunities();
  const [kind, setKind] = useState("");
  const [scope, setScope] = useState("");
  const [field, setField] = useState("");
  const [show, setShow] = useState<"active" | "mine" | "all">("active");
  const [open, setOpen] = useState<string | null>(null);

  const list = useMemo(() => opps
    .filter((o) => (!kind || o.kind === kind) && (!scope || o.scope === scope) && (!field || o.field === field || o.field === "both"))
    .filter((o) => show === "all" ? true : show === "mine" ? ["saved", "applying", "submitted", "won"].includes(o.status) : isActiveOpp(o))
    .sort(sortOpps), [opps, kind, scope, field, show]);

  const closing = opps.filter((o) => isActiveOpp(o) && (daysLeft(o.deadline) ?? 99) <= 14).length;
  const applying = opps.filter((o) => o.status === "applying").length;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 p-3 border-b border-border">
        <select className={sel} value={show} onChange={(e) => setShow(e.target.value as typeof show)}>
          <option value="active">المفتوحة</option>
          <option value="mine">ما حفظته وقدّمت عليه</option>
          <option value="all">الكل (حتى المنتهية والمتجاهلة)</option>
        </select>
        <select className={sel} value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="">عالمي + عربي + الأردن</option>
          {Object.entries(OPP_SCOPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className={sel} value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">كل الأنواع</option>
          {Object.entries(OPP_KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className={sel} value={field} onChange={(e) => setField(e.target.value)}>
          <option value="">تصوير + سينما</option>
          <option value="photo">فوتوغراف</option>
          <option value="film">سينما / فيديو</option>
        </select>
        <AddManual />
        <span className="text-xs text-muted-foreground">
          {closing > 0 && <b className="text-amber-600">⏰ {closing} تُغلق خلال 14 يوماً · </b>}
          {applying > 0 && <>✍️ {applying} تقدّم عليها · </>}
          {list.length} فرصة
        </span>
      </div>
      {isLoading && <p className="p-4 text-muted-foreground">...</p>}
      {error && <p className="p-4 text-red-600">خطأ في قراءة الفرص: {(error as Error).message}</p>}
      {!isLoading && !error && opps.length === 0 && (
        <p className="p-6 text-muted-foreground">
          لا فرص بعد. الرادار يبحث كل صباح من الوكيل (أو أرسل /radar على Telegram)، وتظهر البرامج المعروفة بعد تطبيق تحديث قاعدة البيانات.
        </p>
      )}
      {list.map((o) => <Row key={o.id} o={o} open={open === o.id} onToggle={() => setOpen(open === o.id ? null : o.id)} />)}
    </div>
  );
}
