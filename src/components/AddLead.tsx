import { useState } from "react";
import { useLeadActions } from "@/hooks/useLeads";
import { useToast } from "@/hooks/useToast";
import { KIND_LABEL, type LeadKind } from "@/lib/leads";

/** Add one client by hand (a contact you met, a referral, or a test client with your own email). */
export function AddLead({ onAdded }: { onAdded: (name: string) => void }) {
  const act = useLeadActions();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", kind: "ngo" as LeadKind, email: "", phone: "", website: "", city: "", notes: "" });
  const field = "rounded border border-border bg-background px-2 py-1.5 text-sm";

  if (!open) return <button className="px-3 py-1.5 rounded border border-border text-sm" onClick={() => setOpen(true)}>➕ عميل جديد</button>;

  const save = async () => {
    if (!f.name.trim()) return toast.push("اكتب اسم الجهة", "error");
    try {
      const row = Object.fromEntries(Object.entries(f).filter(([, v]) => v.trim() !== "")) as Record<string, string>;
      const r = await act.add({ ...row, source: "manual" });
      toast.push(r.inserted ? "أُضيف ✓" : "موجود مسبقاً — حدّثت بياناته");
      onAdded(f.name.trim());
      setOpen(false);
      setF({ ...f, name: "", email: "", phone: "", website: "", city: "", notes: "" });
    } catch (e) {
      toast.push((e as Error).message, "error");
    }
  };

  return (
    <div className="fixed inset-0 z-40 bg-black/50 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
      <div dir="rtl" className="bg-background rounded border border-border p-4 w-full max-w-md space-y-2" onClick={(e) => e.stopPropagation()}>
        <b>عميل جديد</b>
        <input className={`${field} w-full`} placeholder="اسم الجهة *" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <select className={`${field} w-full`} value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value as LeadKind })}>
          {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input className={`${field} w-full`} placeholder="الإيميل" dir="ltr" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <input className={`${field} w-full`} placeholder="الهاتف" dir="ltr" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
        <input className={`${field} w-full`} placeholder="الموقع الإلكتروني" dir="ltr" value={f.website} onChange={(e) => setF({ ...f, website: e.target.value })} />
        <input className={`${field} w-full`} placeholder="المدينة" value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} />
        <textarea className={`${field} w-full`} rows={2} placeholder="ملاحظات (كيف تعرفهم، ماذا يحتاجون…)" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} />
        <div className="flex gap-2">
          <button className="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm" onClick={save}>حفظ</button>
          <button className="px-3 py-1.5 rounded border border-border text-sm" onClick={() => setOpen(false)}>إلغاء</button>
        </div>
      </div>
    </div>
  );
}
