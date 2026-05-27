import { SEGMENT_META, STATUS_META, type Restaurant, type Status } from "@/lib/restaurants";
import {
  Star,
  Globe,
  Phone,
  ChevronLeft,
  ChevronRight,
  CalendarClock,
} from "lucide-react";

interface Props {
  rows: Restaurant[];
  selectedId: string | null;
  onSelect: (r: Restaurant) => void;
  getStatus: (id: string) => Status;
  isFavorite: (id: string) => boolean;
  hasNotes: (id: string) => boolean;
  followUp: (id: string) => string | undefined;
  tags: (id: string) => string[];
  toggleFavorite: (id: string) => void;
  selectedIds: Set<string>;
  toggleSelect: (id: string) => void;
  toggleSelectAll: () => void;
  allSelected: boolean;
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}

export function RestaurantTable(p: Props) {
  const totalPages = Math.max(1, Math.ceil(p.total / p.pageSize));
  const from = p.total === 0 ? 0 : (p.page - 1) * p.pageSize + 1;
  const to = Math.min(p.page * p.pageSize, p.total);
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden flex-1 flex flex-col min-h-0">
      <div className="overflow-auto scrollbar-thin flex-1">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="bg-surface-2 text-[11px] tracking-widest uppercase text-muted-foreground">
              <th className="text-center font-medium px-3 py-3 w-10">
                <input
                  type="checkbox"
                  checked={p.allSelected}
                  onChange={p.toggleSelectAll}
                  className="accent-gold w-4 h-4 cursor-pointer"
                />
              </th>
              <th className="text-center font-medium px-2 py-3 w-10">★</th>
              <th className="text-right font-medium px-3 py-3 w-14">#</th>
              <th className="text-right font-medium px-4 py-3">المطعم</th>
              <th className="text-right font-medium px-4 py-3">الفئة</th>
              <th className="text-right font-medium px-4 py-3">الشريحة</th>
              <th className="text-right font-medium px-4 py-3">التقييم</th>
              <th className="text-right font-medium px-4 py-3">الهاتف</th>
              <th className="text-right font-medium px-4 py-3">الحالة</th>
            </tr>
          </thead>
          <tbody>
            {p.rows.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-16 text-muted-foreground">
                  لا توجد نتائج تطابق الفلاتر الحالية
                </td>
              </tr>
            )}
            {p.rows.map((r) => {
              const seg = SEGMENT_META[r.segment];
              const status = p.getStatus(r.id);
              const stMeta = STATUS_META[status];
              const selected = p.selectedId === r.id;
              const fav = p.isFavorite(r.id);
              const checked = p.selectedIds.has(r.id);
              const fu = p.followUp(r.id);
              const fuDue = fu && fu <= today;
              return (
                <tr
                  key={r.id}
                  onClick={() => p.onSelect(r)}
                  className={`border-t border-border cursor-pointer transition-colors ${
                    selected ? "bg-gold-soft/40" : checked ? "bg-emerald-soft/20" : "hover:bg-accent/40"
                  }`}
                >
                  <td className="px-3 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => p.toggleSelect(r.id)}
                      className="accent-gold w-4 h-4 cursor-pointer"
                    />
                  </td>
                  <td className="px-2 py-3 text-center" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => p.toggleFavorite(r.id)}
                      className={`p-1 rounded hover:bg-accent ${fav ? "text-gold" : "text-muted-foreground/40 hover:text-gold"}`}
                    >
                      <Star className={`w-4 h-4 ${fav ? "fill-current" : ""}`} />
                    </button>
                  </td>
                  <td className="px-3 py-3 text-muted-foreground tabular-nums">{r.rank}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-foreground">{r.title}</span>
                      {p.hasNotes(r.id) && (
                        <span title="يحتوي ملاحظات" className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-soft text-emerald">
                          ملاحظة
                        </span>
                      )}
                      {fu && (
                        <span
                          title={`متابعة: ${fu}`}
                          className={`text-[10px] inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${
                            fuDue ? "bg-destructive/20 text-destructive-foreground" : "bg-gold-soft text-gold"
                          }`}
                        >
                          <CalendarClock className="w-3 h-3" />
                          {fu}
                        </span>
                      )}
                      {p.tags(r.id).slice(0, 3).map((t) => (
                        <span key={t} className="text-[10px] px-1.5 py-0.5 rounded bg-accent text-muted-foreground border border-border">
                          #{t}
                        </span>
                      ))}
                    </div>
                    <div className="text-xs text-muted-foreground truncate max-w-[280px]">
                      {r.street || r.address || ""}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground whitespace-nowrap">
                    {r.category}
                  </td>
                  <td className="px-4 py-3">
                    <SegmentBadge segment={r.segment} label={seg.label} />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 text-gold">
                      <Star className="w-3.5 h-3.5 fill-current" />
                      <span className="tabular-nums text-foreground">{r.rating}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3 text-muted-foreground">
                      {r.phone ? (
                        <span className="inline-flex items-center gap-1 text-xs tabular-nums">
                          <Phone className="w-3 h-3" /> {r.phone}
                        </span>
                      ) : (
                        <span className="text-xs">—</span>
                      )}
                      {r.website && <Globe className="w-3.5 h-3.5 text-emerald" />}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-2 text-xs whitespace-nowrap">
                      <span className={`w-1.5 h-1.5 rounded-full ${stMeta.dot}`} />
                      {stMeta.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-surface-2/40 text-xs text-muted-foreground">
        <div>
          عرض <span className="text-foreground tabular-nums">{from}-{to}</span> من{" "}
          <span className="text-foreground tabular-nums">{p.total.toLocaleString("ar")}</span>
        </div>
        <div className="flex items-center gap-1">
          <PagerBtn disabled={p.page <= 1} onClick={() => p.onPage(p.page - 1)}>
            <ChevronRight className="w-4 h-4" />
          </PagerBtn>
          <span className="px-3 tabular-nums">
            {p.page} / {totalPages}
          </span>
          <PagerBtn disabled={p.page >= totalPages} onClick={() => p.onPage(p.page + 1)}>
            <ChevronLeft className="w-4 h-4" />
          </PagerBtn>
        </div>
      </div>
    </div>
  );
}

function SegmentBadge({ segment, label }: { segment: string; label: string }) {
  const cls =
    segment === "premium"
      ? "bg-gold-soft text-gold border-gold/30"
      : segment === "medium"
      ? "bg-emerald-soft text-emerald border-emerald/30"
      : "bg-accent text-muted-foreground border-border";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md border text-[11px] font-medium ${cls}`}>
      {label}
    </span>
  );
}

function PagerBtn({
  children,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-8 h-8 rounded-md border border-border flex items-center justify-center hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed text-foreground"
    >
      {children}
    </button>
  );
}
