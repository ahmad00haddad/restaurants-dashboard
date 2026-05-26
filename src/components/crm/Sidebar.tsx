import { SEGMENT_META, STATUS_META, type Segment, type Status } from "@/lib/restaurants";
import { Film, Filter, Tag, Activity } from "lucide-react";

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
  onReset: () => void;
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
            const active = props.segments.has(s);
            const meta = SEGMENT_META[s];
            return (
              <FilterRow
                key={s}
                active={active}
                onClick={() => props.toggleSegment(s)}
                label={meta.label}
                count={props.segmentCounts[s]}
                accent={meta.color}
              />
            );
          })}
        </Section>

        <Section icon={<Activity className="w-3.5 h-3.5" />} title="حالة التواصل">
          {(Object.keys(STATUS_META) as Status[]).map((s) => {
            const active = props.statuses.has(s);
            return (
              <FilterRow
                key={s}
                active={active}
                onClick={() => props.toggleStatus(s)}
                label={STATUS_META[s].label}
                count={props.statusCounts[s]}
                dot={STATUS_META[s].dot}
              />
            );
          })}
        </Section>

        <Section icon={<Tag className="w-3.5 h-3.5" />} title="الفئة">
          <div className="max-h-72 overflow-y-auto scrollbar-thin pl-1 space-y-1">
            {props.allCategories.map((c) => {
              const active = props.categories.has(c.name);
              return (
                <FilterRow
                  key={c.name}
                  active={active}
                  onClick={() => props.toggleCategory(c.name)}
                  label={c.name}
                  count={c.count}
                />
              );
            })}
          </div>
        </Section>
      </div>

      <div className="border-t border-border p-4">
        <button
          onClick={props.onReset}
          className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors py-2 rounded-md border border-border hover:border-border-strong"
        >
          إعادة ضبط الفلاتر
        </button>
      </div>
    </aside>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2 text-[11px] tracking-widest uppercase text-muted-foreground mb-3">
        {icon}
        <span>{title}</span>
      </div>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function FilterRow({
  active,
  onClick,
  label,
  count,
  accent,
  dot,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  count: number;
  accent?: string;
  dot?: string;
}) {
  const accentClasses =
    accent === "gold"
      ? "border-gold/40 bg-gold-soft text-gold"
      : accent === "emerald"
      ? "border-emerald/40 bg-emerald-soft text-emerald"
      : "border-border-strong bg-accent text-foreground";

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-sm border transition-all ${
        active
          ? accentClasses
          : "border-transparent text-muted-foreground hover:bg-accent/50 hover:text-foreground"
      }`}
    >
      <span className="flex items-center gap-2 truncate">
        {dot && <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />}
        <span className="truncate">{label}</span>
      </span>
      <span className="text-[11px] tabular-nums opacity-80">{count}</span>
    </button>
  );
}
