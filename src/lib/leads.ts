// Shared types for leads, AI profiles and team settings (used by client and server).

export type LeadKind = "ngo" | "org" | "restaurant" | "brand" | "hotel" | "event" | "other";
export type LeadStatus = "new" | "contacted" | "replied" | "meeting" | "won" | "lost" | "skip";
export type Channel = "email" | "whatsapp" | "instagram";

export const KIND_LABEL: Record<LeadKind, string> = {
  ngo: "منظمة / NGO", org: "مؤسسة", restaurant: "مطعم / كافيه", brand: "براند / متجر", hotel: "فندق / سياحة", event: "فعاليات", other: "أخرى",
};
export const STATUS_LABEL: Record<LeadStatus, string> = {
  new: "جديد", contacted: "تواصلنا", replied: "ردّ", meeting: "اجتماع", won: "صفقة", lost: "خسرناه", skip: "تجاهل",
};

/** What the AI learned about a client before writing to them. */
export interface LeadProfile {
  summary: string;          // who they are, one line
  interests: string[];      // what they care about (causes, audience, products, values)
  content_needs: string[];  // visual content they likely need
  best_service: string;     // the one thing to pitch first
  other_services: string[];
  angle: string;            // concrete idea specific to them
  hook: string;             // the real detail to open the message with
  portfolio_pick: string;   // url of the most relevant work
  tone: "formal" | "warm" | "casual";
  lang: "ar" | "en";
  channel: Channel;
  decision_maker: string;   // who to address (role) if inferable
  why: string;
}

export interface Lead {
  id: string;
  kind: LeadKind;
  name: string;
  category: string | null;
  city: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  instagram: string | null;
  facebook: string | null;
  linkedin: string | null;
  youtube: string | null;
  tiktok: string | null;
  rating: number | null;
  maps_url: string | null;
  about: string | null;
  profile: LeadProfile | null;
  score: number | null;
  status: LeadStatus;
  followups: number;
  next_action_at: string | null;
  needs_reply: boolean;
  notes: string | null;
  source: string | null;
  signal: string | null;        // live buying signal: tender / comms hiring
  signal_url: string | null;
  signal_until: string | null;
  deal_value: number | null;
  created_at: string;
}

export interface LeadMessage {
  id: string;
  lead_id: string;
  channel: string;
  direction: "in" | "out";
  subject: string | null;
  body: string;
  draft: boolean;
  created_at: string;
}

export interface TeamSettings {
  senderName: string;
  senderRole: string;
  company: string;
  whoWeAre: string;   // honest description of the team
  services: string;   // one per line
  portfolioSite: string; // our own website with all the work
  pastClients: string;   // one per line: name | sector | language
  portfolio: string;  // one per line: title | url | tags
  priceGuide: string;
  focus: string;      // what to prioritise when it fits
}

export const DEFAULT_TEAM: TeamSettings = {
  senderName: "أحمد حداد",
  senderRole: "Director & Cinematographer",
  company: "FAII HOUSE",
  whoWeAre: "مخرج ومدير تصوير فريلانس مع فريق صغير في الأردن. نصوّر كل شيء: وثائقيات، أفلام للمنظمات، إعلانات، تصوير منتجات وأكل، فعاليات، ومحتوى سوشال ميديا.",
  services: [
    "Documentary / impact film — منظمات، مشاريع، قصص مستفيدين، تقارير للمانحين",
    "Brand film / commercial — شركات، براندات، فنادق",
    "Food & menu photography + reels — مطاعم وكافيهات",
    "Event coverage (photo + aftermovie) — مؤتمرات، إطلاقات، حفلات",
    "Social media content (monthly reels) — أي نشاط يحتاج محتوى مستمر",
    "Product photography — متاجر وبراندات",
    "Portraits / team photos — مؤسسات وشركات",
  ].join("\n"),
  portfolioSite: "",
  pastClients: "",
  portfolio: "",
  priceGuide: "",
  focus: "الوثائقيات وأفلام الأثر للمنظمات هي الأولوية عندما تناسب العميل.",
};

export function portfolioLines(s: TeamSettings) {
  return s.portfolio.split("\n").map((l) => l.split("|").map((p) => p.trim())).filter((p) => p[1]);
}

export function waLink(phone: string, text: string) {
  let d = phone.replace(/\D/g, "");
  if (d.startsWith("00")) d = d.slice(2);
  if (d.startsWith("0")) d = "962" + d.slice(1);
  return `https://wa.me/${d}?text=${encodeURIComponent(text)}`;
}

export function gmailLink(to: string, subject: string, body: string) {
  return `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(to)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
