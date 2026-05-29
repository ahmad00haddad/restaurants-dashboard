import { useEffect, useMemo, useRef, useState } from "react";
import { Search, ArrowLeft, Sparkles } from "lucide-react";
import { SEGMENT_META, type Restaurant } from "@/lib/restaurants";
import { useRestaurants } from "@/hooks/useRestaurants";

interface Props {
  open: boolean;
  onClose: () => void;
  onPick: (r: Restaurant) => void;
}

export function CommandPalette({ open, onClose, onPick }: Props) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const restaurants = useRestaurants();

  useEffect(() => {
    if (open) {
      setQ("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  const results = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return restaurants.slice(0, 8);
    return restaurants.filter((r) =>
      `${r.title} ${r.category} ${r.phone ?? ""}`.toLowerCase().includes(s),
    ).slice(0, 12);
  }, [q, restaurants]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => Math.min(a + 1, results.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => Math.max(a - 1, 0));
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const r = results[active];
        if (r) {
          onPick(r);
          onClose();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, results, active, onClose, onPick]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start justify-center pt-24 px-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-2xl border border-border bg-card shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <Search className="w-4 h-4 text-gold" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => { setQ(e.target.value); setActive(0); }}
            placeholder="ابحث بسرعة عن مطعم أو فئة..."
            className="flex-1 bg-transparent outline-none text-sm text-foreground placeholder:text-muted-foreground"
          />
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 border border-border text-muted-foreground">
            ESC
          </kbd>
        </div>
        <div className="max-h-[420px] overflow-y-auto scrollbar-thin py-1">
          {results.length === 0 && (
            <div className="text-center py-10 text-sm text-muted-foreground">
              لا نتائج
            </div>
          )}
          {results.map((r, i) => {
            const seg = SEGMENT_META[r.segment];
            return (
              <button
                key={r.id}
                onMouseEnter={() => setActive(i)}
                onClick={() => { onPick(r); onClose(); }}
                className={`w-full text-right px-4 py-2.5 flex items-center gap-3 transition-colors ${
                  i === active ? "bg-gold-soft" : "hover:bg-accent/40"
                }`}
              >
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded border ${
                    r.segment === "premium"
                      ? "bg-gold-soft text-gold border-gold/30"
                      : r.segment === "medium"
                      ? "bg-emerald-soft text-emerald border-emerald/30"
                      : "bg-accent text-muted-foreground border-border"
                  }`}
                >
                  {seg.label}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-foreground truncate">{r.title}</div>
                  <div className="text-[11px] text-muted-foreground truncate">
                    {r.category} • #{r.rank}
                  </div>
                </div>
                {i === active && <ArrowLeft className="w-3.5 h-3.5 text-gold" />}
              </button>
            );
          })}
        </div>
        <div className="px-4 py-2 border-t border-border text-[10px] text-muted-foreground flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-gold" />
            بحث فوري عبر ١٬٠٠٠ مطعم
          </span>
          <span className="flex items-center gap-2">
            <kbd className="px-1.5 py-0.5 rounded bg-surface-2 border border-border">↑↓</kbd>
            <kbd className="px-1.5 py-0.5 rounded bg-surface-2 border border-border">Enter</kbd>
          </span>
        </div>
      </div>
    </div>
  );
}
