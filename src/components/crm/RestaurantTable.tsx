import { SEGMENT_META, STATUS_META, type Restaurant, type Status } from "@/lib/restaurants";
import { Star, Globe, Phone, ChevronLeft, ChevronRight } from "lucide-react";

interface Props {
  rows: Restaurant[];
  selectedId: string | null;
  onSelect: (r: Restaurant) => void;
  getStatus: (id: string) => Status;
  page: number;
  pageSize: number;
  total: number;
  onPage: (p: number) => void;
}

export function RestaurantTable({
  rows,
  selectedId,
  onSelect,
  getStatus,
  page,
  pageSize,
  total,
  onPage,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto scrollbar-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-surface-2 text-[11px] tracking-widest uppercase text-muted-foreground">
              <th className="text-right font-medium px-4 py-3 w-12">#</th>
              <th className="text-right font-medium px-4 py-3">المطعم</th>
              <th className="text-right font-medium px-4 py-3">الفئة</th>
              <th className="text-right font-medium px-4 py-3">الشريحة</th>
              <th className="text-right font-medium px-4 py-3">التقييم</th>
              <th className="text-right font-medium px-4 py-3">الهاتف</th>
              <th className="text-right font-medium px-4 py-3">الحالة</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-16 text-muted-foreground">
                  لا توجد نتائج تطابق الفلاتر الحالية
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const seg = SEGMENT_META[r.segment];
              const status = getStatus(r.id);
              const stMeta = STATUS_META[status];
              const selected = selectedId === r.id;
              return (
                <tr
                  key={r.id}
                  onClick={() => onSelect(r)}
                  className={`border-t border-border cursor-pointer transition-colors ${
                    selected ? "bg-gold-soft/40" : "hover:bg-accent/40"
                  }`}
                >
                  <td className="px-4 py-3 text-muted-foreground tabular-nums">{r.rank}</td>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-foreground">{r.title}</div>
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
                    <span className="inline-flex items-center gap-2 text-xs">
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
          <span className="text-foreground tabular-nums">{total.toLocaleString("ar")}</span>
        </div>
        <div className="flex items-center gap-1">
          <PagerBtn disabled={page <= 1} onClick={() => onPage(page - 1)}>
            <ChevronRight className="w-4 h-4" />
          </PagerBtn>
          <span className="px-3 tabular-nums">
            {page} / {totalPages}
          </span>
          <PagerBtn disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
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
