import type { Restaurant, Segment } from "./restaurants";

export interface SenderInfo {
  senderName?: string;
  senderRole?: string;
  signature?: string;
  portfolioUrl?: string;
}

/* Deterministic PRNG seeded from restaurant id + nonce so each restaurant
   consistently gets a different, human-varied message. Bump `nonce` to reshuffle. */
function seededRandom(seed: string) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h += 0x6D2B79F5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const pick = <T,>(arr: T[], rnd: () => number) => arr[Math.floor(rnd() * arr.length)];

/* Openings — feel like a real person opening WhatsApp. Kept short, no emojis spam. */
const OPENERS = [
  (n: string) => `مرحباً ${n} 👋`,
  (n: string) => `أهلاً وسهلاً ${n}`,
  (n: string) => `مساء الخير ${n} 🌙`,
  (n: string) => `صباح الخير ${n} ☀️`,
  (n: string) => `أهلاً فريق ${n}`,
  (n: string) => `تحياتنا لكم من إربد — ${n}`,
  (n: string) => `يعطيكم العافية ${n}`,
];

const INTROS_PREMIUM = [
  (cat: string) => `تابعنا حضوركم في فئة «${cat}» وشدّنا مستوى الاهتمام بالتفاصيل — نادراً نلاقي علامة بهذا الوضوح البصري.`,
  (cat: string) => `ما شاء الله عليكم، البراند حاضر بقوة في مشهد «${cat}» بإربد.`,
  () => `اسمكم من الأسماء اللي دايماً تُذكر بين المطاعم الأنيقة بإربد.`,
  (cat: string) => `متابعينكم من فترة، وحابين نقولها بصراحة: مستوى الـ «${cat}» عندكم يستاهل محتوى بصري بمستوى أعلى.`,
];

const INTROS_MEDIUM = [
  (cat: string) => `فكرة «${cat}» عندكم لافتة، وبيّن من تفاصيلها إنكم شغّالين بشكل جدّي.`,
  (cat: string) => `تبعناكم على السوشال، والمحتوى عندكم فيه شخصية — بس نحس فيه مجال يوصل لجمهور أكبر بلمسة سينمائية.`,
  () => `الأماكن الجديدة اللي عم بتبني هويتها هي أحلى مرحلة نشتغل عليها كسينمائيين.`,
  (cat: string) => `فكرة الـ «${cat}» عندكم مميزة، ومحتاجة بس محتوى فيديو يعكسها بنفس مستوى الجودة.`,
];

const INTROS_TESTING = [
  () => `المطاعم الناشئة أقرب مكان لقلوبنا — فيها روح وحماس، بس أوقات المحتوى ما بيلحق بالفكرة.`,
  (cat: string) => `«${cat}» فئة جميلة للبداية، والمحتوى البصري بيقدر يقصّر عليكم سنة كاملة من المجهود.`,
  () => `دايماً بنقول لأصحاب المطاعم الجديدة: أول 100 يوم بيحددوا هوية المكان — والفيديو أقوى أداة فيهم.`,
];

const PITCH_PREMIUM = [
  "نشتغل معكم على فيلم قصير مخصص، مش ريل عادي — قصة حقيقية لتجربة الضيف عندكم.",
  "نصمّم لكم محتوى بصري بمستوى العلامات العالمية، بلمسة محلية.",
  "من الفكرة للسيناريو للتصوير للألوان، كل ثانية بتحكي شيء عن هويتكم.",
];

const PITCH_MEDIUM = [
  "بنحضر جلسة تصوير كاملة (طبق + مكان + وايبس) بيوم واحد، وبنسلمكم محتوى يكفّي شهرين.",
  "بنشتغل بميزانيات مرنة، وبنركّز على أعلى قيمة بأقل تكلفة إنتاج ممكنة.",
  "الحلول اللي بنقدمها مصمّمة عشان تعطي نتائج مباشرة على السوشال، مش بس محتوى للأرشيف.",
];

const PITCH_TESTING = [
  "عندنا باقة تجريبية مصمّمة خصيصاً للبدايات — سعر رمزي، تنفيذ احترافي كامل.",
  "بنقدر نبلش معكم بريل واحد قوي، وبعدين تقرروا إذا حابين نكمل.",
  "الفكرة إنكم تشوفوا الفرق قبل ما تلتزموا بأي شي كبير.",
];

const CTAs = [
  "لو حابين، بنبعثلكم نماذج من شغلنا الأخير مع مطاعم مشابهة؟",
  "شو رأيكم نحكي 5 دقايق تلفون هالأسبوع؟ بنشرحلكم الفكرة بدون أي التزام.",
  "بنقدر ننسّق زيارة قصيرة للمكان نتعرف عليكم أكثر ونطرح فكرة أولية؟",
  "نرسلكم البورتفوليو مع أسعار الباقات؟",
  "ايش أفضل وقت نتواصل فيه معكم؟",
  "إذا الفكرة عجبتكم، منقدر نجهزلكم اقتراح مبدئي خلال 24 ساعة.",
];

const CLOSERS = [
  "شكراً لوقتكم 🌿",
  "بانتظار ردكم متى ما ناسبكم.",
  "أهلاً بأي استفسار.",
  "ممتنين لكم مقدماً.",
  "نتمنالكم موسم موفق 🙌",
];

function firstNameFromTitle(t: string): string {
  // Trim common restaurant prefixes to make it feel personal
  return t
    .replace(/^(مطعم|كافيه|مقهى|كافي|كوفي|مطبخ|Restaurant|Cafe|Coffee|The)\s+/i, "")
    .trim();
}

function greetingByHour(): string {
  const h = new Date().getHours();
  if (h < 11) return "صباح الخير";
  if (h < 17) return "مساء الخير";
  return "مساء النور";
}

const INTROS: Record<Segment, ((cat: string) => string)[]> = {
  premium: INTROS_PREMIUM,
  medium: INTROS_MEDIUM,
  testing: INTROS_TESTING,
};
const PITCHES: Record<Segment, string[]> = {
  premium: PITCH_PREMIUM,
  medium: PITCH_MEDIUM,
  testing: PITCH_TESTING,
};

function signOff(info?: SenderInfo, rnd?: () => number): string {
  const sig = info?.signature || "FAII HOUSE — Cinematic Studio";
  const who = info?.senderName
    ? `${info.senderName}${info.senderRole ? " · " + info.senderRole : ""}`
    : "";
  const closer = rnd ? pick(CLOSERS, rnd) : CLOSERS[0];
  return `\n\n${closer}\n${who ? who + "\n" : ""}${sig}`;
}

export function buildHumanWhatsApp(
  r: Restaurant,
  info?: SenderInfo,
  nonce = 0,
): string {
  const rnd = seededRandom(`${r.id}|wa|${nonce}`);
  const name = firstNameFromTitle(r.title);
  const opener = pick(OPENERS, rnd)(name);
  const intro = pick(INTROS[r.segment], rnd)(r.category);
  const pitch = pick(PITCHES[r.segment], rnd);
  const cta = pick(CTAs, rnd);

  // A tiny stat block only for premium/medium — feels less templated when trimmed sometimes
  const showStats = rnd() > 0.5 && r.segment !== "testing";
  const stats = showStats
    ? `\n\n• +300 مشروع منجز\n• +140 علامة تجارية\n• +8 سنوات خبرة`
    : "";

  return `${opener}

معكم FAII HOUSE — استوديو إنتاج سينمائي بإربد.

${intro}

${pitch}${stats}

${cta}${signOff(info, rnd)}`;
}

export function buildHumanEmail(
  r: Restaurant,
  info?: SenderInfo,
  nonce = 0,
): { subject: string; body: string } {
  const rnd = seededRandom(`${r.id}|em|${nonce}`);
  const name = firstNameFromTitle(r.title);
  const subjects = [
    `FAII HOUSE × ${name} — فكرة محتوى بصري`,
    `اقتراح تعاون سينمائي لـ ${name}`,
    `محتوى فيديو مخصص لـ ${name} — من FAII HOUSE`,
    `${name}: فكرة سريعة لفيلم قصير عن المطعم`,
    `تعاون بصري بين FAII HOUSE و${name}`,
  ];
  const subject = pick(subjects, rnd);
  const intro = pick(INTROS[r.segment], rnd)(r.category);
  const pitch = pick(PITCHES[r.segment], rnd);
  const cta = pick(CTAs, rnd);
  const hello = greetingByHour();
  const portfolio = info?.portfolioUrl || "https://behance.net/ahmad00haddad";

  const body = `${hello} ${name}،

معكم فريق FAII HOUSE — استوديو إنتاج سينمائي مقره إربد، متخصصين بمحتوى المطاعم والكافيهات.

${intro}

${pitch}

${cta}

يمكنكم الاطلاع على أعمالنا هنا:
${portfolio}

الموقع: https://faiihouse.lovable.app${signOff(info, rnd)}`;

  return { subject, body };
}
