import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  RESTAURANTS,
  type Restaurant,
  type Segment,
  type Status,
} from "@/lib/restaurants";
import { useStatusStore } from "@/hooks/useStatusStore";
import { CrmSidebar } from "@/components/crm/Sidebar";
import { AnalyticsBar } from "@/components/crm/Analytics";
import { RestaurantTable } from "@/components/crm/RestaurantTable";
import { ActionPanel } from "@/components/crm/ActionPanel";
import { Search } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "FAII HOUSE — Outreach CRM" },
      {
        name: "description",
        content:
          "لوحة تحكم احترافية للتواصل مع مطاعم إربد — FAII HOUSE استوديو إنتاج سينمائي.",
      },
    ],
  }),
  component: Dashboard,
});

const PAGE_SIZE = 25;

function Dashboard() {
  const { getStatus, setStatus, map } = useStatusStore();

  const [segments, setSegments] = useState<Set<Segment>>(new Set());
  const [categories, setCategories] = useState<Set<string>>(new Set());
  const [statuses, setStatuses] = useState<Set<Status>>(new Set());
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const segmentCounts = useMemo(() => {
    const c = { premium: 0, medium: 0, testing: 0 } as Record<Segment, number>;
    for (const r of RESTAURANTS) c[r.segment]++;
    return c;
  }, []);

  const statusCounts = useMemo(() => {
    const c = { new: 0, email: 0, whatsapp: 0, meeting: 0 } as Record<Status, number>;
    for (const r of RESTAURANTS) c[(map[r.id] ?? "new") as Status]++;
    return c;
  }, [map]);

  const allCategories = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of RESTAURANTS) m.set(r.category, (m.get(r.category) ?? 0) + 1);
    return [...m.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return RESTAURANTS.filter((r) => {
      if (segments.size && !segments.has(r.segment)) return false;
      if (categories.size && !categories.has(r.category)) return false;
      if (statuses.size && !statuses.has(getStatus(r.id))) return false;
      if (q) {
        const hay = `${r.title} ${r.category} ${r.street ?? ""} ${r.phone ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [segments, categories, statuses, search, getStatus]);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [segments, categories, statuses, search]);

  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const selected: Restaurant | null = useMemo(
    () => (selectedId ? RESTAURANTS.find((r) => r.id === selectedId) ?? null : null),
    [selectedId],
  );

  const contactedCount =
    statusCounts.email + statusCounts.whatsapp + statusCounts.meeting;

  const toggle = <T,>(set: Set<T>, setSet: (s: Set<T>) => void, v: T) => {
    const n = new Set(set);
    if (n.has(v)) n.delete(v);
    else n.add(v);
    setSet(n);
  };

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <CrmSidebar
        segments={segments}
        toggleSegment={(s) => toggle(segments, setSegments, s)}
        categories={categories}
        toggleCategory={(c) => toggle(categories, setCategories, c)}
        allCategories={allCategories}
        statuses={statuses}
        toggleStatus={(s) => toggle(statuses, setStatuses, s)}
        segmentCounts={segmentCounts}
        statusCounts={statusCounts}
        onReset={() => {
          setSegments(new Set());
          setCategories(new Set());
          setStatuses(new Set());
          setSearch("");
        }}
      />

      <main className="flex-1 min-w-0 flex flex-col">
        <header className="px-6 lg:px-8 py-6 border-b border-border bg-gradient-hero">
          <div className="flex items-center justify-between gap-6 mb-5">
            <div>
              <h1 className="text-2xl lg:text-3xl font-extrabold tracking-tight">
                لوحة تواصل المطاعم
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                ١٬٠٠٠ مطعم في إربد — مُصنّفة آلياً حسب الشريحة والفئة، مع رسائل تواصل
                جاهزة لكل مطعم.
              </p>
            </div>
            <div className="hidden md:flex items-center gap-2 px-4 py-2 rounded-full bg-card border border-border">
              <span className="w-2 h-2 rounded-full bg-emerald animate-pulse" />
              <span className="text-xs text-muted-foreground">
                CRM متصل ومُحدّث محلياً
              </span>
            </div>
          </div>
          <AnalyticsBar
            total={RESTAURANTS.length}
            premium={segmentCounts.premium}
            contacted={contactedCount}
            meetings={statusCounts.meeting}
          />
        </header>

        <div className="px-6 lg:px-8 py-5 flex-1 min-h-0 flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="ابحث عن مطعم، فئة، رقم..."
                className="w-full pr-9 pl-4 py-2.5 rounded-lg bg-card border border-border focus:border-gold/50 outline-none text-sm placeholder:text-muted-foreground"
              />
            </div>
            <div className="text-xs text-muted-foreground">
              <span className="text-foreground font-semibold tabular-nums">
                {filtered.length.toLocaleString("ar")}
              </span>{" "}
              نتيجة
            </div>
          </div>

          <RestaurantTable
            rows={pageRows}
            selectedId={selectedId}
            onSelect={(r) => setSelectedId(r.id === selectedId ? null : r.id)}
            getStatus={getStatus}
            page={page}
            pageSize={PAGE_SIZE}
            total={filtered.length}
            onPage={setPage}
          />
        </div>
      </main>

      <ActionPanel
        restaurant={selected}
        status={selected ? getStatus(selected.id) : "new"}
        onStatusChange={(s) => selected && setStatus(selected.id, s)}
        onClose={() => setSelectedId(null)}
      />
    </div>
  );
}
