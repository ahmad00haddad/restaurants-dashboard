import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { z } from "zod";
import { readWebsite } from "@/lib/research.server";
import { DEFAULT_TEAM, type Lead, type LeadMessage, type LeadProfile, type TeamSettings } from "@/lib/leads";

const MODEL = "openai/gpt-6-astra";

async function ask(system: string, user: string): Promise<Record<string, unknown>> {
  const apiKey = process.env["LOVABLE_API_KEY"];
  if (!apiKey) throw new Error("AI غير مُفعّل في Lovable");
  const res = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: MODEL,
      reasoning_effort: "low",
      response_format: { type: "json_object" },
      messages: [{ role: "system", content: system }, { role: "user", content: user }],
    }),
  });
  if (res.status === 429) throw new Error("تجاوزت حد الاستخدام، حاول بعد قليل");
  if (res.status === 402) throw new Error("رصيد الذكاء الاصطناعي غير كافٍ");
  if (!res.ok) throw new Error(`فشل الذكاء الاصطناعي (${res.status})`);
  const json = (await res.json()) as { choices?: { message?: { content?: string } }[] };
  const raw = json.choices?.[0]?.message?.content ?? "";
  const m = raw.match(/\{[\s\S]*\}/);
  if (!m) throw new Error("ردّ غير مفهوم من الذكاء الاصطناعي");
  return JSON.parse(m[0]);
}

type Ctx = { supabase: any };

async function load(ctx: Ctx, id: string) {
  const [{ data: lead, error }, { data: msgs }, { data: st }] = await Promise.all([
    ctx.supabase.from("leads").select("*").eq("id", id).single(),
    ctx.supabase.from("lead_messages").select("*").eq("lead_id", id).eq("draft", false).order("created_at"),
    ctx.supabase.from("app_settings").select("data").eq("id", 1).maybeSingle(),
  ]);
  if (error) throw new Error(error.message);
  const team: TeamSettings = { ...DEFAULT_TEAM, ...((st?.data as Partial<TeamSettings>) ?? {}) };
  return { lead: lead as Lead, msgs: (msgs ?? []) as LeadMessage[], team };
}

function us(t: TeamSettings) {
  return [
    `Sender: ${t.senderName} — ${t.senderRole}, ${t.company}`,
    `Who we are: ${t.whoWeAre}`,
    `Services we offer:\n${t.services}`,
    `Priority: ${t.focus}`,
    `Portfolio (title | url | tags):\n${t.portfolio || "(none added yet — don't invent links)"}`,
  ].join("\n");
}

function them(l: Lead) {
  const f: [string, unknown][] = [
    ["type", l.kind], ["name", l.name], ["category", l.category], ["city", l.city], ["address", l.address],
    ["website", l.website], ["instagram", l.instagram], ["facebook", l.facebook], ["linkedin", l.linkedin],
    ["youtube", l.youtube], ["tiktok", l.tiktok], ["google rating", l.rating], ["our notes", l.notes],
  ];
  const lines = f.filter(([, v]) => v != null && v !== "").map(([k, v]) => `${k}: ${v}`);
  if (l.about) lines.push(`What their website says:\n${l.about}`);
  return lines.join("\n");
}

const VOICE = (t: TeamSettings) => `You write as ${t.senderName} himself — a working photographer/director, not a marketer and not a bot.
Rules:
- Every message must feel written for THIS client only. Open with the real hook from their profile (something specific they do/care about). Never generic praise.
- Talk about what THEY care about (their cause, their guests, their product, their donors) — not about us. One short line about us at most.
- Pitch ONE thing: the best service for them, as a concrete idea in one sentence. Don't list services.
- At most one portfolio link, the closest match, introduced casually. Never invent links, clients, numbers or prices.
- Short: email 4–7 lines, WhatsApp/Instagram 2–4 lines. No headings, bullets, bold, or hashtags. Max one emoji, only on WhatsApp/Instagram if natural.
- End with an easy question (yes/no or "which day suits you").
- Match their world: organisations → respectful, clear, impact-focused (Modern Standard Arabic or English); restaurants/cafés/shops → warm Jordanian dialect; international orgs or English sites → English.
- Banned phrases: "I hope this finds you well", "I wanted to reach out", "leverage", "elevate", "take your brand to the next level", "unlock", "in today's", "يسعدنا أن نضع بين أيديكم", "في ظل", "نفخر بتقديم", "حلول متكاملة", "نقلة نوعية", "لا تتردد".`;

// ---------- 1) Research + profile ----------
export const researchLead = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ id: z.string().uuid(), refetch: z.boolean().default(false) }).parse(d))
  .handler(async ({ data, context }) => {
    const ctx = context as Ctx;
    let { lead, team } = await load(ctx, data.id);
    const patch: Record<string, unknown> = {};
    if (lead.website && (!lead.about || data.refetch)) {
      const site = await readWebsite(lead.website);
      if (site) {
        patch.about = site.text;
        if (!lead.email && site.emails[0]) patch.email = site.emails[0];
        for (const [k, v] of Object.entries(site.socials)) if (!(lead as any)[k]) patch[k] = v;
        lead = { ...lead, ...patch } as Lead;
      }
    }
    const p = (await ask(
      `You research potential clients for a freelance photo/video team before anyone contacts them.
Figure out what kind of client this is, what they care about, and what visual content would genuinely help them.
Be honest: weak signals = low score. Organisations with programs, beneficiaries, donors, campaigns or anniversaries are strong documentary fits.
Return JSON only.`,
      `${us(team)}\n\nCLIENT:\n${them(lead)}\n\nReturn JSON:
{"summary":"who they are, one line","interests":["what they care about"],"content_needs":["visual content they likely need"],
"best_service":"one of our services","other_services":["..."],"angle":"one concrete film/photo idea made for them",
"hook":"a real specific detail from their info to open with (empty if none)","portfolio_pick":"url from our portfolio or empty",
"tone":"formal|warm|casual","lang":"ar|en","channel":"email|whatsapp|instagram","decision_maker":"role to address, e.g. Communications Officer",
"score":0-100,"why":"one short line"}`,
    )) as unknown as LeadProfile & { score: number };
    const { score, ...profile } = p;
    patch.profile = profile;
    patch.score = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));
    const { error } = await ctx.supabase.from("leads").update(patch).eq("id", data.id);
    if (error) throw new Error(error.message);
    return { score: patch.score as number };
  });

// ---------- 2) Write a message (first / follow-up / answer their reply) ----------
export const draftMessage = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) =>
    z.object({
      id: z.string().uuid(),
      mode: z.enum(["first", "followup", "reply"]),
      channel: z.enum(["email", "whatsapp", "instagram"]),
      hint: z.string().max(500).optional(),
    }).parse(d),
  )
  .handler(async ({ data, context }) => {
    const ctx = context as Ctx;
    const { lead, msgs, team } = await load(ctx, data.id);
    const history = msgs.map((m) => `[${m.direction === "in" ? "THEM" : "US"} · ${m.channel} · ${m.created_at.slice(0, 10)}]\n${m.body}`).join("\n\n");
    const task = {
      first: "Write the FIRST message to this client.",
      followup: `They haven't answered. Write follow-up #${lead.followups + 1}. Don't repeat the first message — add one new useful thing (a different relevant example, a quick idea, or a timing reason). 2–4 lines.${lead.followups >= 1 ? " This is the last follow-up: polite, leaves the door open." : ""}`,
      reply: `Answer their latest message exactly like a human would. Price question → ${team.priceGuide ? `use this guide: ${team.priceGuide}` : "no fixed number; propose a 15-minute call to scope it"}. Interested → propose two concrete times this week. Not now / no → thank them in one line and ask if you can check back later. Asked for work → 1–2 closest portfolio links.`,
    }[data.mode];

    const out = await ask(
      VOICE(team) + "\nReturn JSON only.",
      `${us(team)}\n\nCLIENT:\n${them(lead)}\n\nWHAT WE KNOW ABOUT THEM:\n${JSON.stringify(lead.profile ?? {}, null, 1)}\n\n` +
        `CONVERSATION SO FAR:\n${history || "(none)"}\n\nCHANNEL: ${data.channel}\nTASK: ${task}` +
        (data.hint ? `\nEXTRA INSTRUCTION FROM ${team.senderName}: ${data.hint}` : "") +
        `\n\nReturn JSON: {"subject":"${data.channel === "email" ? "short, human, not salesy" : ""}","body":"...",` +
        `"intent":"${data.mode === "reply" ? "interested|question|price|not_now|no|other" : ""}","status":"${data.mode === "reply" ? "replied|meeting|lost" : ""}","summary":"one line for the CRM"}`,
    );
    await ctx.supabase.from("lead_messages").delete().eq("lead_id", data.id).eq("draft", true);
    await ctx.supabase.from("lead_messages").insert({
      lead_id: data.id, channel: data.channel, direction: "out", draft: true,
      subject: (out.subject as string) || null, body: String(out.body ?? ""),
    });
    if (data.mode === "reply" && out.status) {
      const note = `${new Date().toISOString().slice(0, 10)}: ${out.summary ?? ""}`;
      await ctx.supabase.from("leads").update({
        status: out.status, notes: lead.notes ? `${lead.notes}\n${note}` : note,
      }).eq("id", data.id);
    }
    return { subject: out.subject as string | undefined, body: String(out.body ?? ""), intent: out.intent as string | undefined, summary: out.summary as string | undefined };
  });
