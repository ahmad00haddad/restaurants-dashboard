import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  SEGMENT_META, STATUS_META, buildWhatsAppMessage, leadScore, waLink,
  type Restaurant, type Status,
} from "@/lib/restaurants";
import { useRestaurants } from "@/hooks/useRestaurants";
import { useCrmStore } from "@/hooks/useCrmStore";
import { useSettings } from "@/hooks/useSettings";
import { useToast } from "@/hooks/useToast";
import {
  Target, MessageCircle, Phone, Mail, CalendarCheck, Flame, RefreshCw,
  CheckCircle2, AlertTriangle, Star,
} from "lucide-react";

export const Route = createFileRoute("/_authenticated/plan")({
  head: () => ({
    meta: [
      { title: "خطة اليوم — FAII HOUSE CRM" },
      { name: "description", content: "قائمة اتصال يومية ذكية: أفضل العملاء المحتملين لليوم مع متابعات متأخرة وأزرار تواصل فورية." },
      { property: "og:title", content: "خطة اليوم — FAII HOUSE CRM" },
      { property: "og:description", content: "قائمة اتصال يومية ذكية لفريق مبيعات FAII HOUSE." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: PlanPage,
});

const GOAL_OPTIONS = [10, 20, 30, 50];

function PlanPage() {
  const restaurants = useRestaurants();
  const { store, getStatus, setStatus, update, todayCount } = useCrmStore();
  const { settings } = useSettings();
  const toast = useToast();
  const [goal, setGoal] = useState(20);
  const [seed, setSeed] = useState(0);

  const today = new Date().toISOString().slice(0, 10);

  const overdue = useMemo(
    () =>
      restaurants
        .filter((r) => {
          const f = store[r.id]?.followUp;
          return f && f <= today;
        })
        .sort((a, b) => (store[a.id]!.followUp! < store[b.id]!.followUp! ? -1 : 1)),
    [restaurants, store, today],
  );

  const plan = useMemo(() => {
    const overdueIds = new Set(overdue.map((r) => r.id));
    const pool = restaurants
      .filter((r) => !overdueIds.has(r.id))
      .filter((r) => (store[r.id]?.status ?? "new") === "new")
      .filter((r) => !!r.phone || !!r.email);
    const scored = pool
      .map((r) => ({
        r,
        s: leadScore(r) + (store[r.id]?.favorite ? 25 : 0),
      }))
      .sort((a, b) => b.s - a.s);
    // rotate the pool so a refresh gives a fresh batch
    const offset = (seed * goal) % Math.max(1, scored.length);
    const rotated = [...scored.slice(offset), ...scored.slice(0, offset)];
    return rotated.slice(0, Math.max(0, goal - overdue.length)).map((x) => x.r);
  }, [restaurants, store, overdue, goal, seed]);

  const list = useMemo(() => [...overdue, ...plan], [overdue, plan]);
  const doneToday = todayCount;
  const pct = Math.min(100, Math.round((doneToday / goal) * 100));

  const openWa = (r: Restaurant) => {
    if (!r.phone) return;
    window.open(waLink(r.phone, buildWhatsAppMessage(r, settings)), "_blank");
    setStatus(r.id, "whatsapp");
    toast.push(`تم فتح واتساب — ${r.title}`);
  };

  const snooze = (r: Restaurant, days: number) => {
    const d = new Date();
    d.setDate(d.getDate() + days);
    update(r.id, { followUp: d.toISOString().slice(0, 10) });
    toast.push(`تأجيل ${r.title} ${days} يوم`, "info");
  };

  return (
    <div className="min-h-screen bg-background" dir="rtl">
      <div className="max-w-5xl mx-auto px-5 py-8 space-y-6">
        <header className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-[10px] tracking-[0.3em] uppercase text-gold">FAII HOUSE</div>
            <h1 className="text-2xl font-bold text-foreground mt-1 flex items-center gap-2">
              <Target className="w-6 h-6 text-gold" /> خطة اليوم
            </h1>
            <p className="text-xs text-muted-foreground mt-1.5 leading-6">
              قائمة جاهزة للاتصال اليوم: المتابعات المتأخرة أولاً، ثم أعلى العملاء المحتملين تقييماً — بدون بحث أو فلترة.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-surface-2 p-1 rounded-md">
              {GOAL_OPTIONS.map((g) => (
                <button
                  key={g}
                  onClick={() => setGoal(g)}
                  className={`text-xs px-2.5 py-1 rounded ${goal === g ? "bg-gold text-primary-foreground font-semibold" : "text-muted-foreground hover:text-foreground"}`}
                >
                  {g}
                </button>
              ))}
            </div>
            <button
              onClick={() => setSeed((s) => s + 1)}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-md border border-border text-muted-foreground hover:text-gold hover:border-gold/40"
            >
              <RefreshCw className="w-3.5 h-3.5" /> دفعة جديدة
            </button>
          </div>
        </header>

        {/* Progress */}
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">إنجاز اليوم</span>
            <span className="tabular-nums font-bold text-foreground">
              {doneToday} / {goal}
            </span>
          </div>
          <div className="h-2 rounded-full bg-surface-2 mt-3 overflow-hidden">
            <div
              className="h-full bg-gradient-to-l from-gold to-emerald transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="text-[11px] text-muted-foreground mt-2">
            {pct >= 100 ? "🎉 أنجزت هدف اليوم بالكامل" : `متبقٍ ${Math.max(0, goal - doneToday)} تواصل للوصول للهدف`}
          </div>
        </div>

        {overdue.length > 0 && (
          <div className="flex items-center gap-2 text-xs px-4 py-3 rounded-lg border border-destructive/40 bg-destructive/10 text-foreground">
            <AlertTriangle className="w-4 h-4 text-destructive" />
            لديك {overdue.length} متابعة مستحقة اليوم أو متأخرة — تظهر أعلى القائمة.
          </div>
        )}

        <div className="space-y-2">
          {list.length === 0 && (
            <div className="text-center text-sm text-muted-foreground py-16 border border-dashed border-border rounded-xl">
              لا توجد عناصر — جرّب زيادة الهدف أو اضغط "دفعة جديدة".
            </div>
          )}
          {list.map((r, i) => {
            const st = getStatus(r.id);
            const s = store[r.id];
            const isOverdue = !!s?.followUp && s.followUp <= today;
            const score = leadScore(r);
            return (
              <div
                key={r.id}
                className={`rounded-xl border bg-card px-4 py-3 flex items-center gap-3 flex-wrap ${
                  isOverdue ? "border-destructive/40" : "border-border"
                }`}
              >
                <div className="w-7 h-7 shrink-0 rounded-full bg-surface-2 border border-border flex items-center justify-center text-[11px] tabular-nums text-muted-foreground">
                  {i + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-foreground truncate">{r.title}</span>
                    {s?.favorite && <Star className="w-3 h-3 text-gold fill-current" />}
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-border text-muted-foreground">
                      {SEGMENT_META[r.segment].label}
                    </span>
                    <span className="text-[10px] text-muted-foreground">{r.category}</span>
                    <span className="inline-flex items-center gap-1 text-[10px] text-gold">
                      <Flame className="w-3 h-3" /> {score}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[10px] text-muted-foreground">
                      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_META[st as Status].dot}`} />
                      {STATUS_META[st as Status].label}
                    </span>
                  </div>
                  <div className="text-[11px] text-muted-foreground mt-0.5 tabular-nums truncate">
                    {r.phone ?? "بدون هاتف"} {r.email ? `• ${r.email}` : ""}
                    {isOverdue ? ` • متابعة مستحقة ${s!.followUp}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => openWa(r)}
                    disabled={!r.phone}
                    title="واتساب مع رسالة جاهزة"
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md bg-emerald text-background font-semibold disabled:opacity-40"
                  >
                    <MessageCircle className="w-3.5 h-3.5" /> واتساب
                  </button>
                  {r.phone && (
                    <a
                      href={`tel:${r.phone.replace(/\s/g, "")}`}
                      title="اتصال"
                      className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-border text-muted-foreground hover:text-gold"
                    >
                      <Phone className="w-3.5 h-3.5" />
                    </a>
                  )}
                  {r.email && (
                    <a
                      href={`mailto:${r.email}`}
                      onClick={() => setStatus(r.id, "email")}
                      title="إيميل"
                      className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-border text-muted-foreground hover:text-gold"
                    >
                      <Mail className="w-3.5 h-3.5" />
                    </a>
                  )}
                  <button
                    onClick={() => { setStatus(r.id, "meeting"); toast.push("🎉 تم تسجيل اجتماع", "success"); }}
                    title="تم حجز اجتماع"
                    className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-border text-muted-foreground hover:text-gold"
                  >
                    <CalendarCheck className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => snooze(r, 3)}
                    title="تأجيل ٣ أيام"
                    className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-border text-muted-foreground hover:text-foreground text-[10px]"
                  >
                    +3
                  </button>
                  <button
                    onClick={() => { update(r.id, { followUp: undefined }); toast.push("تم وضع علامة إنجاز", "success"); }}
                    title="إنهاء / إخفاء من الخطة"
                    className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-border text-muted-foreground hover:text-emerald"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
