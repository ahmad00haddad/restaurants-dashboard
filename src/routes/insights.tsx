import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo } from "react";
import { useCrmStore } from "@/hooks/useCrmStore";
import { useRestaurants } from "@/hooks/useRestaurants";
import { SEGMENT_META, STATUS_META, type Status, type Segment } from "@/lib/restaurants";
import { ArrowRight, BarChart3, Calendar, Crown, Send, Target, TrendingUp, Tag } from "lucide-react";

export const Route = createFileRoute("/insights")({
  head: () => ({
    meta: [
      { title: "FAII HOUSE — التحليلات" },
      { name: "description", content: "تحليلات شاملة لأداء الـ Outreach ومتابعة الأهداف الأسبوعية والشهرية." },
    ],
  }),
  component: InsightsPage,
});

function InsightsPage() {
  const { store } = useCrmStore();
  const RESTAURANTS = useRestaurants();

  const segmentCounts = useMemo(() => {
    const c = { premium: 0, medium: 0, testing: 0 } as Record<Segment, number>;
    for (const r of RESTAURANTS) c[r.segment]++;
    return c;
  }, [RESTAURANTS]);

  const statusCounts = useMemo(() => {
    const c = { new: 0, email: 0, whatsapp: 0, meeting: 0 } as Record<Status, number>;
    for (const r of RESTAURANTS) c[(store[r.id]?.status ?? "new") as Status]++;
    return c;
  }, [store, RESTAURANTS]);

  const categories = useMemo(() => {
    const m = new Map<string, { total: number; contacted: number }>();
    for (const r of RESTAURANTS) {
      const cur = m.get(r.category) ?? { total: 0, contacted: 0 };
      cur.total++;
      const s = store[r.id]?.status;
      if (s && s !== "new") cur.contacted++;
      m.set(r.category, cur);
    }
    return [...m.entries()]
      .map(([name, v]) => ({ name, ...v }))
      .sort((a, b) => b.total - a.total);
  }, [store, RESTAURANTS]);

  const weekly = useMemo(() => {
    // last 7 days activity
    const days: { label: string; date: string; count: number }[] = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - i);
      days.push({
        label: d.toLocaleDateString("ar-JO", { weekday: "short" }),
        date: d.toISOString().slice(0, 10),
        count: 0,
      });
    }
    for (const s of Object.values(store)) {
      for (const h of s.history ?? []) {
        if (h.status === "new") continue;
        const day = new Date(h.at).toISOString().slice(0, 10);
        const slot = days.find((x) => x.date === day);
        if (slot) slot.count++;
      }
    }
    return days;
  }, [store]);

  const maxWeekly = Math.max(1, ...weekly.map((d) => d.count));
  const totalContacted = statusCounts.email + statusCounts.whatsapp + statusCounts.meeting;
  const convRate = totalContacted > 0 ? ((statusCounts.meeting / totalContacted) * 100).toFixed(1) : "0";
  const reachPct = ((totalContacted / RESTAURANTS.length) * 100).toFixed(1);

  const { revenueTotal, pipelineTotal } = useMemo(() => {
    let r = 0, p = 0;
    for (const s of Object.values(store)) {
      const v = s.dealValue ?? 0;
      if (!v) continue;
      if (s.status === "meeting") r += v;
      else if (s.status === "whatsapp" || s.status === "email") p += v;
    }
    return { revenueTotal: r, pipelineTotal: p };
  }, [store]);

  // Top tags
  const tagCounts = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of Object.values(store)) {
      for (const t of s.tags ?? []) m.set(t, (m.get(t) ?? 0) + 1);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  }, [store]);

  const today = new Date().toISOString().slice(0, 10);
  const upcoming = useMemo(() => {
    return RESTAURANTS
      .map((r) => ({ r, fu: store[r.id]?.followUp }))
      .filter((x): x is { r: typeof x.r; fu: string } => !!x.fu)
      .sort((a, b) => a.fu.localeCompare(b.fu))
      .slice(0, 8);
  }, [store, RESTAURANTS, today]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="px-6 lg:px-12 py-8 border-b border-border bg-gradient-hero">
        <Link to="/" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-gold mb-4">
          <ArrowRight className="w-3.5 h-3.5" />
          العودة للوحة
        </Link>
        <h1 className="text-3xl font-extrabold tracking-tight flex items-center gap-3">
          <BarChart3 className="w-7 h-7 text-gold" />
          لوحة التحليلات
        </h1>
        <p className="text-sm text-muted-foreground mt-2">
          نظرة شاملة على أداء حملات التواصل، أفضل الفئات، الأهداف الأسبوعية، والمتابعات القادمة.
        </p>
      </header>

      <main className="px-6 lg:px-12 py-8 space-y-8 max-w-7xl mx-auto">
        {/* Headline KPIs */}
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <Kpi icon={<Send className="w-4 h-4" />} label="إجمالي التواصل" value={totalContacted} sub={`${reachPct}٪ من القاعدة`} tone="emerald" />
          <Kpi icon={<Crown className="w-4 h-4" />} label="Premium" value={segmentCounts.premium} sub="عميل عالي القيمة" tone="gold" />
          <Kpi icon={<Target className="w-4 h-4" />} label="نسبة التحويل" value={`${convRate}%`} sub="اجتماع / تواصل" tone="gold" />
          <Kpi icon={<Calendar className="w-4 h-4" />} label="اجتماعات" value={statusCounts.meeting} sub="فرصة بيع نشطة" tone="emerald" />
          <Kpi icon={<TrendingUp className="w-4 h-4" />} label="إيرادات محققة" value={`${revenueTotal.toLocaleString("ar")} د.أ`} sub="من صفقات الاجتماعات" tone="gold" />
          <Kpi icon={<TrendingUp className="w-4 h-4" />} label="حجم الـ Pipeline" value={`${pipelineTotal.toLocaleString("ar")} د.أ`} sub="فرص قيد التواصل" tone="emerald" />
        </section>

        {/* Pipeline funnel */}
        <Card title="قمع المبيعات" icon={<TrendingUp className="w-4 h-4 text-gold" />}>
          <div className="space-y-2">
            {(["new", "whatsapp", "email", "meeting"] as Status[]).map((s) => {
              const v = statusCounts[s];
              const pct = (v / RESTAURANTS.length) * 100;
              return (
                <div key={s}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="flex items-center gap-2 text-foreground">
                      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_META[s].dot}`} />
                      {STATUS_META[s].label}
                    </span>
                    <span className="tabular-nums text-muted-foreground">
                      {v.toLocaleString("ar")} • {pct.toFixed(1)}٪
                    </span>
                  </div>
                  <div className="h-2.5 rounded-full bg-surface-2 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        s === "meeting" ? "bg-gold" : s === "whatsapp" ? "bg-emerald" : s === "email" ? "bg-sky-400" : "bg-muted-foreground/60"
                      }`}
                      style={{ width: `${Math.max(2, pct)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Weekly activity */}
          <Card title="النشاط خلال آخر ٧ أيام" icon={<TrendingUp className="w-4 h-4 text-emerald" />}>
            <div className="flex items-end gap-2 h-40 px-2">
              {weekly.map((d) => (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-2">
                  <div className="text-[10px] tabular-nums text-muted-foreground">{d.count}</div>
                  <div className="w-full flex-1 flex items-end">
                    <div
                      className={`w-full rounded-t-md transition-all ${d.count > 0 ? "bg-gradient-to-t from-gold/30 to-gold" : "bg-surface-2"}`}
                      style={{ height: `${(d.count / maxWeekly) * 100}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-muted-foreground">{d.label}</div>
                </div>
              ))}
            </div>
          </Card>

          {/* Segment distribution */}
          <Card title="توزيع الشرائح" icon={<Crown className="w-4 h-4 text-gold" />}>
            <div className="space-y-3">
              {(Object.keys(SEGMENT_META) as Segment[]).map((s) => {
                const v = segmentCounts[s];
                const pct = (v / RESTAURANTS.length) * 100;
                const meta = SEGMENT_META[s];
                return (
                  <div key={s}>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold">{meta.label}</span>
                      <span className="tabular-nums text-muted-foreground">
                        {v.toLocaleString("ar")} • {pct.toFixed(0)}٪
                      </span>
                    </div>
                    <div className="h-2.5 rounded-full bg-surface-2 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          meta.color === "gold" ? "bg-gold" : meta.color === "emerald" ? "bg-emerald" : "bg-muted-foreground/60"
                        }`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-1">{meta.desc}</div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>

        {/* Top categories */}
        <Card title="أفضل الفئات أداءً" icon={<BarChart3 className="w-4 h-4 text-gold" />}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-2">
            {categories.slice(0, 12).map((c) => {
              const pct = c.total > 0 ? (c.contacted / c.total) * 100 : 0;
              return (
                <div key={c.name}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="text-foreground">{c.name}</span>
                    <span className="tabular-nums text-muted-foreground">
                      <span className="text-emerald">{c.contacted}</span> / {c.total}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
                    <div className="h-full bg-emerald rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Upcoming follow-ups */}
          <Card title="المتابعات القادمة" icon={<Calendar className="w-4 h-4 text-gold" />}>
            {upcoming.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                لا توجد متابعات مجدولة.
              </div>
            ) : (
              <div className="space-y-1.5">
                {upcoming.map(({ r, fu }) => {
                  const overdue = fu < today;
                  return (
                    <Link
                      key={r.id}
                      to="/"
                      className={`flex items-center justify-between gap-3 px-3 py-2 rounded-md border text-sm ${
                        overdue ? "border-destructive/30 bg-destructive/10" : "border-border bg-background hover:border-gold/40"
                      }`}
                    >
                      <span className="font-semibold truncate">{r.title}</span>
                      <span className={`text-[11px] tabular-nums ${overdue ? "text-destructive-foreground" : "text-gold"}`}>
                        {fu}
                      </span>
                    </Link>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Tags cloud */}
          <Card title="الوسوم الأكثر استخداماً" icon={<Tag className="w-4 h-4 text-emerald" />}>
            {tagCounts.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                أضف وسوماً للمطاعم من لوحة المطعم لتنظيم أفضل.
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {tagCounts.map(([name, count]) => {
                  const size = Math.min(20, 11 + count);
                  return (
                    <span
                      key={name}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-emerald-soft border border-emerald/30 text-emerald"
                      style={{ fontSize: `${size}px` }}
                    >
                      {name}
                      <span className="text-[10px] tabular-nums opacity-70">×{count}</span>
                    </span>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </main>
    </div>
  );
}

function Card({
  title, icon, children,
}: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 text-sm font-bold mb-4">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}

function Kpi({
  icon, label, value, sub, tone,
}: { icon: React.ReactNode; label: string; value: number | string; sub: string; tone: "gold" | "emerald" }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 relative overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="text-[11px] tracking-widest uppercase text-muted-foreground">{label}</div>
        <div className={`w-8 h-8 rounded-md flex items-center justify-center ${
          tone === "gold" ? "bg-gold-soft text-gold" : "bg-emerald-soft text-emerald"
        }`}>
          {icon}
        </div>
      </div>
      <div className={`text-3xl font-extrabold mt-2 tabular-nums ${tone === "gold" ? "text-gold" : "text-emerald"}`}>
        {typeof value === "number" ? value.toLocaleString("ar") : value}
      </div>
      <div className="text-[11px] text-muted-foreground mt-1">{sub}</div>
    </div>
  );
}
