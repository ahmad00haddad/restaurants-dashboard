import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { KIND_LABEL, tierOf, type Lead } from "@/lib/leads";

const db = supabase as any;

interface Row { label: string; contacted: number; replied: number; meeting: number; won: number }

const pct = (a: number, b: number) => (b ? `${((a / b) * 100).toFixed(1)}%` : "—");

/** Funnel per group: contacted → replied → meeting → won. Status is the source of truth; no tracking pixels. */
function table(title: string, rows: Row[]) {
  return (
    <section className="mb-6">
      <h3 className="font-semibold mb-2">{title}</h3>
      <table className="w-full text-sm border border-border">
        <thead className="bg-muted/40">
          <tr className="text-right">
            <th className="p-2">المجموعة</th><th className="p-2">تواصلنا</th><th className="p-2">ردّوا</th>
            <th className="p-2">نسبة الرد</th><th className="p-2">اجتماع</th><th className="p-2">صفقة</th><th className="p-2">نسبة الإغلاق</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-t border-border">
              <td className="p-2">{r.label}</td><td className="p-2">{r.contacted}</td><td className="p-2">{r.replied}</td>
              <td className="p-2 font-medium">{pct(r.replied, r.contacted)}</td><td className="p-2">{r.meeting}</td>
              <td className="p-2">{r.won}</td><td className="p-2 font-medium">{pct(r.won, r.contacted)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function group(leads: Lead[], key: (l: Lead) => string, label: (k: string) => string): Row[] {
  const m = new Map<string, Row>();
  for (const l of leads) {
    if (["new", "skip"].includes(l.status)) continue; // not contacted yet
    const k = key(l);
    const r = m.get(k) ?? { label: label(k), contacted: 0, replied: 0, meeting: 0, won: 0 };
    r.contacted++;
    if (["replied", "meeting", "won"].includes(l.status) || l.needs_reply) r.replied++;
    if (["meeting", "won"].includes(l.status)) r.meeting++;
    if (l.status === "won") r.won++;
    m.set(k, r);
  }
  return [...m.values()].sort((a, b) => b.contacted - a.contacted);
}

export function Funnel({ leads }: { leads: Lead[] }) {
  const { data: sent = {} } = useQuery({
    queryKey: ["sent-per-day"],
    refetchInterval: 60_000,
    queryFn: async (): Promise<Record<string, number>> => {
      const since = new Date(Date.now() - 14 * 864e5).toISOString();
      const out: Record<string, number> = {};
      for (let from = 0; ; from += 1000) {
        const { data, error } = await db.from("lead_messages").select("created_at")
          .eq("direction", "out").eq("draft", false).gte("created_at", since).range(from, from + 999);
        if (error) throw error;
        for (const m of data ?? []) out[m.created_at.slice(0, 10)] = (out[m.created_at.slice(0, 10)] ?? 0) + 1;
        if (!data || data.length < 1000) break;
      }
      return out;
    },
  });

  const total = group(leads, () => "all", () => "الكل")[0];
  const days = Array.from({ length: 14 }, (_, i) => new Date(Date.now() - i * 864e5).toISOString().slice(0, 10));
  const reachableNew = leads.filter((l) => l.status === "new" && (l.email || l.phone)).length;

  return (
    <div className="p-4 max-w-4xl">
      <p className="mb-4 text-sm text-muted-foreground">
        {total ? `من ${total.contacted} تواصلنا معهم: ردّ ${total.replied} (${pct(total.replied, total.contacted)})، اجتماع ${total.meeting}، صفقة ${total.won}.` : "لم نتواصل مع أحد بعد."}
        {` متبقٍ ${reachableNew} عميل جديد لديه إيميل أو هاتف.`}
        {total && total.contacted < 100 && " العيّنة أقل من 100 — لا تبنِ قراراً على هذه النسب بعد."}
      </p>
      {table("حسب نوع العميل", group(leads, (l) => l.kind, (k) => KIND_LABEL[k as keyof typeof KIND_LABEL] ?? k))}
      {table("حسب الطبقة (A أولاً)", group(leads, (l) => tierOf(l), (k) => `طبقة ${k}`).sort((a, b) => a.label.localeCompare(b.label)))}
      {table("حسب اللغة", group(leads, (l) => l.profile?.lang ?? "?", (k) => (k === "ar" ? "عربي" : k === "en" ? "إنجليزي" : "غير محدد")))}
      <section>
        <h3 className="font-semibold mb-2">المُرسل يومياً (آخر 14 يوماً)</h3>
        <div className="flex flex-wrap gap-2 text-sm">
          {days.map((d) => (
            <span key={d} className="rounded border border-border px-2 py-1">{d.slice(5)}: <b>{sent[d] ?? 0}</b></span>
          ))}
        </div>
      </section>
    </div>
  );
}
