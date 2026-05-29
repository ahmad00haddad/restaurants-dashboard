import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  downloadCSV,
  exportRestaurantsCSV,
  leadScore,
  type Restaurant,
  type Segment,
  type Status,
} from "@/lib/restaurants";
import { useRestaurants } from "@/hooks/useRestaurants";
import { useCrmStore } from "@/hooks/useCrmStore";
import { useSettings } from "@/hooks/useSettings";
import { useToast } from "@/hooks/useToast";
import { CrmSidebar, type ExtraFilters, type SortKey } from "@/components/crm/Sidebar";
import { AnalyticsBar } from "@/components/crm/Analytics";
import { RestaurantTable } from "@/components/crm/RestaurantTable";
import { KanbanBoard } from "@/components/crm/KanbanBoard";
import { BulkActionBar } from "@/components/crm/BulkActionBar";
import { ActionPanel } from "@/components/crm/ActionPanel";
import { CommandPalette } from "@/components/crm/CommandPalette";
import { FollowUpsDrawer } from "@/components/crm/FollowUpsDrawer";
import { SettingsDialog } from "@/components/crm/SettingsDialog";
import { TopNav } from "@/components/crm/TopNav";
import { Search, LayoutGrid, List, Sparkles, Download } from "lucide-react";

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
const DAILY_GOAL = 20;

function Dashboard() {
  const {
    getStatus, setStatus, setStatusBulk, getState, update, toggleFavorite, store, todayCount,
    addTag, removeTag, allTags, importStore, exportStore, clearAll,
  } = useCrmStore();
  const { settings, update: updateSettings, reset: resetSettings } = useSettings();
  const toast = useToast();

  const [segments, setSegments] = useState<Set<Segment>>(new Set());
  const [categories, setCategories] = useState<Set<string>>(new Set());
  const [statuses, setStatuses] = useState<Set<Status>>(new Set());
  const [tags, setTags] = useState<Set<string>>(new Set());
  const [extra, setExtra] = useState<ExtraFilters>({
    favorites: false, hasPhone: false, hasWebsite: false,
  });
  const [sort, setSort] = useState<SortKey>("rank");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [view, setView] = useState<"table" | "kanban">("table");
  const [cmdOpen, setCmdOpen] = useState(false);
  const [followUpsOpen, setFollowUpsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const segmentCounts = useMemo(() => {
    const c = { premium: 0, medium: 0, testing: 0 } as Record<Segment, number>;
    for (const r of RESTAURANTS) c[r.segment]++;
    return c;
  }, []);

  const statusCounts = useMemo(() => {
    const c = { new: 0, email: 0, whatsapp: 0, meeting: 0 } as Record<Status, number>;
    for (const r of RESTAURANTS) c[(store[r.id]?.status ?? "new") as Status]++;
    return c;
  }, [store]);

  const favCount = useMemo(
    () => Object.values(store).filter((s) => s.favorite).length,
    [store],
  );

  const revenueStats = useMemo(() => {
    let revenue = 0, pipeline = 0;
    for (const s of Object.values(store)) {
      const v = s.dealValue ?? 0;
      if (!v) continue;
      if (s.status === "meeting") revenue += v;
      else if (s.status === "whatsapp" || s.status === "email") pipeline += v;
    }
    return { revenue, pipeline };
  }, [store]);

  const allCategories = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of RESTAURANTS) m.set(r.category, (m.get(r.category) ?? 0) + 1);
    return [...m.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, []);

  const today = new Date().toISOString().slice(0, 10);
  const followUps = useMemo(() => {
    let total = 0, overdue = 0;
    for (const s of Object.values(store)) {
      if (!s.followUp) continue;
      total++;
      if (s.followUp < today) overdue++;
    }
    return { total, overdue };
  }, [store, today]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const arr = RESTAURANTS.filter((r) => {
      if (segments.size && !segments.has(r.segment)) return false;
      if (categories.size && !categories.has(r.category)) return false;
      if (statuses.size && !statuses.has(getStatus(r.id))) return false;
      if (extra.favorites && !store[r.id]?.favorite) return false;
      if (extra.hasPhone && !r.phone) return false;
      if (extra.hasWebsite && !r.website) return false;
      if (tags.size) {
        const t = store[r.id]?.tags ?? [];
        if (!t.some((x) => tags.has(x))) return false;
      }
      if (q) {
        const hay = `${r.title} ${r.category} ${r.street ?? ""} ${r.phone ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    const sorted = [...arr];
    switch (sort) {
      case "score": sorted.sort((a, b) => leadScore(b) - leadScore(a)); break;
      case "rating": sorted.sort((a, b) => b.rating - a.rating); break;
      case "name": sorted.sort((a, b) => a.title.localeCompare(b.title, "ar")); break;
      case "updated":
        sorted.sort((a, b) => (store[b.id]?.updatedAt ?? 0) - (store[a.id]?.updatedAt ?? 0)); break;
      default: sorted.sort((a, b) => a.rank - b.rank);
    }
    return sorted;
  }, [segments, categories, statuses, tags, extra, sort, search, getStatus, store]);

  useEffect(() => { setPage(1); }, [segments, categories, statuses, tags, extra, sort, search]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen(true);
        return;
      }
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "/") { e.preventDefault(); searchRef.current?.focus(); }
      else if (e.key === "Escape") {
        if (cmdOpen) setCmdOpen(false);
        else if (followUpsOpen) setFollowUpsOpen(false);
        else if (selectedId) setSelectedId(null);
        else if (selectedIds.size) setSelectedIds(new Set());
      } else if (e.key.toLowerCase() === "k") {
        setView((v) => (v === "table" ? "kanban" : "table"));
      } else if (e.key.toLowerCase() === "f") {
        setFollowUpsOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, selectedIds, cmdOpen, followUpsOpen]);

  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const selected: Restaurant | null = useMemo(
    () => (selectedId ? RESTAURANTS.find((r) => r.id === selectedId) ?? null : null),
    [selectedId],
  );

  const contactedCount = statusCounts.email + statusCounts.whatsapp + statusCounts.meeting;

  const toggle = <T,>(set: Set<T>, setSet: (s: Set<T>) => void, v: T) => {
    const n = new Set(set);
    if (n.has(v)) n.delete(v); else n.add(v);
    setSet(n);
  };

  const toggleSelect = (id: string) => {
    const n = new Set(selectedIds);
    if (n.has(id)) n.delete(id); else n.add(id);
    setSelectedIds(n);
  };

  const pageIds = pageRows.map((r) => r.id);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));
  const toggleSelectAll = () => {
    const n = new Set(selectedIds);
    if (allSelected) pageIds.forEach((id) => n.delete(id));
    else pageIds.forEach((id) => n.add(id));
    setSelectedIds(n);
  };

  const bulkStatus = (s: Status) => {
    setStatusBulk([...selectedIds], s);
    toast.push(`تم تحديث ${selectedIds.size} مطعم`, "success");
    setSelectedIds(new Set());
  };

  const exportSelected = () => {
    const ids = selectedIds.size ? selectedIds : new Set(filtered.map((r) => r.id));
    const rows = RESTAURANTS.filter((r) => ids.has(r.id));
    downloadCSV(`faii-restaurants-${Date.now()}.csv`, exportRestaurantsCSV(rows));
    toast.push(`تم تصدير ${rows.length} مطعم`, "success");
  };

  const smartSuggest = () => {
    const candidates = RESTAURANTS.filter(
      (r) => r.segment === "premium" && r.phone && (store[r.id]?.status ?? "new") === "new",
    )
      .sort((a, b) => b.rating - a.rating || a.rank - b.rank)
      .slice(0, 10);
    setSelectedIds(new Set(candidates.map((r) => r.id)));
    setSegments(new Set(["premium"]));
    setExtra({ ...extra, hasPhone: true });
    setStatuses(new Set(["new"]));
    toast.push(`🔥 تم اقتراح أفضل ${candidates.length} لِيد للبدء بهم`, "info");
  };

  const handleBackup = () => {
    const data = exportStore();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `faii-crm-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.push("تم تنزيل نسخة احتياطية", "success");
  };

  const handleRestore = () => fileRef.current?.click();
  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const text = await f.text();
      const data = JSON.parse(text);
      if (typeof data !== "object" || !data) throw new Error("bad");
      importStore(data);
      toast.push("تم استرجاع البيانات بنجاح", "success");
    } catch {
      toast.push("الملف غير صالح", "error");
    } finally {
      e.target.value = "";
    }
  };

  const handleClearAll = () => {
    if (confirm("سيتم حذف جميع بيانات CRM المحلية (حالات، ملاحظات، مفضلة، وسوم). هل أنت متأكد؟")) {
      clearAll();
      toast.push("تم مسح جميع بيانات CRM", "info");
    }
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
        extra={extra}
        setExtra={setExtra}
        favCount={favCount}
        sort={sort}
        setSort={setSort}
        tags={tags}
        toggleTag={(t) => toggle(tags, setTags, t)}
        allTags={allTags}
        onReset={() => {
          setSegments(new Set());
          setCategories(new Set());
          setStatuses(new Set());
          setTags(new Set());
          setExtra({ favorites: false, hasPhone: false, hasWebsite: false });
          setSearch("");
        }}
        onBackup={handleBackup}
        onRestore={handleRestore}
        onClearAll={handleClearAll}
      />

      <input ref={fileRef} type="file" accept="application/json" onChange={onFile} className="hidden" />

      <main className="flex-1 min-w-0 flex flex-col">
        <header className="px-6 lg:px-8 py-6 border-b border-border bg-gradient-hero">
          <div className="flex items-center justify-between gap-6 mb-5 flex-wrap">
            <div>
              <h1 className="text-2xl lg:text-3xl font-extrabold tracking-tight">
                لوحة تواصل المطاعم
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                ١٬٠٠٠ مطعم في إربد — مُصنّفة آلياً حسب الشريحة والفئة، مع رسائل وأسعار جاهزة.
              </p>
            </div>
            <TopNav
              followUpsCount={followUps.total}
              overdueCount={followUps.overdue}
              onOpenFollowUps={() => setFollowUpsOpen(true)}
              onOpenCommand={() => setCmdOpen(true)}
              onOpenSettings={() => setSettingsOpen(true)}
            />
          </div>
          <AnalyticsBar
            total={RESTAURANTS.length}
            premium={segmentCounts.premium}
            contacted={contactedCount}
            meetings={statusCounts.meeting}
            today={todayCount}
            goal={DAILY_GOAL}
            revenue={revenueStats.revenue}
            pipeline={revenueStats.pipeline}
            currency={settings.currency}
          />
        </header>

        <div className="px-6 lg:px-8 py-5 flex-1 min-h-0 flex flex-col gap-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 min-w-[240px] max-w-md">
              <Search className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                ref={searchRef}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="ابحث عن مطعم، فئة، رقم... (/)"
                className="w-full pr-9 pl-4 py-2.5 rounded-lg bg-card border border-border focus:border-gold/50 outline-none text-sm placeholder:text-muted-foreground"
              />
            </div>
            <div className="text-xs text-muted-foreground">
              <span className="text-foreground font-semibold tabular-nums">
                {filtered.length.toLocaleString("ar")}
              </span>{" "}
              نتيجة
            </div>

            <div className="flex-1" />

            <button
              onClick={smartSuggest}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg bg-gold-soft border border-gold/40 text-gold hover:bg-gold/20"
            >
              <Sparkles className="w-3.5 h-3.5" /> اقتراح ذكي
            </button>
            <button
              onClick={exportSelected}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg bg-card border border-border text-foreground hover:border-emerald/50"
              title="تصدير القائمة الحالية أو المحددة"
            >
              <Download className="w-3.5 h-3.5" /> تصدير
            </button>

            <div className="inline-flex rounded-lg border border-border bg-card p-1">
              <ViewBtn active={view === "table"} onClick={() => setView("table")}>
                <List className="w-3.5 h-3.5" /> جدول
              </ViewBtn>
              <ViewBtn active={view === "kanban"} onClick={() => setView("kanban")}>
                <LayoutGrid className="w-3.5 h-3.5" /> Pipeline
              </ViewBtn>
            </div>
          </div>

          <BulkActionBar
            count={selectedIds.size}
            onClear={() => setSelectedIds(new Set())}
            onBulkStatus={bulkStatus}
            onExport={exportSelected}
          />

          {view === "table" ? (
            <RestaurantTable
              rows={pageRows}
              selectedId={selectedId}
              onSelect={(r) => setSelectedId(r.id === selectedId ? null : r.id)}
              getStatus={getStatus}
              isFavorite={(id) => !!store[id]?.favorite}
              hasNotes={(id) => !!store[id]?.notes?.trim()}
              followUp={(id) => store[id]?.followUp}
              tags={(id) => store[id]?.tags ?? []}
              toggleFavorite={(id) => {
                toggleFavorite(id);
                toast.push(store[id]?.favorite ? "أُزيلت من المفضلة" : "أُضيفت للمفضلة", "info");
              }}
              selectedIds={selectedIds}
              toggleSelect={toggleSelect}
              toggleSelectAll={toggleSelectAll}
              allSelected={allSelected}
              page={page}
              pageSize={PAGE_SIZE}
              total={filtered.length}
              onPage={setPage}
            />
          ) : (
            <KanbanBoard
              rows={filtered}
              getStatus={getStatus}
              isFavorite={(id) => !!store[id]?.favorite}
              onSelect={(r) => setSelectedId(r.id === selectedId ? null : r.id)}
              selectedId={selectedId}
            />
          )}
        </div>
      </main>

      <ActionPanel
        restaurant={selected}
        state={selected ? getState(selected.id) : {}}
        settings={settings}
        onStatusChange={(s) => selected && setStatus(selected.id, s)}
        onToggleFavorite={() => selected && toggleFavorite(selected.id)}
        onUpdate={(patch) => selected && update(selected.id, patch)}
        onAddTag={(t) => selected && addTag(selected.id, t)}
        onRemoveTag={(t) => selected && removeTag(selected.id, t)}
        onClose={() => setSelectedId(null)}
      />

      <CommandPalette
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        onPick={(r) => setSelectedId(r.id)}
      />
      <FollowUpsDrawer
        open={followUpsOpen}
        onClose={() => setFollowUpsOpen(false)}
        store={store}
        onPick={(r) => setSelectedId(r.id)}
      />
      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        onSave={updateSettings}
        onReset={resetSettings}
      />
    </div>
  );
}

function ViewBtn({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs transition-all ${
        active ? "bg-gold text-primary-foreground font-semibold" : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}
