import raw from "@/data/restaurants.json";

export type Segment = "premium" | "medium" | "testing";
export type Status = "new" | "email" | "whatsapp" | "meeting";

export interface RawRestaurant {
  address: string | null;
  city: string | null;
  phone: string | null;
  street: string | null;
  title: string;
  website?: string;
  email?: string | null;
  rank: number;
}

export interface Restaurant extends RawRestaurant {
  id: string;
  segment: Segment;
  category: string;
  rating: number; // simulated 3.8 - 4.9 deterministic from rank
}

const CATEGORY_RULES: Array<{ kw: RegExp; label: string }> = [
  { kw: /(سوشي|sushi)/i, label: "سوشي / آسيوي" },
  { kw: /(برجر|burger)/i, label: "برجر" },
  { kw: /(بيتزا|pizza)/i, label: "بيتزا" },
  { kw: /(كافيه|cafe|coffee|كوفي|قهوة)/i, label: "كافيه" },
  { kw: /(مشاوي|grill|شواء|كباب|broast|بروست|دجاج|chicken)/i, label: "مشاوي ودجاج" },
  { kw: /(شاورما|shawarma|فلافل|حمص|مناقيش|فطائر|عربي)/i, label: "مأكولات عربية" },
  { kw: /(باستا|pasta|ايطالي|italian|crepe|كريب|وافل|waffle|حلويات|sweet|desserts|ice|آيس)/i, label: "حلويات وإيطالي" },
  { kw: /(كرك|karak|شاي|tea|juice|عصير)/i, label: "مشروبات" },
  { kw: /(steak|ستيك|seafood|سمك|بحري)/i, label: "ستيك ومأكولات بحرية" },
];

export function detectCategory(title: string): string {
  for (const r of CATEGORY_RULES) if (r.kw.test(title)) return r.label;
  return "مطعم عام";
}

export function detectSegment(r: RawRestaurant): Segment {
  const hasSite = !!r.website && !/facebook\.com|instagram\.com/i.test(r.website);
  const hasSocial = !!r.website;
  if (hasSite && r.rank <= 150) return "premium";
  if (hasSocial || r.rank <= 400) return "medium";
  return "testing";
}

export function ratingFromRank(rank: number): number {
  const base = 4.9 - (Math.min(1000, Math.max(1, rank)) / 1000) * 1.1;
  return Math.round(base * 10) / 10;
}

/** Seed list computed once from JSON. Live editable list lives in useRestaurants. */
export const RESTAURANTS: Restaurant[] = (raw as RawRestaurant[]).map((r, i) => ({
  ...r,
  id: `r-${r.rank}-${i}`,
  segment: detectSegment(r),
  category: detectCategory(r.title),
  rating: ratingFromRank(r.rank),
}));

/** Normalize an Arabic/English title for duplicate matching. */
export function normalizeTitle(t: string): string {
  return (t || "")
    .toLowerCase()
    .replace(/[\u064B-\u065F\u0670]/g, "")       // diacritics
    .replace(/[إأآٱا]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/ؤ/g, "و")
    .replace(/ئ/g, "ي")
    .replace(/\s+/g, "")
    .replace(/[^\p{L}\p{N}]+/gu, "");
}

/** Find clusters of duplicate restaurants by normalized title OR same normalized phone. */
export function findDuplicateGroups(list: Restaurant[]): Restaurant[][] {
  const parent = new Map<number, number>();
  const find = (x: number): number => {
    let p = parent.get(x)!;
    while (p !== parent.get(p)) p = parent.get(p)!;
    parent.set(x, p);
    return p;
  };
  const union = (a: number, b: number) => {
    const ra = find(a), rb = find(b);
    if (ra !== rb) parent.set(ra, rb);
  };
  list.forEach((_, i) => parent.set(i, i));

  const byTitle = new Map<string, number[]>();
  const byPhone = new Map<string, number[]>();
  list.forEach((r, i) => {
    const t = normalizeTitle(r.title);
    if (t.length >= 3) {
      const arr = byTitle.get(t) ?? [];
      arr.push(i); byTitle.set(t, arr);
    }
    const p = normalizeJordanianPhone(r.phone);
    if (p && p.length >= 8) {
      const arr = byPhone.get(p) ?? [];
      arr.push(i); byPhone.set(p, arr);
    }
  });
  for (const arr of byTitle.values()) for (let i = 1; i < arr.length; i++) union(arr[0], arr[i]);
  for (const arr of byPhone.values()) for (let i = 1; i < arr.length; i++) union(arr[0], arr[i]);

  const groups = new Map<number, number[]>();
  list.forEach((_, i) => {
    const r = find(i);
    const g = groups.get(r) ?? [];
    g.push(i); groups.set(r, g);
  });
  return [...groups.values()]
    .filter((g) => g.length > 1)
    .map((g) => g.map((i) => list[i]).sort((a, b) => a.rank - b.rank));
}

/** Lead Score 0-100: priority signal combining segment, rating, contact channels, rank. */
export function leadScore(r: Restaurant): number {
  let s = 0;
  if (r.segment === "premium") s += 40;
  else if (r.segment === "medium") s += 25;
  else s += 10;
  s += Math.round(r.rating * 8);
  if (r.phone) s += 15;
  if (r.website) s += 10;
  s += Math.max(0, 10 - Math.floor(r.rank / 100));
  return Math.min(100, s);
}

export function scoreTier(score: number): { label: string; color: string } {
  if (score >= 75) return { label: "ساخن", color: "gold" };
  if (score >= 55) return { label: "دافئ", color: "emerald" };
  return { label: "بارد", color: "muted" };
}

export const SEGMENT_META: Record<Segment, { label: string; color: string; desc: string }> = {
  premium: { label: "Premium", color: "gold", desc: "علامات تجارية قوية بميزانية لمشاريع احترافية" },
  medium: { label: "Medium", color: "emerald", desc: "مطاعم نامية تفهم قيمة المحتوى" },
  testing: { label: "Testing", color: "muted", desc: "مطاعم مناسبة لمشاريع تجريبية وبناء محفظة" },
};

export const STATUS_META: Record<Status, { label: string; dot: string }> = {
  new: { label: "جديد", dot: "bg-muted-foreground" },
  email: { label: "تم إرسال إيميل", dot: "bg-sky-400" },
  whatsapp: { label: "تم إرسال واتساب", dot: "bg-emerald" },
  meeting: { label: "تم حجز اجتماع", dot: "bg-gold" },
};

export function cleanPhone(phone: string | null): string {
  if (!phone) return "";
  return phone.replace(/\D/g, "");
}

/** Normalize Jordanian numbers to international E.164 (no +) for wa.me. */
export function normalizeJordanianPhone(phone: string | null): string {
  let d = cleanPhone(phone);
  if (!d) return "";
  if (d.startsWith("00")) d = d.slice(2);
  if (d.startsWith("962")) return d;
  if (d.startsWith("0")) return "962" + d.slice(1);
  if (d.startsWith("7") && d.length === 9) return "962" + d;
  return d;
}

export function waLink(phone: string | null, msg: string): string {
  const clean = normalizeJordanianPhone(phone);
  return `https://wa.me/${clean}?text=${encodeURIComponent(msg)}`;
}

export function exportRestaurantsCSV(rows: Restaurant[]): string {
  const headers = [
    "rank",
    "title",
    "category",
    "segment",
    "rating",
    "phone",
    "phone_intl",
    "website",
    "address",
    "street",
    "city",
  ];
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(",")];
  for (const r of rows) {
    lines.push(
      [
        r.rank,
        r.title,
        r.category,
        r.segment,
        r.rating,
        r.phone ?? "",
        normalizeJordanianPhone(r.phone),
        r.website ?? "",
        r.address ?? "",
        r.street ?? "",
        r.city ?? "",
      ]
        .map(esc)
        .join(","),
    );
  }
  return "\uFEFF" + lines.join("\n");
}

export function downloadCSV(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export type { SenderInfo } from "./messages";
import { buildHumanWhatsApp, buildHumanEmail, type SenderInfo } from "./messages";

export function buildWhatsAppMessage(r: Restaurant, info?: SenderInfo, nonce = 0): string {
  return buildHumanWhatsApp(r, info, nonce);
}

export function buildEmailMessage(r: Restaurant, info?: SenderInfo, nonce = 0): { subject: string; body: string } {
  return buildHumanEmail(r, info, nonce);
}
