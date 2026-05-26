import { Building2, Crown, Send, Target } from "lucide-react";

interface Props {
  total: number;
  premium: number;
  contacted: number;
  meetings: number;
}

export function AnalyticsBar({ total, premium, contacted, meetings }: Props) {
  const conv = total > 0 ? ((meetings / Math.max(contacted, 1)) * 100).toFixed(1) : "0";
  const cards = [
    { icon: Building2, label: "إجمالي المطاعم", value: total.toLocaleString("ar"), tone: "default" },
    { icon: Crown, label: "Premium", value: premium.toLocaleString("ar"), tone: "gold" },
    { icon: Send, label: "تم التواصل", value: contacted.toLocaleString("ar"), tone: "emerald" },
    { icon: Target, label: "نسبة التحويل", value: `${conv}%`, tone: "gold" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map(({ icon: Icon, label, value, tone }) => (
        <div
          key={label}
          className="relative overflow-hidden rounded-xl border border-border bg-card px-5 py-4"
        >
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
            <div
              className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                tone === "gold"
                  ? "bg-gold-soft text-gold"
                  : tone === "emerald"
                  ? "bg-emerald-soft text-emerald"
                  : "bg-accent text-muted-foreground"
              }`}
            >
              <Icon className="w-4.5 h-4.5" />
            </div>
          </div>
          <div
            className={`absolute -bottom-8 -left-8 w-24 h-24 rounded-full opacity-20 blur-2xl ${
              tone === "gold" ? "bg-gold" : tone === "emerald" ? "bg-emerald" : "bg-muted-foreground"
            }`}
          />
        </div>
      ))}
    </div>
  );
}
