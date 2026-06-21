import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useRef, useState } from "react";
import {
  ArrowRight, Database, Copy, Plus, Search, Trash2, Pencil, Save, X,
  AlertTriangle, RefreshCcw, CheckCircle2, Crown, Download, Upload, Loader2,
} from "lucide-react";
import {
  useRestaurants, addRestaurant, updateRestaurant, deleteRestaurants,
  restoreAllRestaurants, restaurantStats, type NewRestaurantInput,
} from "@/hooks/useRestaurants";
import { findDuplicateGroups, SEGMENT_META, type Restaurant } from "@/lib/restaurants";
import { useToast } from "@/hooks/useToast";
import { restaurantsToCsv, downloadCsv, parseCsv } from "@/lib/csv";

export const Route = createFileRoute("/_authenticated/manage")({
  head: () => ({
    meta: [
      { title: "FAII HOUSE — إدارة قاعدة البيانات" },
      { name: "description", content: "إضافة وتعديل وحذف المطاعم وإدارة التكرارات في قاعدة بيانات FAII HOUSE." },
    ],
  }),
  component: ManagePage,
});

type Tab = "all" | "duplicates" | "added" | "edited";

function ManagePage() {
  const list = useRestaurants();
  const stats = restaurantStats();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("all");
  const [q, setQ] = useState("");
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<Restaurant | null>(null);
  const [importing, setImporting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const duplicateGroups = useMemo(() => findDuplicateGroups(list), [list]);
  const duplicateCount = duplicateGroups.reduce((n, g) => n + g.length - 1, 0);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return list;
    return list.filter((r) =>
      `${r.title} ${r.phone ?? ""} ${r.street ?? ""} ${r.address ?? ""}`.toLowerCase().includes(s),
    );
  }, [list, q]);

  const handleDelete = async (r: Restaurant) => {
    if (!confirm(`حذف "${r.title}" نهائياً من القاعدة؟`)) return;
    await deleteRestaurants([r.id]);
    toast.push("تم الحذف", "success");
  };

  const handleBulkDelete = async (ids: string[]) => {
    if (ids.length === 0) return;
    if (!confirm(`حذف ${ids.length} مطعم نهائياً؟ لا يمكن التراجع.`)) return;
    await deleteRestaurants(ids);
    toast.push(`تم حذف ${ids.length} مطعم`, "success");
  };

  const handleAdd = async (input: NewRestaurantInput) => {
    await addRestaurant(input);
    setShowAdd(false);
    toast.push("تمت إضافة المطعم الجديد ✓", "success");
  };

  const handleEdit = async (id: string, patch: NewRestaurantInput) => {
    await updateRestaurant(id, patch);
    setEditing(null);
    toast.push("تم حفظ التعديلات", "success");
  };

  const handleRestoreAll = async () => {
    if (!confirm("سيتم استرجاع جميع المطاعم المحذوفة والتعديلات. هل أنت متأكد؟")) return;
    await restoreAllRestaurants();
    toast.push("تم استرجاع البيانات الأصلية", "info");
  };

  const handleExport = () => {
    const rows = tab === "all" ? filtered : list;
    const csv = restaurantsToCsv(rows);
    const stamp = new Date().toISOString().slice(0, 10);
    downloadCsv(`faii-restaurants-${stamp}.csv`, csv);
    toast.push(`تم تصدير ${rows.length} مطعم إلى CSV`, "success");
  };

  const handleImportFile = async (file: File) => {
    setImporting(true);
    try {
      const text = await file.text();
      const rows = parseCsv(text);
      if (rows.length === 0) {
        toast.push("لم نعثر على بيانات صالحة. تأكد من وجود عمود title.", "error");
        return;
      }
      if (!confirm(`استيراد ${rows.length} مطعم إلى القاعدة؟`)) return;
      let ok = 0;
      for (const r of rows) {
        try {
          await addRestaurant({
            title: r.title,
            phone: r.phone || null,
            website: r.website,
            street: r.street || null,
            address: r.address || null,
            city: r.city || null,
          });
          ok++;
        } catch {
          /* skip row */
        }
      }
      toast.push(`تم استيراد ${ok} من ${rows.length}`, ok > 0 ? "success" : "error");
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };


  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="px-6 lg:px-12 py-8 border-b border-border bg-gradient-hero">
        <Link to="/" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-gold mb-4">
          <ArrowRight className="w-3.5 h-3.5" />
          العودة للوحة
        </Link>
        <div className="flex items-start justify-between gap-6 flex-wrap">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight flex items-center gap-3">
              <Database className="w-7 h-7 text-gold" />
              إدارة قاعدة البيانات
            </h1>
            <p className="text-sm text-muted-foreground mt-2">
              أضف مطاعم جديدة، عدّل البيانات الموجودة، احذف المكررات أو غير المناسبة.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) handleImportFile(f); }}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={importing}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border border-border bg-card hover:border-gold/50 disabled:opacity-50"
              title="استيراد من CSV (الأعمدة المطلوبة: title, phone, website, street, address, city)"
            >
              {importing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              استيراد CSV
            </button>
            <button
              onClick={handleExport}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border border-border bg-card hover:border-gold/50"
            >
              <Download className="w-3.5 h-3.5" />
              تصدير CSV
            </button>
            <button
              onClick={handleRestoreAll}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg border border-border bg-card hover:border-emerald/50"
            >
              <RefreshCcw className="w-3.5 h-3.5" />
              استرجاع الأصلية
            </button>
            <button
              onClick={() => setShowAdd(true)}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-2 rounded-lg bg-gold text-primary-foreground font-semibold hover:bg-gold/90"
            >
              <Plus className="w-3.5 h-3.5" />
              مطعم جديد
            </button>
          </div>

        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-6">
          <StatChip label="الإجمالي الحالي" value={stats.total} tone="gold" icon={<Database className="w-4 h-4" />} />
          <StatChip label="مكررات مكتشفة" value={duplicateCount} tone="destructive" icon={<Copy className="w-4 h-4" />} />
          <StatChip label="مضاف يدوياً" value={stats.added} tone="emerald" icon={<Plus className="w-4 h-4" />} />
          <StatChip label="محذوف من الأصل" value={stats.deleted} tone="muted" icon={<Trash2 className="w-4 h-4" />} />
        </div>
      </header>

      <main className="px-6 lg:px-12 py-8 max-w-7xl mx-auto space-y-6">
        <div className="flex items-center gap-2 border-b border-border">
          <TabBtn active={tab === "all"} onClick={() => setTab("all")} count={list.length}>
            كل المطاعم
          </TabBtn>
          <TabBtn active={tab === "duplicates"} onClick={() => setTab("duplicates")} count={duplicateCount} highlight={duplicateCount > 0}>
            <Copy className="w-3.5 h-3.5 inline-block ml-1" />
            المكررات
          </TabBtn>
        </div>

        {tab === "all" && (
          <>
            <div className="relative max-w-md">
              <Search className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="ابحث في كل البيانات..."
                className="w-full pr-9 pl-4 py-2.5 rounded-lg bg-card border border-border focus:border-gold/50 outline-none text-sm"
              />
            </div>
            <RestaurantTableManage rows={filtered} onEdit={setEditing} onDelete={handleDelete} />
          </>
        )}

        {tab === "duplicates" && (
          <DuplicatesView groups={duplicateGroups} onEdit={setEditing} />
        )}
      </main>

      {showAdd && (
        <RestaurantFormDialog
          title="إضافة مطعم جديد"
          onClose={() => setShowAdd(false)}
          onSave={handleAdd}
        />
      )}
      {editing && (
        <RestaurantFormDialog
          title={`تعديل: ${editing.title}`}
          initial={{
            title: editing.title,
            phone: editing.phone ?? "",
            website: editing.website ?? "",
            address: editing.address ?? "",
            street: editing.street ?? "",
            city: editing.city ?? "",
            rank: editing.rank,
          }}
          onClose={() => setEditing(null)}
          onSave={(v) => handleEdit(editing.id, v)}
        />
      )}
    </div>
  );
}

function StatChip({
  label, value, tone, icon,
}: { label: string; value: number; tone: "gold" | "emerald" | "destructive" | "muted"; icon: React.ReactNode }) {
  const toneCls =
    tone === "gold" ? "border-gold/30 bg-gold-soft text-gold" :
    tone === "emerald" ? "border-emerald/30 bg-emerald-soft text-emerald" :
    tone === "destructive" ? "border-destructive/30 bg-destructive/10 text-destructive-foreground" :
    "border-border bg-card text-muted-foreground";
  return (
    <div className={`rounded-xl border p-4 ${toneCls}`}>
      <div className="flex items-center justify-between">
        <div className="text-[11px] tracking-widest uppercase opacity-80">{label}</div>
        {icon}
      </div>
      <div className="text-3xl font-extrabold mt-2 tabular-nums">{value.toLocaleString("ar")}</div>
    </div>
  );
}

function TabBtn({
  active, onClick, count, highlight, children,
}: { active: boolean; onClick: () => void; count: number; highlight?: boolean; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors flex items-center gap-2 ${
        active
          ? "border-gold text-gold"
          : "border-transparent text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
      <span className={`text-[10px] tabular-nums px-1.5 py-0.5 rounded-full ${
        highlight ? "bg-destructive text-destructive-foreground" : "bg-surface-2 text-muted-foreground"
      }`}>
        {count.toLocaleString("ar")}
      </span>
    </button>
  );
}

/* ---------------- Table view ---------------- */

const PAGE = 30;

function RestaurantTableManage({
  rows, onEdit, onDelete,
}: { rows: Restaurant[]; onEdit: (r: Restaurant) => void; onDelete: (r: Restaurant) => void }) {
  const [page, setPage] = useState(1);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE));
  const cur = rows.slice((page - 1) * PAGE, page * PAGE);

  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-surface-2 text-muted-foreground text-[11px] uppercase tracking-wider">
            <tr>
              <th className="text-right px-3 py-2.5 w-12">#</th>
              <th className="text-right px-3 py-2.5">المطعم</th>
              <th className="text-right px-3 py-2.5">الفئة</th>
              <th className="text-right px-3 py-2.5">الشريحة</th>
              <th className="text-right px-3 py-2.5">الهاتف</th>
              <th className="text-right px-3 py-2.5">العنوان</th>
              <th className="text-right px-3 py-2.5 w-28">إجراء</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {cur.map((r, i) => {
              const seg = SEGMENT_META[r.segment];
              return (
                <tr key={r.id} className="hover:bg-accent/30">
                  <td className="px-3 py-2.5 text-[11px] text-muted-foreground tabular-nums">
                    {((page - 1) * PAGE + i + 1).toLocaleString("ar")}
                  </td>
                  <td className="px-3 py-2.5 font-semibold text-foreground">{r.title}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">{r.category}</td>
                  <td className="px-3 py-2.5">
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${
                      r.segment === "premium" ? "bg-gold-soft text-gold border-gold/30" :
                      r.segment === "medium" ? "bg-emerald-soft text-emerald border-emerald/30" :
                      "bg-accent text-muted-foreground border-border"
                    }`}>{seg.label}</span>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground text-xs tabular-nums">{r.phone ?? "—"}</td>
                  <td className="px-3 py-2.5 text-muted-foreground text-xs truncate max-w-[220px]">{r.street ?? r.address ?? "—"}</td>
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => onEdit(r)}
                        className="w-7 h-7 rounded-md hover:bg-gold-soft text-muted-foreground hover:text-gold flex items-center justify-center"
                        title="تعديل"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => onDelete(r)}
                        className="w-7 h-7 rounded-md hover:bg-destructive/15 text-muted-foreground hover:text-destructive-foreground flex items-center justify-center"
                        title="حذف"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
            {cur.length === 0 && (
              <tr><td colSpan={7} className="text-center py-10 text-sm text-muted-foreground">لا توجد نتائج</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-border text-xs text-muted-foreground">
          <span>
            صفحة <span className="text-foreground font-semibold">{page.toLocaleString("ar")}</span> من{" "}
            <span className="text-foreground font-semibold">{pages.toLocaleString("ar")}</span> • {rows.length.toLocaleString("ar")} سجل
          </span>
          <div className="flex items-center gap-1">
            <button disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-3 py-1.5 rounded-md border border-border bg-surface-2 disabled:opacity-40 hover:border-gold/40">السابق</button>
            <button disabled={page === pages} onClick={() => setPage((p) => Math.min(pages, p + 1))}
              className="px-3 py-1.5 rounded-md border border-border bg-surface-2 disabled:opacity-40 hover:border-gold/40">التالي</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------- Duplicates view ---------------- */

function DuplicatesView({
  groups, onEdit,
}: { groups: Restaurant[][]; onEdit: (r: Restaurant) => void }) {
  const toast = useToast();
  if (groups.length === 0) {
    return (
      <div className="rounded-2xl border border-emerald/30 bg-emerald-soft p-10 text-center">
        <CheckCircle2 className="w-10 h-10 text-emerald mx-auto mb-3" />
        <div className="text-lg font-bold text-foreground">لا توجد تكرارات في القاعدة</div>
        <div className="text-sm text-muted-foreground mt-2">القاعدة نظيفة — كل المطاعم فريدة بحسب الاسم والرقم.</div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-destructive-foreground shrink-0 mt-0.5" />
        <div>
          <div className="font-semibold text-foreground">تم العثور على {groups.length.toLocaleString("ar")} مجموعة مكررة</div>
          <div className="text-muted-foreground text-xs mt-1">
            يتم اكتشاف التكرار عبر مطابقة الاسم (بعد التطبيع) أو نفس رقم الهاتف. اختر أي نسخة تريد الإبقاء عليها واحذف الباقي.
          </div>
        </div>
      </div>

      {groups.map((group, gi) => (
        <DuplicateGroupCard key={gi} group={group} onEdit={onEdit} toast={toast} />
      ))}
    </div>
  );
}

function DuplicateGroupCard({
  group, onEdit, toast,
}: { group: Restaurant[]; onEdit: (r: Restaurant) => void; toast: ReturnType<typeof useToast> }) {
  // Default keeper: highest rank (lowest number) with the most data
  const score = (r: Restaurant) =>
    (r.phone ? 3 : 0) + (r.website ? 2 : 0) + (r.address ? 1 : 0) - r.rank / 10000;
  const initialKeep = group.slice().sort((a, b) => score(b) - score(a))[0].id;
  const [keepId, setKeepId] = useState(initialKeep);

  const deleteOthers = () => {
    const toDelete = group.filter((r) => r.id !== keepId).map((r) => r.id);
    if (toDelete.length === 0) return;
    if (!confirm(`حذف ${toDelete.length} نسخة مكررة والإبقاء على واحدة فقط؟`)) return;
    deleteRestaurants(toDelete);
    toast.push(`تم دمج المجموعة وحذف ${toDelete.length} نسخة`, "success");
  };

  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border bg-surface-2 flex items-center justify-between gap-3 flex-wrap">
        <div className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Copy className="w-4 h-4 text-destructive-foreground" />
          {group.length.toLocaleString("ar")} نسخ — "{group[0].title}"
        </div>
        <button
          onClick={deleteOthers}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-destructive/15 border border-destructive/30 text-destructive-foreground hover:bg-destructive/25"
        >
          <Trash2 className="w-3.5 h-3.5" />
          حذف المكررات والإبقاء على المحدّد
        </button>
      </div>
      <div className="divide-y divide-border">
        {group.map((r) => {
          const isKeep = r.id === keepId;
          return (
            <div key={r.id} className={`p-4 flex items-start gap-3 ${isKeep ? "bg-emerald-soft/40" : ""}`}>
              <label className="flex items-center gap-2 cursor-pointer pt-1">
                <input
                  type="radio"
                  name={`keep-${group[0].id}`}
                  checked={isKeep}
                  onChange={() => setKeepId(r.id)}
                  className="accent-emerald w-4 h-4"
                />
                <span className={`text-[10px] uppercase tracking-wider ${isKeep ? "text-emerald font-bold" : "text-muted-foreground"}`}>
                  {isKeep ? "الإبقاء" : "حذف"}
                </span>
              </label>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <div className="font-semibold text-foreground">{r.title}</div>
                  {r.segment === "premium" && <Crown className="w-3.5 h-3.5 text-gold" />}
                  <span className="text-[10px] text-muted-foreground tabular-nums">#{r.rank}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded border border-border bg-surface-2 text-muted-foreground">
                    {r.category}
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                  <div><b className="text-foreground/80">هاتف:</b> {r.phone ?? "—"}</div>
                  <div className="truncate"><b className="text-foreground/80">شارع:</b> {r.street ?? "—"}</div>
                  <div className="truncate"><b className="text-foreground/80">موقع:</b> {r.website ?? "—"}</div>
                </div>
              </div>
              <button
                onClick={() => onEdit(r)}
                className="text-xs text-muted-foreground hover:text-gold inline-flex items-center gap-1 shrink-0"
              >
                <Pencil className="w-3.5 h-3.5" />
                تعديل
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------- Add/Edit form ---------------- */

function RestaurantFormDialog({
  title, initial, onClose, onSave,
}: {
  title: string;
  initial?: NewRestaurantInput;
  onClose: () => void;
  onSave: (v: NewRestaurantInput) => void;
}) {
  const [form, setForm] = useState<NewRestaurantInput>({
    title: initial?.title ?? "",
    phone: initial?.phone ?? "",
    website: initial?.website ?? "",
    address: initial?.address ?? "",
    street: initial?.street ?? "",
    city: initial?.city ?? "إربد",
    rank: initial?.rank,
  });

  const submit = () => {
    if (!form.title.trim()) { alert("الاسم مطلوب"); return; }
    onSave(form);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div className="w-full max-w-lg rounded-2xl border border-border bg-card shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-gradient-hero">
          <h3 className="text-base font-bold">{title}</h3>
          <button onClick={onClose} className="w-8 h-8 rounded-md hover:bg-accent flex items-center justify-center">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 space-y-3">
          <Field label="اسم المطعم *">
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className={inputCls} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="رقم الهاتف">
              <input value={form.phone ?? ""} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                placeholder="07..." className={inputCls} dir="ltr" />
            </Field>
            <Field label="الموقع / Instagram">
              <input value={form.website ?? ""} onChange={(e) => setForm({ ...form, website: e.target.value })}
                placeholder="https://..." className={inputCls} dir="ltr" />
            </Field>
          </div>
          <Field label="الشارع">
            <input value={form.street ?? ""} onChange={(e) => setForm({ ...form, street: e.target.value })} className={inputCls} />
          </Field>
          <Field label="العنوان الكامل">
            <input value={form.address ?? ""} onChange={(e) => setForm({ ...form, address: e.target.value })} className={inputCls} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="المدينة">
              <input value={form.city ?? ""} onChange={(e) => setForm({ ...form, city: e.target.value })} className={inputCls} />
            </Field>
            <Field label="رتبة (Rank)">
              <input type="number" value={form.rank ?? ""} onChange={(e) => setForm({ ...form, rank: Number(e.target.value) || undefined })}
                placeholder="تلقائي" className={inputCls} dir="ltr" />
            </Field>
          </div>
        </div>
        <div className="px-5 py-3 border-t border-border flex items-center justify-end gap-2">
          <button onClick={onClose} className="px-3 py-2 text-xs rounded-lg border border-border bg-surface-2 hover:border-muted-foreground">إلغاء</button>
          <button onClick={submit} className="inline-flex items-center gap-1.5 px-4 py-2 text-xs rounded-lg bg-gold text-primary-foreground font-semibold hover:bg-gold/90">
            <Save className="w-3.5 h-3.5" />
            حفظ
          </button>
        </div>
      </div>
    </div>
  );
}

const inputCls = "w-full px-3 py-2 rounded-lg bg-background border border-border focus:border-gold/50 outline-none text-sm";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-1">{label}</div>
      {children}
    </label>
  );
}
