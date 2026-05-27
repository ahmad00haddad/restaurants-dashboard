import { useMemo } from "react";
import { CalendarClock, X, AlertCircle } from "lucide-react";
import { RESTAURANTS, type Restaurant } from "@/lib/restaurants";
import type { RestaurantState } from "@/hooks/useCrmStore";

interface Props {
  open: boolean;
  onClose: () => void;
  store: Record<string, RestaurantState>;
  onPick: (r: Restaurant) => void;
}

export function FollowUpsDrawer({ open, onClose, store, onPick }: Props) {
  const items = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    const list: { r: Restaurant; date: string; overdue: boolean }[] = [];
    for (const r of RESTAURANTS) {
      const fu = store[r.id]?.followUp;
      if (!fu) continue;
      list.push({ r, date: fu, overdue: fu < today });
    }
    return list.sort((a, b) => a.date.localeCompare(b.date));
  }, [store]);

  if (!open) return null;

  const overdue = items.filter((i) => i.overdue).length;
  const today = items.filter((i) => i.date === new Date().toISOString().slice(0, 10)).length;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="absolute left-0 top-0 h-full w-full max-w-md bg-card border-l border-border shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b border-border bg-gradient-hero flex items-center justify-between">
          <div>
            <div className="text-[10px] tracking-widest uppercase text-muted-foreground">
              التذكيرات والمتابعات
            </div>
            <h2 className="text-lg font-bold mt-1 flex items-center gap-2">
              <CalendarClock className="w-5 h-5 text-gold" />
              {items.length} متابعة
            </h2>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-md hover:bg-accent flex items-center justify-center">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2 px-5 py-3 border-b border-border">
          <Stat label="متأخرة" value={overdue} tone="destructive" />
          <Stat label="اليوم" value={today} tone="gold" />
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-2">
          {items.length === 0 && (
            <div className="text-center py-12 text-sm text-muted-foreground">
              لا توجد متابعات مجدولة. أضف تذكيراً من لوحة المطعم.
            </div>
          )}
          {items.map(({ r, date, overdue }) => (
            <button
              key={r.id}
              onClick={() => { onPick(r); onClose(); }}
              className={`w-full text-right p-3 rounded-lg border transition-colors flex items-start justify-between gap-3 ${
                overdue
                  ? "border-destructive/40 bg-destructive/10 hover:bg-destructive/15"
                  : "border-border bg-background hover:border-gold/40"
              }`}
            >
              <div className="min-w-0">
                <div className="font-semibold text-sm text-foreground truncate">{r.title}</div>
                <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
                  {r.category} • #{r.rank}
                </div>
              </div>
              <div className={`text-[11px] tabular-nums flex items-center gap-1 shrink-0 ${
                overdue ? "text-destructive-foreground" : "text-gold"
              }`}>
                {overdue && <AlertCircle className="w-3 h-3" />}
                {date}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: "destructive" | "gold" }) {
  return (
    <div className={`rounded-lg px-3 py-2 border ${
      tone === "destructive" ? "border-destructive/30 bg-destructive/10" : "border-gold/30 bg-gold-soft"
    }`}>
      <div className="text-[10px] tracking-widest uppercase text-muted-foreground">{label}</div>
      <div className={`text-xl font-extrabold tabular-nums ${tone === "destructive" ? "text-destructive-foreground" : "text-gold"}`}>
        {value.toLocaleString("ar")}
      </div>
    </div>
  );
}
