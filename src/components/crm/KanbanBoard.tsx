import { useState } from "react";
import { SEGMENT_META, STATUS_META, type Restaurant, type Status } from "@/lib/restaurants";
import { Star, Phone, Globe, GripVertical } from "lucide-react";

interface Props {
  rows: Restaurant[];
  getStatus: (id: string) => Status;
  isFavorite: (id: string) => boolean;
  onSelect: (r: Restaurant) => void;
  selectedId: string | null;
  onStatusChange?: (id: string, status: Status) => void;
}

const COLUMNS: { key: Status; label: string; ring: string }[] = [
  { key: "new", label: "جديد", ring: "border-border" },
  { key: "whatsapp", label: "تم إرسال واتساب", ring: "border-emerald/40" },
  { key: "email", label: "تم إرسال إيميل", ring: "border-sky-400/40" },
  { key: "meeting", label: "تم حجز اجتماع", ring: "border-gold/40" },
];

export function KanbanBoard({ rows, getStatus, isFavorite, onSelect, selectedId, onStatusChange }: Props) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overCol, setOverCol] = useState<Status | null>(null);

  const grouped: Record<Status, Restaurant[]> = {
    new: [], email: [], whatsapp: [], meeting: [],
  };
  for (const r of rows) grouped[getStatus(r.id)].push(r);

  const handleDrop = (col: Status) => {
    if (dragId && onStatusChange && getStatus(dragId) !== col) {
      onStatusChange(dragId, col);
    }
    setDragId(null);
    setOverCol(null);
  };

  return (
    <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
      {COLUMNS.map((c) => {
        const isOver = overCol === c.key;
        return (
          <div
            key={c.key}
            onDragOver={(e) => { e.preventDefault(); setOverCol(c.key); }}
            onDragLeave={() => setOverCol((v) => (v === c.key ? null : v))}
            onDrop={() => handleDrop(c.key)}
            className={`flex flex-col min-h-0 rounded-xl border transition-colors ${
              isOver ? "border-gold/70 bg-gold-soft/30" : `${c.ring} bg-card/40`
            }`}
          >
            <div className="px-4 py-3 border-b border-border flex items-center justify-between bg-surface-2/40 rounded-t-xl">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <span className={`w-2 h-2 rounded-full ${STATUS_META[c.key].dot}`} />
                {c.label}
              </div>
              <span className="text-xs text-muted-foreground tabular-nums">
                {grouped[c.key].length}
              </span>
            </div>
            <div className="flex-1 overflow-y-auto scrollbar-thin p-2 space-y-2">
              {grouped[c.key].length === 0 && (
                <div className="text-center text-xs text-muted-foreground py-10">
                  {isOver ? "أفلت هنا لتغيير الحالة" : "لا يوجد"}
                </div>
              )}
              {grouped[c.key].slice(0, 80).map((r) => {
                const seg = SEGMENT_META[r.segment];
                const sel = selectedId === r.id;
                const fav = isFavorite(r.id);
                const dragging = dragId === r.id;
                return (
                  <div
                    key={r.id}
                    draggable={!!onStatusChange}
                    onDragStart={(e) => { setDragId(r.id); e.dataTransfer.effectAllowed = "move"; }}
                    onDragEnd={() => { setDragId(null); setOverCol(null); }}
                    onClick={() => onSelect(r)}
                    className={`group w-full text-right p-3 rounded-lg border transition-all cursor-pointer ${
                      sel
                        ? "border-gold/60 bg-gold-soft"
                        : "border-border bg-background hover:border-border-strong"
                    } ${dragging ? "opacity-40" : ""}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="font-semibold text-sm text-foreground truncate flex-1 flex items-center gap-1.5">
                        {onStatusChange && (
                          <GripVertical className="w-3.5 h-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 cursor-grab shrink-0" />
                        )}
                        <span className="truncate">{r.title}</span>
                      </div>
                      {fav && <Star className="w-3.5 h-3.5 text-gold fill-current shrink-0" />}
                    </div>
                    <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
                      {r.category}
                    </div>
                    <div className="flex items-center justify-between mt-2">
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
                      <div className="flex items-center gap-2 text-muted-foreground">
                        {r.phone && <Phone className="w-3 h-3" />}
                        {r.website && <Globe className="w-3 h-3 text-emerald" />}
                        <span className="text-[10px] tabular-nums text-gold">★ {r.rating}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
              {grouped[c.key].length > 80 && (
                <div className="text-center text-[10px] text-muted-foreground py-2">
                  + {grouped[c.key].length - 80} عنصر إضافي (استخدم الفلاتر للتضييق)
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
