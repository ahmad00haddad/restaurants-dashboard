import { useEffect, useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { draftMessage, researchLead } from "@/lib/ai.functions";
import { useLead, useLeadActions } from "@/hooks/useLeads";
import { useToast } from "@/hooks/useToast";
import { gmailLink, KIND_LABEL, STATUS_LABEL, waLink, type Channel, type LeadKind, type LeadStatus } from "@/lib/leads";

const btn = "px-3 py-1.5 rounded border border-border text-sm hover:bg-muted disabled:opacity-40";
const primary = "px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm disabled:opacity-40";
const field = "w-full rounded border border-border bg-background px-2 py-1.5 text-sm";

export function LeadPanel({ id }: { id: string }) {
  const { data, isLoading } = useLead(id);
  const act = useLeadActions();
  const toast = useToast();
  const research = useServerFn(researchLead);
  const draft = useServerFn(draftMessage);
  const [busy, setBusy] = useState<string | null>(null);
  const [channel, setChannel] = useState<Channel>("email");
  const [hint, setHint] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [theirs, setTheirs] = useState("");
  const [theirsCh, setTheirsCh] = useState("whatsapp");

  const lead = data?.lead;
  const msgs = data?.msgs.filter((m) => !m.draft) ?? [];
  const saved = data?.msgs.find((m) => m.draft);

  useEffect(() => {
    if (!lead) return;
    setChannel(lead.profile?.channel ?? (lead.email ? "email" : lead.phone ? "whatsapp" : "instagram"));
  }, [lead?.id]);
  useEffect(() => {
    setSubject(saved?.subject ?? "");
    setBody(saved?.body ?? "");
    if (saved) setChannel(saved.channel as Channel);
  }, [saved?.id]);

  if (isLoading || !lead) return <div className="p-6 text-muted-foreground">...</div>;
  const p = lead.profile;

  const run = async (name: string, fn: () => Promise<unknown>) => {
    setBusy(name);
    try {
      await fn();
    } catch (e) {
      toast.push((e as Error).message, "error");
    } finally {
      setBusy(null);
      act.refresh(id);
    }
  };

  const write = (mode: "first" | "followup" | "reply" | "proposal") =>
    run(mode, async () => {
      if (!lead.profile) await research({ data: { id, refetch: false } });
      const r = await draft({ data: { id, mode, channel, hint: hint || undefined } });
      setSubject(r.subject ?? "");
      setBody(r.body);
      if (r.summary) toast.push(mode === "reply" ? `${r.intent ?? ""}: ${r.summary}` : r.summary, "info");
    });

  const mode = lead.needs_reply ? "reply" : lead.status === "contacted" ? "followup" : lead.status === "new" ? "first" : "reply";

  const send = async () => {
    if (channel === "email") {
      if (!lead.email) return toast.push("لا يوجد إيميل", "error");
      window.open(gmailLink(lead.email, subject, body), "_blank");
    } else if (channel === "whatsapp") {
      if (!lead.phone) return toast.push("لا يوجد رقم", "error");
      window.open(waLink(lead.phone, body), "_blank");
    } else {
      await navigator.clipboard.writeText(body);
      toast.push("نُسخت الرسالة — الصقها في الدايركت", "info");
      if (lead.instagram) window.open(lead.instagram, "_blank");
    }
    await act.logSent(lead, channel, body, subject);
    setBody(""); setSubject(""); setHint("");
  };

  return (
    <div className="p-4 flex flex-col gap-4 text-sm">
      <div className="order-first">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{lead.name}</h2>
          {lead.score != null && <span className="rounded bg-muted px-2 text-xs font-bold">{lead.score}</span>}
        </div>
        <div className="text-muted-foreground text-xs">
          {KIND_LABEL[lead.kind]} · {lead.category ?? ""} · {lead.address ?? lead.city ?? ""} {lead.rating ? `· ★${lead.rating}` : ""}
        </div>
        <div className="flex flex-wrap gap-3 mt-1 text-xs">
          {(["website", "instagram", "facebook", "linkedin", "youtube", "tiktok", "maps_url"] as const).map((k) =>
            lead[k] ? <a key={k} className="underline" target="_blank" rel="noreferrer" href={lead[k]!.startsWith("http") ? lead[k]! : `https://${lead[k]}`}>{k.replace("_url", "")}</a> : null,
          )}
        </div>
      </div>

      {(() => {
        const last = msgs.filter((m) => m.direction === "out").at(-1);
        const theirs = msgs.filter((m) => m.direction === "in").at(-1);
        if (!last && !theirs) return null;
        const waiting = data?.msgs.find((m) => m.draft && (m as any).review === "pending");
        return (
          <div className="-order-1 rounded border border-green-600/40 bg-green-500/10 p-2 text-xs space-y-0.5">
            {last && <div>✅ أُرسلت آخر رسالة عبر {last.channel} في {last.created_at.slice(0, 16).replace("T", " ")}</div>}
            {theirs ? <div>💬 ردّوا في {theirs.created_at.slice(0, 10)}</div> : last && <div>⏳ بانتظار ردّهم{lead.next_action_at ? ` — المتابعة الهادئة يوم ${lead.next_action_at}` : ""}</div>}
            {waiting && <div>📤 هناك رسالة بانتظار موافقتك على Telegram</div>}
          </div>
        );
      })()}

      {lead.signal && (
        <div className="rounded border border-amber-500/50 bg-amber-500/10 p-2">
          🔔 <b>فرصة الآن:</b> {lead.signal}
          {lead.signal_until && <span className="text-xs"> — تُغلق {lead.signal_until}</span>}
          {lead.signal_url && <a className="underline mr-2 text-xs" target="_blank" rel="noreferrer" href={lead.signal_url}>الإعلان</a>}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2">
        <input className={field} defaultValue={lead.email ?? ""} placeholder="email" onBlur={(e) => e.target.value !== (lead.email ?? "") && act.update(id, { email: e.target.value || null })} />
        <input className={field} defaultValue={lead.phone ?? ""} placeholder="phone" onBlur={(e) => e.target.value !== (lead.phone ?? "") && act.update(id, { phone: e.target.value || null })} />
        <input className={field} defaultValue={lead.website ?? ""} placeholder="website" onBlur={(e) => e.target.value !== (lead.website ?? "") && act.update(id, { website: e.target.value || null })} />
        <input className={field} defaultValue={lead.instagram ?? ""} placeholder="instagram" onBlur={(e) => e.target.value !== (lead.instagram ?? "") && act.update(id, { instagram: e.target.value || null })} />
        <select className={field} value={lead.kind} onChange={(e) => act.update(id, { kind: e.target.value as LeadKind })}>
          {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className={field} value={lead.status} onChange={(e) => act.update(id, { status: e.target.value as LeadStatus })}>
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input className={field} type="number" defaultValue={lead.deal_value ?? ""} placeholder="قيمة الصفقة (د.أ)"
          onBlur={(e) => String(lead.deal_value ?? "") !== e.target.value && act.update(id, { deal_value: e.target.value ? Number(e.target.value) : null })} />
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          المتابعة القادمة
          <input type="date" className="rounded border border-border bg-background px-2 py-1" value={lead.next_action_at ?? ""} onChange={(e) => act.update(id, { next_action_at: e.target.value || null })} />
        </label>
      </div>

      <section className="rounded border border-border p-3 space-y-1">
        <div className="flex justify-between items-center">
          <b>ماذا نعرف عنهم</b>
          <button className={btn} disabled={!!busy} onClick={() => run("research", () => research({ data: { id, refetch: true } }))}>
            {busy === "research" ? "يبحث…" : p ? "إعادة البحث" : "ابحث وحلّل"}
          </button>
        </div>
        {p ? (
          <>
            <p>{p.summary}</p>
            {p.interests?.length > 0 && <p><span className="text-muted-foreground">يهتمون بـ:</span> {p.interests.join("، ")}</p>}
            {p.content_needs?.length > 0 && <p><span className="text-muted-foreground">يحتاجون:</span> {p.content_needs.join("، ")}</p>}
            <p><span className="text-muted-foreground">نعرض عليهم:</span> <b>{p.best_service}</b>{p.other_services?.length ? ` (وأيضاً: ${p.other_services.join("، ")})` : ""}</p>
            <p>💡 {p.angle}</p>
            {p.hook && <p><span className="text-muted-foreground">نفتح بـ:</span> {p.hook}</p>}
            <p className="text-xs text-muted-foreground">{p.decision_maker} · {p.lang} · {p.tone} · {p.why}</p>
          </>
        ) : <p className="text-muted-foreground">لم يُحلَّل بعد.</p>}
      </section>

      <section className="rounded border border-border p-3 space-y-2">
        <div className="flex flex-wrap gap-2 items-center">
          <select className="rounded border border-border bg-background px-2 py-1.5" value={channel} onChange={(e) => setChannel(e.target.value as Channel)}>
            <option value="email">إيميل</option><option value="whatsapp">واتساب</option><option value="instagram">إنستغرام</option>
          </select>
          <button className={primary} disabled={!!busy} onClick={() => write(mode)}>
            {busy && busy !== "research" ? "يكتب…" : { first: "✍️ اكتب رسالة أولى", followup: "↩️ اكتب متابعة", reply: "💬 اكتب ردّاً" }[mode]}
          </button>
          <button className={btn} disabled={!!busy} onClick={() => act.requestLocalWrite(id, channel, hint || undefined)
            .then(() => toast.push("💻 جهازك يكتبها الآن — ستصلك على Telegram خلال دقيقة"), (e) => toast.push(e.message, "error"))}>
            💻 اكتب على جهازي (مجاني)
          </button>
          {mode !== "first" && <button className={btn} disabled={!!busy} onClick={() => write("first")}>رسالة أولى جديدة</button>}
          {["replied", "meeting"].includes(lead.status) && <button className={btn} disabled={!!busy} onClick={() => write("proposal")}>📄 اكتب عرضاً</button>}
        </div>
        <input className={field} value={hint} onChange={(e) => setHint(e.target.value)} placeholder="توجيه اختياري: مثلاً 'اذكر أن عندهم ذكرى 20 سنة' أو 'اعرض تصوير المنيو'" />
        {body && (
          <>
            <p className="text-xs text-green-600">✓ الرسالة جاهزة. راجعها وعدّل ما تريد، ثم اضغط «📤 للموافقة على الهاتف» لتصلك على Telegram، أو الزر الثاني لفتحها مباشرة.</p>
            {channel === "email" && <input className={field} value={subject} onChange={(e) => setSubject(e.target.value)} />}
            <textarea className={field} rows={8} value={body} onChange={(e) => setBody(e.target.value)} />
            <button className={primary} onClick={() => act.queueForApproval(id, channel, body, subject).then(() => {
              toast.push("📤 أُرسلت للموافقة على هاتفك"); setBody(""); setSubject("");
            }, (e) => toast.push(e.message, "error"))}>📤 للموافقة على الهاتف</button>
            <button className={btn} onClick={send}>
              {channel === "email" ? "فتح في Gmail وتسجيل الإرسال" : channel === "whatsapp" ? "فتح واتساب وتسجيل الإرسال" : "نسخ + فتح إنستغرام وتسجيل الإرسال"}
            </button>
          </>
        )}
      </section>

      {/* Once we have written to them, the conversation is what matters: it moves to the top. */}
      <section className={`rounded border border-border p-3 space-y-2 ${msgs.length ? "-order-1" : ""}`}>
        <b>المحادثة</b>
        {msgs.length === 0 && <p className="text-muted-foreground">لا يوجد تواصل بعد.</p>}
        {msgs.map((m) => (
          <div key={m.id} className={`whitespace-pre-wrap border-r-2 pr-2 ${m.direction === "in" ? "border-green-600 bg-green-500/5" : "border-border"}`}>
            <div className="text-xs text-muted-foreground">{m.direction === "in" ? "هم" : "أنت"} · {m.channel} · {m.created_at.slice(0, 16).replace("T", " ")}{m.subject ? ` · ${m.subject}` : ""}</div>
            {m.body}
          </div>
        ))}
        <textarea className={field} rows={3} value={theirs} onChange={(e) => setTheirs(e.target.value)} placeholder="ردّوا؟ الصق ردّهم هنا (أو ملخص المكالمة)" />
        <div className="flex gap-2">
          <select className="rounded border border-border bg-background px-2" value={theirsCh} onChange={(e) => setTheirsCh(e.target.value)}>
            <option value="whatsapp">واتساب</option><option value="email">إيميل</option><option value="instagram">إنستغرام</option><option value="call">مكالمة</option>
          </select>
          <button className={btn} disabled={!theirs.trim() || !!busy} onClick={() => run("reply", async () => {
            await act.logTheirReply(lead, theirsCh, theirs.trim());
            setTheirs("");
            if (theirsCh !== "call") setChannel(theirsCh as Channel);
            const r = await draft({ data: { id, mode: "reply", channel: theirsCh === "call" ? channel : (theirsCh as Channel) } });
            setSubject(r.subject ?? ""); setBody(r.body);
            if (r.summary) toast.push(`${r.intent ?? ""}: ${r.summary}`, "info");
          })}>حفظ ردّهم + اكتب الجواب</button>
        </div>
      </section>

      <textarea className={field} rows={3} defaultValue={lead.notes ?? ""} placeholder="ملاحظات" onBlur={(e) => e.target.value !== (lead.notes ?? "") && act.update(id, { notes: e.target.value })} />
    </div>
  );
}
