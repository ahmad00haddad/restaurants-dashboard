// Reads a lead's website like a person would before pitching: home, about, work/projects, contact.

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36";
const EMAIL_RE = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
const BAD_EMAIL = /(sentry|wixpress|example\.|domain\.|\.(png|jpe?g|gif|svg|webp|css|js)$|noreply|no-reply|@2x)/i;
const SOCIAL: Record<string, RegExp> = {
  instagram: /https?:\/\/(?:www\.)?instagram\.com\/[A-Za-z0-9_.]+/,
  facebook: /https?:\/\/(?:www\.|m\.)?facebook\.com\/[A-Za-z0-9_.\-]+/,
  linkedin: /https?:\/\/(?:[a-z]+\.)?linkedin\.com\/(?:company|in)\/[A-Za-z0-9_\-%]+/,
  youtube: /https?:\/\/(?:www\.)?youtube\.com\/(?:@|c\/|channel\/|user\/)[A-Za-z0-9_\-]+/,
  tiktok: /https?:\/\/(?:www\.)?tiktok\.com\/@[A-Za-z0-9_.]+/,
};
const PAGE_HINT = /contact|about|who-we-are|our-work|projects|programs|programmes|stories|news|menu|تواصل|من-نحن|اتصل|مشاريع|برامج/i;

async function get(url: string): Promise<string> {
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 9000);
    const res = await fetch(url, { headers: { "User-Agent": UA, Accept: "text/html" }, signal: ctl.signal, redirect: "follow" });
    clearTimeout(t);
    if (!res.ok || !(res.headers.get("content-type") || "").includes("html")) return "";
    return (await res.text()).slice(0, 500_000);
  } catch {
    return "";
  }
}

function toText(html: string): string {
  return html
    .replace(/<(script|style|noscript|svg|nav|footer)[^>]*>[\s\S]*?<\/\1>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&#39;|&rsquo;/g, "'").replace(/&quot;/g, '"')
    .replace(/\s+/g, " ")
    .trim();
}

export interface SiteFindings {
  emails: string[];
  socials: Record<string, string>;
  text: string;
}

export async function readWebsite(website: string): Promise<SiteFindings | null> {
  let start = website.trim();
  if (!/^https?:\/\//i.test(start)) start = "https://" + start;
  let origin: string;
  try {
    origin = new URL(start).origin;
  } catch {
    return null;
  }
  const home = await get(start);
  if (!home) return null;
  const links = [...home.matchAll(/href=["']([^"'#]+)["']/gi)].map((m) => m[1]).filter((l) => PAGE_HINT.test(l));
  const extra = [...new Set(links)].slice(0, 4).map((l) => {
    try { return new URL(l, origin + "/").toString(); } catch { return ""; }
  }).filter((u) => u.startsWith(origin));
  const pages = [home, ...(await Promise.all((extra.length ? extra : [origin + "/contact", origin + "/about"]).map(get)))];
  const blob = pages.join(" ");

  const host = new URL(start).host.replace(/^www\./, "");
  const emails = [...new Set([...blob.matchAll(/mailto:([^"'?\s>]+)/gi)].map((m) => m[1]).concat(blob.match(EMAIL_RE) ?? []))]
    .map((e) => decodeURIComponent(e).toLowerCase().replace(/\.$/, ""))
    .filter((e) => !BAD_EMAIL.test(e))
    .sort((a, b) => Number(b.endsWith(host)) - Number(a.endsWith(host)) ||
      Number(/^(info|contact|hello|media|comm|pr|marketing)/.test(b)) - Number(/^(info|contact|hello|media|comm|pr|marketing)/.test(a)));

  const socials: Record<string, string> = {};
  for (const [k, re] of Object.entries(SOCIAL)) {
    const m = blob.match(re)?.[0];
    if (m && !/\/(sharer|share|tr|plugins|intent)\b/.test(m)) socials[k] = m;
  }
  const text = pages.filter(Boolean).map((p) => toText(p).slice(0, 1500)).join("\n---\n").slice(0, 4000);
  return { emails, socials, text };
}

export interface PageSummary {
  url: string;
  title: string;
  text: string;
}

/** Behance project pages are bot-protected, but the profile page lists every project's id + name. */
async function behanceProjects(profileUrl: string): Promise<PageSummary[]> {
  const h = await get(profileUrl.replace(/behance\.com/, "behance.net"));
  const out = new Map<string, PageSummary>();
  for (const m of h.matchAll(/gallery\/(\d+)\/([A-Za-z0-9\-%_.]+)/g)) {
    if (out.has(m[1])) continue;
    const seg = h.slice(Math.max(0, h.indexOf(`"id":${m[1]}`)), h.indexOf(`"id":${m[1]}`) + 1500);
    const name = seg.match(/"name":"([^"]{2,120})"/)?.[1] ?? decodeURIComponent(m[2]).replace(/-/g, " ");
    out.set(m[1], { url: `https://www.behance.net/gallery/${m[1]}/${m[2]}`, title: name, text: "Behance project" });
  }
  return [...out.values()];
}

/** Crawl a site (sitemap first, then links from the home page) — used to read our own portfolio site. */
export async function crawlSite(siteUrl: string, max = 40): Promise<PageSummary[]> {
  let start = siteUrl.trim();
  if (!/^https?:\/\//i.test(start)) start = "https://" + start;
  if (/behance\.(net|com)/i.test(start)) return behanceProjects(start);
  const origin = new URL(start).origin;
  const queue = new Set<string>([start]);

  const sitemap = await get(origin + "/sitemap.xml");
  for (const m of sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)) if (m[1].startsWith(origin)) queue.add(m[1]);
  const home = await get(start);
  for (const m of home.matchAll(/href=["']([^"'#?]+)["']/gi)) {
    try {
      const u = new URL(m[1], origin + "/").toString();
      if (u.startsWith(origin) && !/\.(jpe?g|png|gif|webp|svg|pdf|css|js|xml)$/i.test(u)) queue.add(u);
    } catch { /* skip */ }
  }
  const urls = [...queue].slice(0, max);
  const pages = await Promise.all(urls.map(async (url) => {
    const h = url === start ? home : await get(url);
    if (!h) return null;
    const title = (h.match(/<title[^>]*>([^<]*)<\/title>/i)?.[1] ?? "").trim();
    const videos = [...h.matchAll(/(?:youtube\.com\/embed\/|player\.vimeo\.com\/video\/)[A-Za-z0-9_-]+/g)].map((m) => m[0]).slice(0, 3);
    return { url, title, text: (toText(h).slice(0, 600) + (videos.length ? ` [videos: ${videos.join(", ")}]` : "")) };
  }));
  return pages.filter((p): p is PageSummary => !!p);
}
