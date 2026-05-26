import { Building2, Crown, Send, Target, Zap, TrendingUp } from "lucide-react";

interface Props {
  total: number;
  premium: number;
  contacted: number;
  meetings: number;
  today: number;
  goal: number;
}

export function AnalyticsBar({ total, premium, contacted, meetings, today, goal }: Props) {
  const conv = contacted > 0 ? ((meetings / contacted) * 100).toFixed(1) : "0";
  const goalPct = Math.min(100, Math.round((today / goal) * 100));
  const cards = [
    { icon: Building2, label: "إجمالي المطاعم", value: total.toLocaleString("ar"), tone: "default" as const },
    { icon: Crown, label: "Premium", value: premium.toLocaleString("ar"), tone: "gold" as const },
    { icon: Send, label: "تم التواصل", value: contacted.toLocaleString("ar"), tone: "emerald" as const },
    { icon: Target, label: "نسبة التحويل", value: `${conv}%`, tone: "gold" as const },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
      {cards.map(({ icon: Icon, label, value, tone }) => (
        <Card key={label} tone={tone}>
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] tracking-widest uppercase text-muted-foreground">
                {label}
              </div>
              <div
                className={`text-2xl font-extrabold mt-1 tabular-nums ${
                  tone === "gold" ? "text-gold" : tone === "emerald" ? "text-emerald" : "text-foreground"
                }`}
              >
                {value}
              </div>
            </div>
            <IconBadge tone={tone}>
              <Icon className="w-4 h-4" />
            </IconBadge>
          </div>
        </Card>
      ))}

      {/* Daily goal card spans 2 cols */}
      <div className="col-span-2 relative overflow-hidden rounded-xl border border-border bg-card px-5 py-4">
        <div className="flex items-start justify-between mb-2">
          <div>
            <div className="text-[11px] tracking-widest uppercase text-muted-foreground flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-gold" /> هدف اليوم
            </div>
            <div className="text-2xl font-extrabold mt-1 tabular-nums">
              <span className={today >= goal ? "text-emerald" : "text-foreground"}>
                {today.toLocaleString("ar")}
              </span>
              <span className="text-muted-foreground text-base mx-1">/</span>
              <span className="text-muted-foreground text-base">{goal}</span>
            </div>
          </div>
          <IconBadge tone={today >= goal ? "emerald" : "gold"}>
            <TrendingUp className="w-4 h-4" />
          </IconBadge>
        </div>
        <div className="h-1.5 rounded-full bg-surface-2 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              today >= goal ? "bg-emerald" : "bg-gold"
            }`}
            style={{ width: `${goalPct}%` }}
          />
        </div>
        <div className="mt-1.5 text-[10px] text-muted-foreground">
          {today >= goal ? "🎬 أحسنت! تم تحقيق هدف اليوم" : `بقي ${goal - today} للوصول للهدف`}
        </div>
      </div>
    </div>
  );
}

function Card({ children, tone }: { children: React.ReactNode; tone: string }) {
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-card px-5 py-4">
      {children}
      <div
        className={`absolute -bottom-8 -left-8 w-24 h-24 rounded-full opacity-20 blur-2xl ${
          tone === "gold" ? "bg-gold" : tone === "emerald" ? "bg-emerald" : "bg-muted-foreground"
        }`}
      />
    </div>
  );
}

function IconBadge({ children, tone }: { children: React.ReactNode; tone: string }) {
  return (
    <div
      className={`w-9 h-9 rounded-lg flex items-center justify-center ${
        tone === "gold"
          ? "bg-gold-soft text-gold"
          : tone === "emerald"
          ? "bg-emerald-soft text-emerald"
          : "bg-accent text-muted-foreground"
      }`}
    >
      {children}
    </div>
  );
}
