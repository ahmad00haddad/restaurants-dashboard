import { useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { KIND_LABEL } from "@/lib/leads";

const db = supabase as any; // new table; types regenerate after Lovable syncs the migration

interface Insight {
  id: string;
  lead_kind: string | null;
  category: string;
  objection: string | null;
  lesson: string | null;
  suggestion: string | null;
  confidence: number | null;
  applied: boolean;
  created_at: string;
  leads: { name: string } | null;
}

const CATEGORY: Record<string, string> = {
  interested: "✅ مهتم", question: "❓ سؤال", meeting_request: "🤝 طلب اجتماع", not_now: "⏳ ليس الآن", no_internal_capacity: "🏢 يفعلونها داخلياً",
  no_budget: "💸 لا ميزانية", not_relevant: "🎯 لا تناسبهم", stop_contact: "🚫 اطلبوا التوقف", wrong_person: "👤 الشخص خطأ",
  auto_reply_support_desk: "📨 ردّ آلي من دعم المانحين", auto_reply_generic: "🤖 ردّ آلي", out_of_office: "🏖 خارج المكتب", other: "• أخرى",
};

export function ReplyLessons() {
  const qc = useQueryClient();
  const { data = [], error } = useQuery({
    queryKey: ["reply-insights"],
    refetchInterval: 60_000,
    retry: false,
    queryFn: async (): Promise<Insight[]> => {
      const { data, error } = await db.from("reply_insights").select("*,leads(name)").order("created_at", { ascending: false }).limit(300);
      if (error) {
        if (/relation|does not exist|schema cache/i.test(error.message)) return [];
        throw error;
      }
      return data as Insight[];
    },
  });
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const i of data) m.set(i.category, (m.get(i.category) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [data]);
  const toggle = async (i: Insight) => {
    await db.from("reply_insights").update({ applied: !i.applied }).eq("id", i.id);
    qc.invalidateQueries({ queryKey: ["reply-insights"] });
  };
  const todo = data.filter((i) => i.suggestion && !i.applied);

  return (
    <div className="p-4 space-y-3 text-sm">
      <h3 className="font-semibold">🧠 ماذا تعلّمنا من الردود</h3>
      {error && <p className="text-red-600">{(error as Error).message}</p>}
      {data.length === 0 && <p className="text-muted-foreground">لا ردود مدروسة بعد. كل ردّ يصل (حتى الآلي) يدرسه الوكيل ويكتب هنا المشكلة والدرس والتحسين المقترح.</p>}
      {counts.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {counts.map(([c, n]) => <span key={c} className="rounded border border-border px-2 py-0.5 text-xs">{CATEGORY[c] ?? c}: <b>{n}</b></span>)}
        </div>
      )}
      {todo.length > 0 && <p className="text-xs text-amber-600">{todo.length} اقتراح لتحسين النظام لم يُطبَّق بعد</p>}
      {data.map((i) => (
        <div key={i.id} className={`rounded border border-border p-2 space-y-0.5 ${i.applied ? "opacity-50" : ""}`}>
          <div className="font-medium">
            {i.leads?.name ?? "—"} <span className="text-xs text-muted-foreground">· {i.lead_kind ? KIND_LABEL[i.lead_kind as keyof typeof KIND_LABEL] ?? i.lead_kind : ""} · {i.created_at.slice(0, 10)}</span>
          </div>
          <div className="text-xs">{CATEGORY[i.category] ?? i.category}{i.objection ? ` — ${i.objection}` : ""}</div>
          {i.lesson && <div className="text-xs text-muted-foreground">📘 {i.lesson}</div>}
          {i.suggestion && (
            <div className="text-xs flex items-start gap-2">
              <span className="flex-1">🔧 {i.suggestion}</span>
              <button className="underline shrink-0" onClick={() => toggle(i)}>{i.applied ? "↺ لم يُطبَّق" : "✔ طُبّق"}</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
