import type { Restaurant, Segment } from "./restaurants";

export type ServiceKey = "reel" | "menu" | "brand" | "opening" | "social";

export interface ServicePackage {
  key: ServiceKey;
  label: string;
  short: string;
  // Price in JOD per segment
  price: Record<Segment, number>;
  duration: string;
  deliverables: string[];
  emoji: string;
}

export const SERVICES: ServicePackage[] = [
  {
    key: "reel",
    label: "Reel سينمائي قصير",
    short: "ريل 15-30 ثانية",
    price: { premium: 350, medium: 220, testing: 120 },
    duration: "يوم تصوير + 3 أيام مونتاج",
    deliverables: ["ريل عمودي 9:16", "نسخة أفقية للإعلانات", "ألوان سينمائية"],
    emoji: "🎬",
  },
  {
    key: "menu",
    label: "تصوير منيو احترافي",
    short: "صور أطباق فاخرة",
    price: { premium: 500, medium: 320, testing: 180 },
    duration: "يوم تصوير + معالجة لونية",
    deliverables: ["20 صورة عالية الدقة", "خلفيات متعددة", "نسخ للسوشال والطباعة"],
    emoji: "🍽️",
  },
  {
    key: "brand",
    label: "فيلم تعريفي للعلامة",
    short: "Brand Film 60-90 ثانية",
    price: { premium: 1200, medium: 800, testing: 450 },
    duration: "أسبوع كامل (سيناريو → تسليم)",
    deliverables: ["فيلم 60-90 ثانية", "تيزر قصير", "موسيقى أصلية", "سيناريو وستوري بورد"],
    emoji: "🎥",
  },
  {
    key: "opening",
    label: "تغطية افتتاح",
    short: "Event Coverage",
    price: { premium: 800, medium: 550, testing: 350 },
    duration: "يوم التغطية + 5 أيام تسليم",
    deliverables: ["فيلم آفترموفي", "ريلز للسوشال", "صور مختارة", "بث مباشر اختياري"],
    emoji: "🎉",
  },
  {
    key: "social",
    label: "باقة سوشال شهرية",
    short: "محتوى مستمر",
    price: { premium: 1800, medium: 1100, testing: 700 },
    duration: "شهرياً — جلسة + تسليم أسبوعي",
    deliverables: ["8 ريلز شهرياً", "صور للمنشورات", "تخطيط محتوى", "إدارة لونية موحدة"],
    emoji: "📱",
  },
];

export const SERVICE_BY_KEY: Record<ServiceKey, ServicePackage> = Object.fromEntries(
  SERVICES.map((s) => [s.key, s]),
) as Record<ServiceKey, ServicePackage>;

export function priceFor(r: Restaurant, service: ServiceKey): number {
  return SERVICE_BY_KEY[service].price[r.segment];
}

export function buildServiceMessage(r: Restaurant, service: ServiceKey): string {
  const s = SERVICE_BY_KEY[service];
  const price = priceFor(r, service).toLocaleString("ar");
  return `مرحباً ${r.title} ${s.emoji}

نحن FAII HOUSE — استوديو إنتاج سينمائي من إربد.

نقترح عليكم باقة "${s.label}" المصممة خصيصاً لمطاعم بمستوى "${r.category}".

ما تشمله الباقة:
${s.deliverables.map((d) => `  • ${d}`).join("\n")}

⏱️ المدة: ${s.duration}
💰 الاستثمار: ${price} دينار

كل مشروع نشتغل عليه بأعلى مستوى من التفاصيل البصرية.
هل تحبّون نرسل لكم نماذج من أعمالنا السابقة لمطاعم مشابهة؟

— فريق FAII HOUSE`;
}

export function buildProposal(r: Restaurant, services: ServiceKey[]): string {
  const lines: string[] = [];
  lines.push(`عرض سعر — FAII HOUSE × ${r.title}`);
  lines.push(`التاريخ: ${new Date().toLocaleDateString("ar-JO")}`);
  lines.push(`الشريحة: ${r.segment.toUpperCase()}`);
  lines.push("");
  lines.push("الباقات المقترحة:");
  let total = 0;
  for (const k of services) {
    const s = SERVICE_BY_KEY[k];
    const p = priceFor(r, k);
    total += p;
    lines.push(`  ${s.emoji} ${s.label} — ${p.toLocaleString("ar")} دينار`);
    lines.push(`     ${s.duration}`);
  }
  lines.push("");
  lines.push(`الإجمالي: ${total.toLocaleString("ar")} دينار`);
  lines.push("");
  lines.push("ملاحظات:");
  lines.push("• الأسعار شاملة المعالجة اللونية والتسليم النهائي.");
  lines.push("• يُمنح خصم 10٪ عند حجز باقتين أو أكثر.");
  lines.push("• مدة صلاحية العرض: 14 يوماً.");
  lines.push("");
  lines.push("— FAII HOUSE Cinematic Studio");
  lines.push("https://faiihouse.lovable.app");
  return lines.join("\n");
}
