import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { z } from "zod";

const EMAIL_RE = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
const BAD_HOSTS = /(sentry|wixpress|wix\.com|example\.com|gmail\.com\/example|godaddy|domain\.|placeholder)/i;
const BAD_EXT = /\.(png|jpg|jpeg|gif|svg|webp|ico|css|js|woff|ttf)$/i;

const UA = "Mozilla/5.0 (compatible; FAIIHouseBot/1.0; +https://faiihouse.lovable.app)";

async function fetchText(url: string, timeoutMs = 8000): Promise<string | null> {
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), timeoutMs);
    const res = await fetch(url, {
      headers: { "User-Agent": UA, Accept: "text/html,*/*" },
      signal: ctl.signal,
      redirect: "follow",
    });
    clearTimeout(t);
    if (!res.ok) return null;
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("text") && !ct.includes("html")) return null;
    return (await res.text()).slice(0, 400_000);
  } catch {
    return null;
  }
}

function normalizeUrl(input: string): string | null {
  let s = input.trim();
  if (!s) return null;
  if (!/^https?:\/\//i.test(s)) s = "https://" + s;
  try {
    const u = new URL(s);
    // Skip pure social pages — no scrapable emails
    if (/facebook\.com|instagram\.com|tiktok\.com|twitter\.com|x\.com/i.test(u.host)) return null;
    return u.toString();
  } catch {
    return null;
  }
}

function extractEmails(html: string): string[] {
  const found = new Set<string>();
  // mailto: links
  for (const m of html.matchAll(/mailto:([^"'?\s>]+)/gi)) {
    const e = decodeURIComponent(m[1]).toLowerCase();
    if (isValidEmail(e)) found.add(e);
  }
  // Plain regex
  for (const m of html.matchAll(EMAIL_RE)) {
    const e = m[0].toLowerCase();
    if (isValidEmail(e)) found.add(e);
  }
  // Obfuscated "at" / "dot"
  const deobf = html
    .replace(/\s*\(\s*at\s*\)\s*|\s+at\s+|\s*\[\s*at\s*\]\s*/gi, "@")
    .replace(/\s*\(\s*dot\s*\)\s*|\s+dot\s+|\s*\[\s*dot\s*\]\s*/gi, ".");
  if (deobf !== html) {
    for (const m of deobf.matchAll(EMAIL_RE)) {
      const e = m[0].toLowerCase();
      if (isValidEmail(e)) found.add(e);
    }
  }
  return [...found];
}

function isValidEmail(e: string): boolean {
  if (e.length > 120 || e.length < 6) return false;
  if (BAD_EXT.test(e)) return false;
  if (BAD_HOSTS.test(e)) return false;
  if (/(sentry-|wixpress|@sentry|@wixpress|noreply@|no-reply@|donotreply@)/i.test(e)) return false;
  return /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(e);
}

/** Rank candidate emails: prefer info@ / contact@ / hello@ on the site's own domain. */
function pickBest(emails: string[], host?: string): string | null {
  if (emails.length === 0) return null;
  const scored = emails.map((e) => {
    const [local, dom] = e.split("@");
    let s = 0;
    if (host && dom && host.endsWith(dom.replace(/^www\./, ""))) s += 10;
    if (dom && host && dom.replace(/^www\./, "").endsWith(host.replace(/^www\./, ""))) s += 10;
    if (/^(info|contact|hello|hi|book|reservations|reserve|sales|orders)$/i.test(local)) s += 5;
    if (/gmail\.com|hotmail|yahoo|outlook/i.test(dom)) s -= 2;
    return { e, s };
  });
  scored.sort((a, b) => b.s - a.s);
  return scored[0].e;
}

async function scrapeSite(websiteUrl: string): Promise<string | null> {
  const start = normalizeUrl(websiteUrl);
  if (!start) return null;
  const origin = new URL(start).origin;
  const host = new URL(start).host.replace(/^www\./, "");

  const candidates = [
    start,
    origin + "/contact",
    origin + "/contact-us",
    origin + "/about",
    origin + "/about-us",
    origin + "/ar/contact",
    origin + "/en/contact",
  ];

  const emails = new Set<string>();
  for (const url of candidates) {
    const html = await fetchText(url);
    if (!html) continue;
    for (const e of extractEmails(html)) emails.add(e);
    if (url === start && emails.size === 0) {
      // Try to discover a contact link from homepage
      const contactHref = html.match(/href=["']([^"']*(contact|about|تواصل|اتصل)[^"']*)["']/i)?.[1];
      if (contactHref) {
        try {
          const abs = new URL(contactHref, origin).toString();
          const h2 = await fetchText(abs);
          if (h2) for (const e of extractEmails(h2)) emails.add(e);
        } catch { /* ignore */ }
      }
    }
    if (emails.size >= 3) break;
  }
  return pickBest([...emails], host);
}

export const scrapeEmailForRestaurant = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((v: unknown) => z.object({ restaurantId: z.string().uuid() }).parse(v))
  .handler(async ({ data, context }) => {
    const { restaurantId } = data;
    const { supabase } = context;
    const { data: row, error } = await supabase
      .from("restaurants")
      .select("id, website, email")
      .eq("id", restaurantId)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (!row) return { found: false as const, email: null, reason: "not_found" };
    if (!row.website) return { found: false as const, email: null, reason: "no_website" };

    const email = await scrapeSite(row.website);
    if (!email) return { found: false as const, email: null, reason: "not_found_on_site" };

    await supabase.from("restaurants").update({ email }).eq("id", restaurantId);
    return { found: true as const, email, reason: "ok" };
  });

export const bulkScrapeEmails = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((v: unknown) =>
    z.object({ limit: z.number().int().min(1).max(50).default(20) }).parse(v),
  )
  .handler(async ({ data, context }) => {
    const { supabase } = context;
    const { data: rows, error } = await supabase
      .from("restaurants")
      .select("id, website")
      .not("website", "is", null)
      .is("email", null)
      .limit(data.limit);
    if (error) throw new Error(error.message);
    let ok = 0;
    const results: { id: string; email: string | null }[] = [];
    for (const r of rows ?? []) {
      if (!r.website) continue;
      try {
        const email = await scrapeSite(r.website);
        if (email) {
          await supabase.from("restaurants").update({ email }).eq("id", r.id);
          ok++;
          results.push({ id: r.id, email });
        } else {
          results.push({ id: r.id, email: null });
        }
      } catch {
        results.push({ id: r.id, email: null });
      }
    }
    return { scanned: rows?.length ?? 0, found: ok, results };
  });
