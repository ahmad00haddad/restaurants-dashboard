import { CheckCircle2, X, Download, MessageCircle, Mail, Calendar } from "lucide-react";
import type { Status } from "@/lib/restaurants";
import { STATUS_META } from "@/lib/restaurants";

interface Props {
  count: number;
  onClear: () => void;
  onBulkStatus: (s: Status) => void;
  onExport: () => void;
}

export function BulkActionBar({ count, onClear, onBulkStatus, onExport }: Props) {
  if (count === 0) return null;
  return (
    <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-gold/40 bg-gold-soft/40 backdrop-blur-sm">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
        <CheckCircle2 className="w-4 h-4 text-gold" />
        تم تحديد <span className="tabular-nums text-gold">{count}</span> مطعم
      </div>
      <div className="h-5 w-px bg-border" />
      <div className="flex items-center gap-1.5 flex-wrap">
        {(Object.keys(STATUS_META) as Status[]).map((s) => {
          const m = STATUS_META[s];
          const icon =
            s === "whatsapp" ? <MessageCircle className="w-3 h-3" /> :
            s === "email" ? <Mail className="w-3 h-3" /> :
            s === "meeting" ? <Calendar className="w-3 h-3" /> :
            <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />;
          return (
            <button
              key={s}
              onClick={() => onBulkStatus(s)}
              className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md bg-card border border-border hover:border-gold/50 text-foreground"
            >
              {icon} {m.label}
            </button>
          );
        })}
      </div>
      <div className="flex-1" />
      <button
        onClick={onExport}
        className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-emerald text-background font-semibold hover:opacity-90"
      >
        <Download className="w-3.5 h-3.5" /> تصدير CSV
      </button>
      <button
        onClick={onClear}
        className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <X className="w-3.5 h-3.5" /> إلغاء
      </button>
    </div>
  );
}
