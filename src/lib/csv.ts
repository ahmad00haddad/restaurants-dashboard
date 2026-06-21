import type { Restaurant } from "./restaurants";

const COLS: { key: keyof Restaurant; label: string }[] = [
  { key: "rank", label: "Rank" },
  { key: "title", label: "Title" },
  { key: "category", label: "Category" },
  { key: "segment", label: "Segment" },
  { key: "phone", label: "Phone" },
  { key: "website", label: "Website" },
  { key: "street", label: "Street" },
  { key: "address", label: "Address" },
  { key: "city", label: "City" },
];

function esc(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function restaurantsToCsv(rows: Restaurant[]): string {
  const header = COLS.map((c) => c.label).join(",");
  const lines = rows.map((r) => COLS.map((c) => esc(r[c.key])).join(","));
  return "\uFEFF" + [header, ...lines].join("\n");
}

export function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export interface ParsedRow {
  title: string;
  phone?: string;
  website?: string;
  street?: string;
  address?: string;
  city?: string;
}

function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQ) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') inQ = false;
      else cur += ch;
    } else {
      if (ch === ",") { out.push(cur); cur = ""; }
      else if (ch === '"') inQ = true;
      else cur += ch;
    }
  }
  out.push(cur);
  return out;
}

export function parseCsv(text: string): ParsedRow[] {
  const clean = text.replace(/^\uFEFF/, "").trim();
  if (!clean) return [];
  const lines = clean.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length === 0) return [];
  const headers = splitCsvLine(lines[0]).map((h) => h.trim().toLowerCase());
  const idx = (names: string[]) => {
    for (const n of names) {
      const i = headers.indexOf(n);
      if (i >= 0) return i;
    }
    return -1;
  };
  const ti = idx(["title", "اسم", "name", "المطعم"]);
  const pi = idx(["phone", "هاتف", "tel", "mobile"]);
  const wi = idx(["website", "موقع", "url", "site"]);
  const si = idx(["street", "شارع"]);
  const ai = idx(["address", "عنوان"]);
  const ci = idx(["city", "مدينة"]);
  const out: ParsedRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cells = splitCsvLine(lines[i]);
    const title = ti >= 0 ? cells[ti]?.trim() : "";
    if (!title) continue;
    out.push({
      title,
      phone: pi >= 0 ? cells[pi]?.trim() : undefined,
      website: wi >= 0 ? cells[wi]?.trim() : undefined,
      street: si >= 0 ? cells[si]?.trim() : undefined,
      address: ai >= 0 ? cells[ai]?.trim() : undefined,
      city: ci >= 0 ? cells[ci]?.trim() : undefined,
    });
  }
  return out;
}
