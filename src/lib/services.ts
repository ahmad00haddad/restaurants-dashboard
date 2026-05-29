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

export interface ProposalSettings {
  senderName?: string;
  senderRole?: string;
  signature?: string;
  discountPct?: number;
  currency?: string;
  portfolioUrl?: string;
}

export function buildServiceMessage(r: Restaurant, service: ServiceKey, s?: ProposalSettings): string {
  const pkg = SERVICE_BY_KEY[service];
  const cur = s?.currency || "د.أ";
  const price = priceFor(r, service).toLocaleString("ar");
  const sig = s?.signature || "FAII HOUSE";
  const who = s?.senderName ? `${s.senderName}${s.senderRole ? " — " + s.senderRole : ""}\n` : "";
  return `مرحباً ${r.title} ${pkg.emoji}

نحن FAII HOUSE — استوديو إنتاج سينمائي من إربد.

نقترح عليكم باقة "${pkg.label}" المصممة خصيصاً لمطاعم بمستوى "${r.category}".

ما تشمله الباقة:
${pkg.deliverables.map((d) => `  • ${d}`).join("\n")}

⏱️ المدة: ${pkg.duration}
💰 الاستثمار: ${price} ${cur}

كل مشروع نشتغل عليه بأعلى مستوى من التفاصيل البصرية.
هل تحبّون نرسل لكم نماذج من أعمالنا السابقة لمطاعم مشابهة؟

${who}${sig}`;
}

export interface ProposalLine { key: ServiceKey; label: string; emoji: string; duration: string; price: number; }
export interface ProposalData {
  restaurant: Restaurant;
  lines: ProposalLine[];
  subtotal: number;
  discountPct: number;
  discountAmount: number;
  total: number;
  currency: string;
  date: string;
  validityDays: number;
  senderName: string;
  senderRole: string;
  signature: string;
  portfolioUrl: string;
}

export function computeProposal(r: Restaurant, services: ServiceKey[], s?: ProposalSettings): ProposalData {
  const lines: ProposalLine[] = services.map((k) => {
    const pk = SERVICE_BY_KEY[k];
    return { key: k, label: pk.label, emoji: pk.emoji, duration: pk.duration, price: priceFor(r, k) };
  });
  const subtotal = lines.reduce((a, b) => a + b.price, 0);
  const discountPct = Math.max(0, Math.min(50, s?.discountPct ?? 10));
  const discountAmount = Math.round((subtotal * discountPct) / 100);
  return {
    restaurant: r, lines, subtotal, discountPct, discountAmount,
    total: subtotal - discountAmount,
    currency: s?.currency || "د.أ",
    date: new Date().toLocaleDateString("ar-JO"),
    validityDays: 14,
    senderName: s?.senderName || "أحمد حداد",
    senderRole: s?.senderRole || "Creative Director",
    signature: s?.signature || "FAII HOUSE — Cinematic Studio",
    portfolioUrl: s?.portfolioUrl || "https://behance.net/ahmad00haddad",
  };
}

export function buildProposal(r: Restaurant, services: ServiceKey[], s?: ProposalSettings): string {
  const p = computeProposal(r, services, s);
  const L: string[] = [];
  L.push(`عرض سعر — FAII HOUSE × ${p.restaurant.title}`);
  L.push(`التاريخ: ${p.date}`);
  L.push(`الشريحة: ${p.restaurant.segment.toUpperCase()}`);
  L.push("");
  L.push("الباقات المقترحة:");
  for (const ln of p.lines) {
    L.push(`  ${ln.emoji} ${ln.label} — ${ln.price.toLocaleString("ar")} ${p.currency}`);
    L.push(`     ${ln.duration}`);
  }
  L.push("");
  L.push(`المجموع قبل الخصم: ${p.subtotal.toLocaleString("ar")} ${p.currency}`);
  if (p.discountPct > 0) {
    L.push(`خصم (${p.discountPct}٪): -${p.discountAmount.toLocaleString("ar")} ${p.currency}`);
  }
  L.push(`الإجمالي النهائي: ${p.total.toLocaleString("ar")} ${p.currency}`);
  L.push("");
  L.push("ملاحظات:");
  L.push("• الأسعار شاملة المعالجة اللونية والتسليم النهائي.");
  L.push(`• مدة صلاحية العرض: ${p.validityDays} يوماً.`);
  L.push("");
  L.push(`${p.senderName} — ${p.senderRole}`);
  L.push(p.signature);
  L.push(p.portfolioUrl);
  return L.join("\n");
}

export function openPrintableProposal(r: Restaurant, services: ServiceKey[], s?: ProposalSettings) {
  const p = computeProposal(r, services, s);
  const html = `<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8"/>
<title>عرض سعر — ${p.restaurant.title}</title>
<style>
  *{box-sizing:border-box}
  body{font-family:'Cairo','Segoe UI',Tahoma,sans-serif;margin:0;background:#0c0c10;color:#e8e8ea;padding:40px}
  .page{max-width:800px;margin:0 auto;background:#15151c;border:1px solid #2a2a35;border-radius:18px;padding:48px;box-shadow:0 30px 80px rgba(0,0,0,.6)}
  .head{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #d4a84c;padding-bottom:20px;margin-bottom:28px}
  .brand{font-weight:900;font-size:28px;letter-spacing:.5px}
  .brand .g{color:#d4a84c}
  .sub{font-size:11px;letter-spacing:3px;color:#8a8a99;text-transform:uppercase;margin-top:4px}
  .meta{text-align:left;font-size:12px;color:#a0a0b0;line-height:1.8}
  h1{font-size:22px;margin:0 0 6px}
  .client{font-size:14px;color:#a0a0b0;margin-bottom:32px}
  .row{display:flex;justify-content:space-between;align-items:flex-start;padding:18px 0;border-bottom:1px solid #232330}
  .row .name{font-weight:700;font-size:15px}
  .row .dur{font-size:11px;color:#8a8a99;margin-top:4px}
  .row .price{font-weight:800;color:#d4a84c;font-size:16px;white-space:nowrap}
  .totals{margin-top:24px;padding:20px;background:#1c1c25;border-radius:12px}
  .totals .line{display:flex;justify-content:space-between;font-size:13px;margin-bottom:8px;color:#a0a0b0}
  .totals .total{display:flex;justify-content:space-between;font-size:20px;font-weight:900;color:#d4a84c;padding-top:12px;border-top:1px solid #2a2a35;margin-top:8px}
  .notes{margin-top:28px;font-size:12px;color:#8a8a99;line-height:1.9}
  .sig{margin-top:36px;padding-top:20px;border-top:1px solid #2a2a35;font-size:13px;color:#c8c8d0}
  .sig .who{font-weight:700;color:#e8e8ea}
  .sig .url{color:#7ad9b8;direction:ltr;display:inline-block;margin-top:6px;font-size:11px}
  @media print {
    body{background:#fff;color:#111;padding:0}
    .page{background:#fff;border:none;box-shadow:none;color:#111}
    .brand .g{color:#b8902f}
    .row{border-bottom-color:#eee}
    .row .price,.totals .total{color:#b8902f}
    .totals{background:#f9f7f2}
    .sub,.meta,.client,.row .dur,.totals .line,.notes{color:#555}
  }
  .actions{position:fixed;top:20px;left:20px;display:flex;gap:8px}
  .btn{background:#d4a84c;color:#000;border:0;padding:10px 16px;border-radius:8px;font-weight:700;cursor:pointer;font-family:inherit}
  .btn.ghost{background:#2a2a35;color:#e8e8ea}
  @media print { .actions{display:none} }
</style></head><body>
<div class="actions">
  <button class="btn" onclick="window.print()">طباعة / حفظ PDF</button>
  <button class="btn ghost" onclick="window.close()">إغلاق</button>
</div>
<div class="page">
  <div class="head">
    <div>
      <div class="brand"><span class="g">FAII</span> HOUSE</div>
      <div class="sub">Cinematic Production Studio</div>
    </div>
    <div class="meta">
      <div>التاريخ: ${p.date}</div>
      <div>صالح لـ ${p.validityDays} يوماً</div>
      <div>الشريحة: ${p.restaurant.segment.toUpperCase()}</div>
    </div>
  </div>
  <h1>عرض سعر — ${p.restaurant.title}</h1>
  <div class="client">الفئة: ${p.restaurant.category}${p.restaurant.address ? " • " + p.restaurant.address : ""}</div>
  ${p.lines.map((ln) => `
    <div class="row">
      <div>
        <div class="name">${ln.emoji} ${ln.label}</div>
        <div class="dur">${ln.duration}</div>
      </div>
      <div class="price">${ln.price.toLocaleString("ar")} ${p.currency}</div>
    </div>`).join("")}
  <div class="totals">
    <div class="line"><span>المجموع</span><span>${p.subtotal.toLocaleString("ar")} ${p.currency}</span></div>
    ${p.discountPct > 0 ? `<div class="line"><span>خصم ${p.discountPct}٪</span><span>-${p.discountAmount.toLocaleString("ar")} ${p.currency}</span></div>` : ""}
    <div class="total"><span>الإجمالي</span><span>${p.total.toLocaleString("ar")} ${p.currency}</span></div>
  </div>
  <div class="notes">
    • الأسعار شاملة المعالجة اللونية الكاملة والتسليم النهائي.<br/>
    • يمكن تقسيم الدفعات على مرحلتين (50٪ مقدّم — 50٪ عند التسليم).<br/>
    • نوفّر مراجعة واحدة مجانية لكل تسليم.
  </div>
  <div class="sig">
    <div class="who">${p.senderName} — ${p.senderRole}</div>
    <div>${p.signature}</div>
    <div class="url">${p.portfolioUrl}</div>
  </div>
</div>
</body></html>`;
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(html);
  w.document.close();
}

