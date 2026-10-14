// Competitions, festivals, grants, fellowships, open calls and jobs found by the radar (tools/agent/radar.py) or added by hand.

export type OppKind = "competition" | "festival" | "grant" | "fellowship" | "residency" | "open_call" | "tender" | "job";
export type OppStatus = "new" | "saved" | "applying" | "submitted" | "won" | "skip";

export interface Opportunity {
  id: string;
  title: string;
  organizer: string | null;
  kind: OppKind;
  field: "photo" | "film" | "both";
  scope: "international" | "regional" | "local";
  url: string | null;
  deadline: string | null;
  prize: string | null;
  fee: string | null;
  eligibility: string | null;
  description: string | null;
  evidence: string | null;
  fit: number | null;
  status: OppStatus;
  notes: string | null;
  source: string | null;
  last_checked: string | null;
  created_at: string;
}

export const OPP_KIND_LABEL: Record<OppKind, string> = {
  competition: "مسابقة", festival: "مهرجان", grant: "منحة / تمويل", fellowship: "زمالة", residency: "إقامة فنية",
  open_call: "دعوة مفتوحة", tender: "مناقصة", job: "وظيفة / عمل",
};
export const OPP_STATUS_LABEL: Record<OppStatus, string> = {
  new: "جديد", saved: "محفوظ", applying: "أقدّم عليه", submitted: "قدّمت", won: "فزت", skip: "تجاهل",
};
export const OPP_SCOPE_LABEL = { international: "عالمي", regional: "عربي / إقليمي", local: "الأردن" } as const;
export const OPP_FIELD_LABEL = { photo: "فوتوغراف", film: "سينما / فيديو", both: "الاثنان" } as const;

/** Days until the deadline (negative = passed); null when unknown. */
export function daysLeft(deadline: string | null): number | null {
  if (!deadline) return null;
  const d = new Date(deadline + "T23:59:59").getTime();
  return Math.ceil((d - Date.now()) / 864e5);
}

/** Still worth looking at: not skipped / won / submitted, and not past its deadline. */
export const isActiveOpp = (o: Opportunity) => !["skip", "won", "submitted"].includes(o.status) && (daysLeft(o.deadline) ?? 1) >= 0;

/** Closing first, then unknown deadlines by fit. */
export function sortOpps(a: Opportunity, b: Opportunity) {
  const da = daysLeft(a.deadline), db = daysLeft(b.deadline);
  if (da != null && db != null) return da - db;
  if (da != null) return -1;
  if (db != null) return 1;
  return (b.fit ?? 0) - (a.fit ?? 0);
}

/** Japan is the travel goal: anything that mentions it can be shown on its own. */
const JAPAN = /japan|tokyo|kyoto|osaka|hokkaido|okinawa|aomori|yamagata|hiroshima|nikon|اليابان|طوكيو/i;
export const isJapanOpp = (o: Opportunity) =>
  JAPAN.test([o.title, o.organizer, o.description, o.eligibility, o.prize, o.url].filter(Boolean).join(" "));
