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

function detectCategory(title: string): string {
  for (const r of CATEGORY_RULES) if (r.kw.test(title)) return r.label;
  return "مطعم عام";
}

function detectSegment(r: RawRestaurant): Segment {
  const hasSite = !!r.website && !/facebook\.com|instagram\.com/i.test(r.website);
  const hasSocial = !!r.website;
  if (hasSite && r.rank <= 150) return "premium";
  if (hasSocial || r.rank <= 400) return "medium";
  return "testing";
}

function rating(rank: number): number {
  // Higher rank (smaller number) → higher rating. Deterministic.
  const base = 4.9 - (rank / 1000) * 1.1;
  return Math.round(base * 10) / 10;
}

export const RESTAURANTS: Restaurant[] = (raw as RawRestaurant[]).map((r, i) => ({
  ...r,
  id: `r-${r.rank}-${i}`,
  segment: detectSegment(r),
  category: detectCategory(r.title),
  rating: rating(r.rank),
}));

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

export function waLink(phone: string | null, msg: string): string {
  const clean = cleanPhone(phone);
  return `https://wa.me/${clean}?text=${encodeURIComponent(msg)}`;
}

export function buildWhatsAppMessage(r: Restaurant): string {
  const name = r.title;
  if (r.segment === "premium") {
    return `مرحباً ${name} 🎬

نحن FAII HOUSE — استوديو إنتاج سينمائي من إربد، متخصصون في تصوير المطاعم والكافيهات الراقية.

تابعنا حضوركم في فئة "${r.category}" — ومستوى العلامة يستحق محتوى بصري بنفس الفخامة.

✦ +300 مشروع منجز
✦ +140 علامة تجارية
✦ +8 سنوات خبرة

نقترح جلسة قصيرة لمناقشة فكرة فيلم قصير مخصص لـ ${name} — هل يناسبكم هذا الأسبوع؟

— فريق FAII HOUSE`;
  }
  if (r.segment === "medium") {
    return `أهلاً ${name} 👋

من فريق FAII HOUSE للإنتاج السينمائي في إربد.

نشتغل على محتوى فيديو احترافي يرفع تفاعل المطاعم على السوشال — ولفت انتباهنا مفهومكم في "${r.category}".

نصمم كل مشروع خصيصاً لطبيعة المطعم، بميزانيات مرنة.

نشاركك أعمالنا ونقترح فكرة سريعة تناسبكم — موافق؟`;
  }
  return `مرحباً ${name} 🌱

FAII HOUSE — تصوير فيديوغرافي سينمائي من إربد.

عندنا باقة تجريبية مناسبة للمطاعم الناشئة في فئة "${r.category}" — فيديو قصير احترافي يساعدكم على رؤية أثر المحتوى البصري على جمهوركم.

تحبّون نرسل التفاصيل؟`;
}

export function buildEmailMessage(r: Restaurant): { subject: string; body: string } {
  const subject =
    r.segment === "premium"
      ? `FAII HOUSE × ${r.title} — اقتراح فيلم سينمائي مخصص`
      : r.segment === "medium"
      ? `فكرة محتوى فيديو لـ ${r.title}`
      : `باقة تجريبية للمطاعم الناشئة — FAII HOUSE`;
  const body = `${buildWhatsAppMessage(r)}

—
الموقع: https://faiihouse.lovable.app
أعمالنا: https://behance.net/ahmad00haddad`;
  return { subject, body };
}
