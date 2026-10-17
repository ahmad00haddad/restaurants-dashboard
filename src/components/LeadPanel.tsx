import { useEffect, useState } from "react";
import { useLead, useLeadActions } from "@/hooks/useLeads";
import { useToast } from "@/hooks/useToast";
import { gmailLink, KIND_LABEL, STATUS_LABEL, type Channel, type LeadKind, type LeadStatus } from "@/lib/leads";

const btn = "px-3 py-1.5 rounded border border-border text-sm hover:bg-muted disabled:opacity-40";
const primary = "px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm disabled:opacity-40";
const field = "w-full rounded border border-border bg-background px-2 py-1.5 text-sm";
const LINKS = { website: "الموقع", instagram: "إنستغرام", facebook: "فيسبوك", linkedin: "لينكدإن", youtube: "يوتيوب", tiktok: "تيك توك", maps_url: "الخريطة" } as const;

/** One lead, in a fixed order: who they are, where the conversation stands, the conversation, the next message; details folded away. */
export function LeadPanel({ id, onDeleted }: { id: string; onDeleted?: () => void }) {
  const { data, isLoading } = useLead(id);
  const act = useLeadActions();
  const toast = useToast();
  const [hint, setHint] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [theirs, setTheirs] = useState("");

  const lead = data?.lead;
  const msgs = data?.msgs.filter((m) => !m.draft) ?? [];
  const saved = data?.msgs.find((m) => m.draft && (m as { review?: string }).review !== "rejected");
  const review = (saved as { review?: string } | undefined)?.review;

  useEffect(() => {
    setSubject(saved?.subject ?? "");
    setBody(saved?.body ?? "");
  }, [saved?.id, saved?.body]);

  if (isLoading || !lead) return <div className="p-6 text-muted-foreground">...</div>;
  const p = lead.profile;
  const channel = (saved?.channel as Channel) ?? "email";
  const fail = (e: unknown) => toast.push((e as Error).message, "error");
  const writeOnPc = () => act.requestLocalWrite(id, "email", hint || undefined)
    .then(() => { setHint(""); toast.push("💻 يكتبها جهازك الآن، وتصلك على Telegram للموافقة"); }, fail);
  const lastOut = msgs.filter((m) => m.direction === "out").at(-1);
  const lastIn = msgs.filter((m) => m.direction === "in").at(-1);

  return (
    <div className="p-4 flex flex-col gap-4 text-sm">
      <div>
        <h2 className="text-lg font-semibold">{lead.name}</h2>
        <div className="text-muted-foreground text-xs">{KIND_LABEL[lead.kind]}{lead.city ? ` · ${lead.city}` : ""} · {STATUS_LABEL[lead.status]}</div>
        <div className="flex flex-wrap gap-3 mt-1 text-xs">
          {lead.email && <span dir="ltr">{lead.email}</span>}
          {(Object.keys(LINKS) as (keyof typeof LINKS)[]).map((k) =>
            lead[k] ? <a key={k} className="underline" target="_blank" rel="noreferrer" href={lead[k]!.startsWith("http") ? lead[k]! : `https://${lead[k]}`}>{LINKS[k]}</a> : null,
          )}
        </div>
      </div>

      {(lastOut || lastIn || lead.signal) && (
        <div className="rounded border border-border bg-muted/40 p-2 text-xs space-y-0.5">
          {lead.signal && <div>🔔 <b>فرصة:</b> {lead.signal}{lead.signal_until ? ` — تُغلق ${lead.signal_until}` : ""} {lead.signal_url && <a className="underline" target="_blank" rel="noreferrer" href={lead.signal_url}>الإعلان</a>}</div>}
          {lastOut && <div>📤 آخر رسالة منّا: {lastOut.created_at.slice(0, 10)}</div>}
          {lastIn ? <div>💬 ردّوا: {lastIn.created_at.slice(0, 10)}</div> : lastOut && <div>⏳ لم يردّوا بعد{lead.next_action_at ? ` · المتابعة ${lead.next_action_at}` : ""}</div>}
        </div>
      )}

      {msgs.length > 0 && (
        <section className="space-y-2">
          <b>المحادثة</b>
          {msgs.map((m) => (
            <div key={m.id} className={`whitespace-pre-wrap rounded p-2 ${m.direction === "in" ? "bg-green-500/10" : "bg-muted/40"}`}>
              <div className="text-xs text-muted-foreground">{m.direction === "in" ? "هم" : "أنت"} · {m.created_at.slice(0, 16).replace("T", " ")}{m.subject ? ` · ${m.subject}` : ""}</div>
              {m.body}
            </div>
          ))}
        </section>
      )}

      <section className="rounded border border-border p-3 space-y-2">
        <b>الرسالة التالية</b>
        {saved && review === "write" ? (
          <p className="text-muted-foreground">💻 جهازك يكتبها الآن، وتصلك على Telegram.</p>
        ) : saved && body ? (
          <>
            <p className="text-xs text-muted-foreground">{review === "pending" ? "📤 بانتظار موافقتك على Telegram. يمكنك تعديلها هنا." : review === "failed" ? `⚠️ ${(saved as { review_note?: string }).review_note ?? "لم تُرسل"}` : ""}</p>
            {channel === "email" && <input className={field} value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="الموضوع" />}
            <textarea className={field} rows={9} value={body} onChange={(e) => setBody(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              <button className={primary} onClick={() => act.queueForApproval(id, channel, body, subject).then(() => toast.push("📤 أُرسلت لهاتفك للموافقة"), fail)}>📤 للموافقة على الهاتف</button>
              {lead.email && <button className={btn} onClick={async () => { window.open(gmailLink(lead.email!, subject, body), "_blank"); await act.logSent(lead, "email", body, subject); }}>فتح في Gmail وتسجيل الإرسال</button>}
            </div>
          </>
        ) : (
          <>
            <input className={field} value={hint} onChange={(e) => setHint(e.target.value)} placeholder="توجيه اختياري، مثلاً: اذكر مشروعهم الجديد للشباب" />
            <button className={primary} disabled={!lead.email} onClick={writeOnPc}>{lead.email ? "✍️ اكتب رسالة" : "لا يوجد إيميل: أضفه في التفاصيل"}</button>
          </>
        )}
        <details>
          <summary className="cursor-pointer text-xs text-muted-foreground">ردّوا بطريقة أخرى (هاتف، واتساب)؟</summary>
          <textarea className={`${field} mt-2`} rows={3} value={theirs} onChange={(e) => setTheirs(e.target.value)} placeholder="الصق ردّهم أو ملخص المكالمة" />
          <button className={`${btn} mt-1`} disabled={!theirs.trim()} onClick={() => act.logTheirReply(lead, "call", theirs.trim()).then(() => { setTheirs(""); toast.push("✓ حُفظ"); }, fail)}>حفظ</button>
        </details>
      </section>

      <details className="rounded border border-border p-3">
        <summary className="cursor-pointer font-semibold">التفاصيل والتعديل</summary>
        <div className="grid grid-cols-2 gap-2 mt-3">
          <input className={field} defaultValue={lead.email ?? ""} placeholder="الإيميل" onBlur={(e) => e.target.value !== (lead.email ?? "") && act.update(id, { email: e.target.value || null })} />
          <input className={field} defaultValue={lead.phone ?? ""} placeholder="الهاتف" onBlur={(e) => e.target.value !== (lead.phone ?? "") && act.update(id, { phone: e.target.value || null })} />
          <input className={field} defaultValue={lead.website ?? ""} placeholder="الموقع" onBlur={(e) => e.target.value !== (lead.website ?? "") && act.update(id, { website: e.target.value || null })} />
          <input className={field} type="number" defaultValue={lead.deal_value ?? ""} placeholder="قيمة الصفقة (د.أ)"
            onBlur={(e) => String(lead.deal_value ?? "") !== e.target.value && act.update(id, { deal_value: e.target.value ? Number(e.target.value) : null })} />
          <select className={field} value={lead.kind} onChange={(e) => act.update(id, { kind: e.target.value as LeadKind })}>
            {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className={field} value={lead.status} onChange={(e) => act.update(id, { status: e.target.value as LeadStatus })}>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <label className="col-span-2 flex items-center gap-2 text-xs text-muted-foreground">
            المتابعة القادمة
            <input type="date" className="rounded border border-border bg-background px-2 py-1" value={lead.next_action_at ?? ""} onChange={(e) => act.update(id, { next_action_at: e.target.value || null })} />
          </label>
        </div>
        {p?.summary && <p className="mt-3"><span className="text-muted-foreground">عنهم:</span> {p.summary}</p>}
        <textarea className={`${field} mt-3`} rows={3} defaultValue={lead.notes ?? ""} placeholder="ملاحظات" onBlur={(e) => e.target.value !== (lead.notes ?? "") && act.update(id, { notes: e.target.value })} />
        <button className="mt-3 text-xs text-red-600 underline" onClick={() => {
          if (!window.confirm(`حذف «${lead.name}» نهائياً؟ لن يُكتب له مرة أخرى.`)) return;
          act.remove(id).then(() => { toast.push("🗑 حُذف"); onDeleted?.(); }, fail);
        }}>🗑 حذف العميل</button>
      </details>
    </div>
  );
}
