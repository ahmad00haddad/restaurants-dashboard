import { useState } from "react";
import { useLeadActions, type Approval } from "@/hooks/useLeads";
import { useToast } from "@/hooks/useToast";
import { KIND_LABEL } from "@/lib/leads";

const STATE: Record<string, string> = { write: "💻 جهازك يكتبها الآن…", pending: "بانتظار موافقتك", approved: "موافق — سيُرسلها الوكيل خلال دقيقة", failed: "فشل الإرسال" };

/** Same queue as Telegram — approve here if the phone isn't at hand. The PC agent does the actual sending. */
export function Approvals({ items, onOpen }: { items: Approval[]; onOpen: (leadId: string) => void }) {
  if (items.length === 0) return <p className="p-6 text-muted-foreground">لا شيء بانتظار الموافقة.</p>;
  return (
    <div className="max-w-3xl mx-auto p-4 space-y-4">
      <p className="text-xs text-muted-foreground">الإرسال يتم من جهازك عبر وكيل FAII (tools/agent/run.bat) — يجب أن يكون شغّالاً.</p>
      {items.map((m) => <Item key={m.id} m={m} onOpen={onOpen} />)}
    </div>
  );
}

function Item({ m, onOpen }: { m: Approval; onOpen: (id: string) => void }) {
  const act = useLeadActions();
  const toast = useToast();
  const [body, setBody] = useState(m.body);
  const [subject, setSubject] = useState(m.subject ?? "");
  const L = m.leads;
  const to = m.channel === "email" ? L.email : m.channel === "whatsapp" ? L.phone : L.instagram;
  const go = (r: "approved" | "rejected") =>
    act.review(m.id, r, body, subject || null).then(() => toast.push(r === "approved" ? "✅ تمت الموافقة" : "❌ رُفضت"), (e) => toast.push(e.message, "error"));
  return (
    <div className="rounded border border-border p-3 space-y-2 text-sm">
      <div className="flex justify-between gap-2">
        <button className="font-medium underline text-start" onClick={() => onOpen(L.id)}>{L.name}</button>
        <span className="text-xs text-muted-foreground">{KIND_LABEL[L.kind]} · {m.channel} → {to ?? "—"}</span>
      </div>
      {L.signal && <div className="text-xs text-amber-600">🔔 {L.signal}</div>}
      <div className={`text-xs ${m.review === "failed" ? "text-red-600" : "text-muted-foreground"}`}>{STATE[m.review]}{m.review_note ? `: ${m.review_note}` : ""}</div>
      {m.channel === "email" && <input className="w-full rounded border border-border bg-background px-2 py-1.5" value={subject} onChange={(e) => setSubject(e.target.value)} />}
      <textarea className="w-full rounded border border-border bg-background px-2 py-1.5" rows={7} value={body} onChange={(e) => setBody(e.target.value)} />
      {!["approved", "write"].includes(m.review) && (
        <div className="flex gap-2">
          <button className="px-3 py-1.5 rounded bg-primary text-primary-foreground" onClick={() => go("approved")}>✅ وافق وأرسل</button>
          <button className="px-3 py-1.5 rounded border border-border" onClick={() => go("rejected")}>❌ ارفض</button>
        </div>
      )}
    </div>
  );
}
