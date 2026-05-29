import { SEGMENT_META, STATUS_META, type Segment, type Status } from "@/lib/restaurants";
import {
  Film, Filter, Tag, Activity, Star, Phone, Globe, ArrowUpDown,
  Download, Upload, Trash2,
} from "lucide-react";

export type SortKey = "score" | "rank" | "rating" | "name" | "updated";
export interface ExtraFilters {
  favorites: boolean;
  hasPhone: boolean;
  hasWebsite: boolean;
}

interface Props {
  segments: Set<Segment>;
  toggleSegment: (s: Segment) => void;
  categories: Set<string>;
  toggleCategory: (c: string) => void;
  allCategories: { name: string; count: number }[];
  statuses: Set<Status>;
  toggleStatus: (s: Status) => void;
  segmentCounts: Record<Segment, number>;
  statusCounts: Record<Status, number>;
  extra: ExtraFilters;
  setExtra: (e: ExtraFilters) => void;
  favCount: number;
  sort: SortKey;
  setSort: (s: SortKey) => void;
  tags: Set<string>;
  toggleTag: (t: string) => void;
  allTags: { name: string; count: number }[];
  onReset: () => void;
  onBackup: () => void;
  onRestore: () => void;
  onClearAll: () => void;
}

export function CrmSidebar(props: Props) {
  return (
    <aside className="hidden lg:flex w-72 shrink-0 flex-col border-l border-border bg-surface/60 backdrop-blur-sm">
      <div className="px-6 py-6 border-b border-border bg-gradient-hero">
        <div className="flex items-center gap-2">
          <Film className="w-6 h-6 text-gold" strokeWidth={2.2} />
          <div>
            <div className="text-xl font-extrabold tracking-tight">
              <span className="text-gold">FAII</span> HOUSE
            </div>
            <div className="text-[10px] tracking-[0.25em] text-muted-foreground uppercase">
              Outreach CRM
            </div>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-5 space-y-7">
        <Section icon={<Filter className="w-3.5 h-3.5" />} title="الشريحة">
          {(Object.keys(SEGMENT_META) as Segment[]).map((s) => {
            const meta = SEGMENT_META[s];
            return (
              <FilterRow
                key={s}
                active={props.segments.has(s)}
                onClick={() => props.toggleSegment(s)}
                label={meta.label}
                count={props.segmentCounts[s]}
                accent={meta.color}
              />
            );
          })}
        </Section>

        <Section icon={<Activity className="w-3.5 h-3.5" />} title="حالة التواصل">
          {(Object.keys(STATUS_META) as Status[]).map((s) => (
            <FilterRow
              key={s}
              active={props.statuses.has(s)}
              onClick={() => props.toggleStatus(s)}
              label={STATUS_META[s].label}
              count={props.statusCounts[s]}
              dot={STATUS_META[s].dot}
            />
          ))}
        </Section>

        <Section icon={<Filter className="w-3.5 h-3.5" />} title="فلاتر سريعة">
          <FilterRow
            active={props.extra.favorites}
            onClick={() => props.setExtra({ ...props.extra, favorites: !props.extra.favorites })}
            label="المفضلة فقط"
            count={props.favCount}
            icon={<Star className="w-3 h-3 fill-current text-gold" />}
          />
          <FilterRow
            active={props.extra.hasPhone}
            onClick={() => props.setExtra({ ...props.extra, hasPhone: !props.extra.hasPhone })}
            label="يحتوي رقم هاتف"
            icon={<Phone className="w-3 h-3" />}
          />
          <FilterRow
            active={props.extra.hasWebsite}
            onClick={() => props.setExtra({ ...props.extra, hasWebsite: !props.extra.hasWebsite })}
            label="لديه موقع/سوشال"
            icon={<Globe className="w-3 h-3 text-emerald" />}
          />
        </Section>

        <Section icon={<ArrowUpDown className="w-3.5 h-3.5" />} title="ترتيب حسب">
          {(
            [
              { k: "score", l: "Lead Score (الأقوى)" },
              { k: "rank", l: "الأعلى ترتيباً" },
              { k: "rating", l: "التقييم" },
              { k: "name", l: "الاسم" },
              { k: "updated", l: "آخر تحديث" },
            ] as { k: SortKey; l: string }[]
          ).map(({ k, l }) => (
            <FilterRow key={k} active={props.sort === k} onClick={() => props.setSort(k)} label={l} />
          ))}
        </Section>

        {props.allTags.length > 0 && (
          <Section icon={<Tag className="w-3.5 h-3.5" />} title="الوسوم">
            <div className="max-h-48 overflow-y-auto scrollbar-thin pl-1 space-y-1">
              {props.allTags.map((t) => (
                <FilterRow
                  key={t.name}
                  active={props.tags.has(t.name)}
                  onClick={() => props.toggleTag(t.name)}
                  label={t.name}
                  count={t.count}
                />
              ))}
            </div>
          </Section>
        )}

        <Section icon={<Tag className="w-3.5 h-3.5" />} title="الفئة">
          <div className="max-h-72 overflow-y-auto scrollbar-thin pl-1 space-y-1">
            {props.allCategories.map((c) => (
              <FilterRow
                key={c.name}
                active={props.categories.has(c.name)}
                onClick={() => props.toggleCategory(c.name)}
                label={c.name}
                count={c.count}
              />
            ))}
          </div>
        </Section>
      </div>

      <div className="border-t border-border p-4 space-y-2">
        <button
          onClick={props.onReset}
          className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors py-2 rounded-md border border-border hover:border-border-strong"
        >
          إعادة ضبط الفلاتر
        </button>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={props.onBackup}
            title="نسخة احتياطية JSON"
            className="inline-flex items-center justify-center gap-1 text-[11px] py-2 rounded-md border border-border hover:border-emerald/40 text-muted-foreground hover:text-emerald"
          >
            <Download className="w-3 h-3" /> نسخ احتياطي
          </button>
          <button
            onClick={props.onRestore}
            title="استرجاع من ملف"
            className="inline-flex items-center justify-center gap-1 text-[11px] py-2 rounded-md border border-border hover:border-gold/40 text-muted-foreground hover:text-gold"
          >
            <Upload className="w-3 h-3" /> استرجاع
          </button>
        </div>
        <button
          onClick={props.onClearAll}
          className="w-full inline-flex items-center justify-center gap-1 text-[11px] text-muted-foreground hover:text-destructive py-1.5"
        >
          <Trash2 className="w-3 h-3" /> مسح جميع بيانات CRM
        </button>
      </div>
    </aside>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-[11px] tracking-widest uppercase text-muted-foreground mb-3">
        {icon}<span>{title}</span>
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function FilterRow({
  active, onClick, label, count, accent, dot, icon,
}: {
  active: boolean; onClick: () => void; label: string;
  count?: number; accent?: string; dot?: string; icon?: React.ReactNode;
}) {
  const accentClasses =
    accent === "gold" ? "border-gold/40 bg-gold-soft text-gold" :
    accent === "emerald" ? "border-emerald/40 bg-emerald-soft text-emerald" :
    "border-border-strong bg-accent text-foreground";

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm border transition-all ${
        active ? accentClasses : "border-transparent text-muted-foreground hover:bg-accent/50 hover:text-foreground"
      }`}
    >
      <span className="flex items-center gap-2 truncate">
        {icon}
        {dot && <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />}
        <span className="truncate">{label}</span>
      </span>
      {count != null && <span className="text-[11px] tabular-nums opacity-80">{count}</span>}
    </button>
  );
}
