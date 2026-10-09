import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { z } from "zod";
import { crawlSite, readWebsite } from "@/lib/research.server";
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

/** Our past first messages that got a reply from the same kind of client — the AI learns the style that works. */
async function winners(ctx: Ctx, lead: Lead): Promise<string> {
  const { data: won } = await ctx.supabase.from("leads").select("id")
    .eq("kind", lead.kind).in("status", ["replied", "meeting", "won"]).neq("id", lead.id).limit(30);
  if (!won?.length) return "";
  const { data: msgs } = await ctx.supabase.from("lead_messages").select("lead_id, body, created_at")
    .in("lead_id", won.map((w: { id: string }) => w.id)).eq("direction", "out").eq("draft", false).order("created_at");
  const firsts = new Map<string, string>();
  for (const m of msgs ?? []) if (!firsts.has(m.lead_id)) firsts.set(m.lead_id, m.body);
  const ex = [...firsts.values()].slice(-3);
  if (!ex.length) return "";
  return "\n\nOUR PAST FIRST MESSAGES THAT GOT REPLIES from similar clients (learn what works — never copy):\n" +
    ex.map((e, i) => `#${i + 1}\n${e}`).join("\n\n");
}

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
    t.portfolioSite ? `Full portfolio website (may be mentioned once as "the rest of our work"): ${t.portfolioSite}` : "",
    `PAST CLIENTS we really worked with (name | sector | language) — the only names you may mention:
${t.pastClients || "(none listed — mention no client names)"}`,
    `LINKS — send exactly one, the full body of work, never a single project:
- ${PERSONAL_SITE} — Ahmad's own site (films, documentaries, client logos). Default; best for organisations, NGOs, institutions, culture and documentaries.
- ${TEAM_SITE} — FAII House, the production team. Best for brands, restaurants, cafés, companies, campaigns and larger productions.
- ${BEHANCE} — Behance. Only for design-minded creative clients (agencies, studios) or when asked for a portfolio file.`,
    `Portfolio (for choosing which work to NAME as proof — do not paste these links) (title | url | tags). Lines starting with ★ are our FLAGSHIP works — always choose a ★ work when one is reasonably related; use others only if no ★ fits. A work whose tags say "ONLY …" may be used only in that case (e.g. only for schools, only around Ramadan):\n${t.portfolio || "(none added yet — don't invent links)"}`,
  ].join("\n");
}

function them(l: Lead) {
  const f: [string, unknown][] = [
    ["type", l.kind], ["name", l.name], ["category", l.category], ["city", l.city], ["address", l.address],
    ["website", l.website], ["instagram", l.instagram], ["facebook", l.facebook], ["linkedin", l.linkedin],
    ["youtube", l.youtube], ["tiktok", l.tiktok], ["google rating", l.rating], ["our notes", l.notes],
    ["LIVE SIGNAL (why now)", l.signal ? `${l.signal}${l.signal_until ? ` — closes ${l.signal_until}` : ""} ${l.signal_url ?? ""}` : null],
  ];
  const lines = f.filter(([, v]) => v != null && v !== "").map(([k, v]) => `${k}: ${v}`);
  if (l.about) lines.push(`What their website says:\n${l.about}`);
  return lines.join("\n");
}

const PERSONAL_SITE = "https://ahmadhaddad.lovable.app";
const TEAM_SITE = "https://faiihouse.lovable.app";
const BEHANCE = "https://www.behance.net/ahmad00haddad";

/** From the study of our 63 past clients: which language each kind of client actually works in. */
const LANGUAGE_RULES = `Language — decide from their own website/profile first. Defaults, from studying our 62 real past clients
(international bodies and companies work in English; local organisations and businesses in Arabic):
- UN agencies, international NGOs and donors, EU programmes, embassies, international brands, tech/corporate companies → English: polished, plain, warm.
- Jordanian royal/national foundations and institutions (QRTA, JOHUD, Jordan River…) → formal, elegant Modern Standard Arabic (English only if their site is English-only).
- Local charities, community and youth initiatives → refined Modern Standard Arabic, warm and human.
- Restaurants, cafés, roasteries, sweets, pharmacies, shops, salons, local brands → Arabic in a respectful, light Jordanian register (never slang).
- Private schools, publishers, local companies → their website's main language; if bilingual → Arabic.
- One language per message. If unsure for an international organisation in Jordan, choose English.`;

const VOICE = (t: TeamSettings) => `You write as ${t.senderName}, a director and photographer whose work speaks for itself (UNICEF, USAID, Mercy Corps, UN Women, QRTA and many Jordanian brands).
You are not selling and you are not asking. You noticed something genuinely interesting in their world, and you're opening a conversation between two people who care about good work.

THE POSTURE — this decides everything:
- Write as an equal, from abundance. Someone with a full calendar who chose to write because their story caught his eye.
- The message is about THEM and their story. We appear only as quiet evidence: one fact, one piece of work.
- Give before you ask: offer one sharp, specific insight about their story or how it could be seen (the thing a great director would notice). That insight is the value of the message.
- Never position yourself as a supplier. Never say or imply: "we offer", "our services", "we are ready", "we'd be glad/happy/honoured to", "if you ever need", "don't hesitate", "hope to hear from you", "looking forward to working with you", "sorry to bother", "thank you for your time", "opportunity to collaborate".
- No permission-asking, no apologising, no thanking in advance, no "I won't write again", no opt-out lines, no flattery, no adjectives about ourselves (no "professional", "creative", "high-quality", "passionate").
- The close is calm and confident, one short line that leaves a door open without pushing, e.g. "If the timing is right on your side, I'd enjoy a conversation about it." / "إن كان التوقيت مناسباً لديكم، يسعدني أن نتحدث." — never a question that begs for a reply, never a request for a meeting.

CRAFT:
- Open with a precise observation from the profile hook: a real detail of their work, place or people. If removing the first line leaves the message unchanged, rewrite it.
- Right after the observation, ONE quiet line that introduces the sender together with the proof, so a stranger knows who is writing: e.g. "I'm Ahmad Haddad, a director and photographer based in Jordan; I've documented similar stories for USAID and QRTA." / "أنا أحمد حدّاد، مخرج ومصوّر من الأردن، وثّقت قصصاً مشابهة لـ USAID وأكاديمية الملكة رانيا." Name the closest ★ work or past client only if truly close.
- Then one insight/idea about their story (one sentence, concrete, visual). Then the calm close. One close only; never add "I am available…".
- Short: email 4–6 lines of body. WhatsApp/Instagram 2–3 lines. No bullets, bold, hashtags, emojis in emails; no exclamation marks; no em dashes in the body.
- Subject (email): 2–5 calm words about THEM (their programme, place or story), never about us. No "collaboration", "proposal", "opportunity", "services".
- Greeting: their organisation or the right person. Sign-off: ${t.senderName}, then ${t.senderRole}, ${t.company}, then ONE labelled link on its own line: "Selected work: <site>" (English) or "بعض أعمالي: <site>" (Arabic), choosing the site that fits them (see LINKS). That is the only link; never link a single project. WhatsApp/Instagram: no subject.
${LANGUAGE_RULES}
- Never invent facts, clients, numbers, prices or links.`;

/** Second pass: an editor who rejects anything that reads as needy, generic or self-centred, and rewrites it. */
const EDITOR = `You are the toughest editor of outreach messages for a respected director. You judge one draft.
Score 1-10 on each: dignity (zero neediness, no supplier tone, no begging/thanking/apologising), specificity (could only have been written to this client),
insight (gives them a real idea about their own story), restraint (short, calm, no adjectives about us), language (natural, elegant, correct for this audience).
If ANY score is below 9, rewrite the message to score 10 on all, keeping the same language, facts, link and signature. Never add new facts, links or client names. Keep exactly one link: the site in the signature; remove any link to a single project.
Return JSON only: {"scores":{"dignity":n,"specificity":n,"insight":n,"restraint":n,"language":n},"subject":"...","body":"final message"}`;

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
"hook":"a real specific detail from their info to open with (empty if none)","portfolio_pick":"name of the closest ★ work to mention (no url)","link_pick":"which ONE site to send: personal | team | behance",
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
      mode: z.enum(["first", "followup", "reply", "proposal"]),
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
      followup: "They haven't answered — that's fine. Write ONE gracious, brief note (2–3 lines) that adds value: share a different piece of work relevant to them, or a thoughtful observation. No reminder of the previous message, no 'following up', no pressure. Close by leaving the door open. This is the only follow-up we ever send.",
      proposal: `They are interested. Write a short, clear proposal email they can forward internally: one line on their goal (in their words), the idea, what we deliver (bullets allowed here: e.g. film length, versions, photos, subtitles), timeline, what we need from them, and investment ${team.priceGuide ? `based on: ${team.priceGuide}` : "as 'tailored once we understand the scope' (no numbers)"}. Professional, composed tone — a studio proposal, not a sales pitch. Then the next step. Keep it under 200 words.`,
      reply: `Answer their latest message exactly like a human would. Price question → ${team.priceGuide ? `use this guide: ${team.priceGuide}` : "no fixed number; offer to understand the project first, since every piece is tailored"}. Interested → suggest meeting or a short call at their convenience, offering two possible times. Not now / no → thank them graciously in one line and wish them well; no request to check back. Asked for work → 1–2 closest portfolio links with one line of context each.`,
    }[data.mode];

    const learned = data.mode === "first" ? await winners(ctx, lead) : "";
    const signalRule = lead.signal
      ? "\n- They have a LIVE signal (tender, or hiring for comms/media). You may mention it with tact as context (e.g. that we've seen they're expanding their communications work), offering our work as a resource. Never sound opportunistic."
      : "";
    const out = await ask(
      VOICE(team) + signalRule + "\nReturn JSON only.",
      `${us(team)}\n\nCLIENT:\n${them(lead)}\n\nWHAT WE KNOW ABOUT THEM:\n${JSON.stringify(lead.profile ?? {}, null, 1)}\n\n` +
        `CONVERSATION SO FAR:\n${history || "(none)"}${learned}\n\nCHANNEL: ${data.channel}\nTASK: ${task}` +
        (data.hint ? `\nEXTRA INSTRUCTION FROM ${team.senderName}: ${data.hint}` : "") +
        `\n\nReturn JSON: {"subject":"${data.channel === "email" ? "short, human, not salesy" : ""}","body":"...",` +
        `"intent":"${data.mode === "reply" ? "interested|question|price|not_now|no|other" : ""}","status":"${data.mode === "reply" ? "replied|meeting|lost" : ""}","summary":"one line for the CRM"}` +
        `\nThe "body" must always contain the full message text. If you have a concern about this client, still write the best message and put the concern in "summary".`,
    );
    // Models sometimes nest the text or use another key — find it, and never save an empty draft.
    const text = [out.body, out.message, out.email, out.text, (out.message as any)?.body]
      .find((v) => typeof v === "string" && v.trim().length > 20) as string | undefined;
    if (!text) throw new Error(`لم يكتب الذكاء رسالة${out.summary ? ` — ملاحظته: ${out.summary}` : ""}. جرّب مرة أخرى أو أضف توجيهاً.`);
    out.body = text.trim();
    // Editor pass: catch anything needy or generic before Ahmad ever sees it.
    try {
      const ed = await ask(EDITOR, `CLIENT:
${them(lead)}

WHAT WE KNOW:
${JSON.stringify(lead.profile ?? {})}

CHANNEL: ${data.channel}
SUBJECT: ${out.subject ?? ""}
DRAFT:
${out.body}`);
      if (typeof ed.body === "string" && ed.body.trim().length > 20) {
        out.body = ed.body.trim();
        if (typeof ed.subject === "string" && ed.subject.trim()) out.subject = ed.subject.trim();
      }
    } catch { /* keep the first draft if the editor fails */ }
    await ctx.supabase.from("lead_messages").delete().eq("lead_id", data.id).eq("draft", true);
    await ctx.supabase.from("lead_messages").insert({
      lead_id: data.id, channel: data.channel, direction: "out", draft: true,
      subject: (out.subject as string) || null, body: out.body,
    });
    if (data.mode === "reply" && out.status) {
      const note = `${new Date().toISOString().slice(0, 10)}: ${out.summary ?? ""}`;
      await ctx.supabase.from("leads").update({
        status: out.status, notes: lead.notes ? `${lead.notes}\n${note}` : note,
      }).eq("id", data.id);
    }
    return { subject: out.subject as string | undefined, body: String(out.body ?? ""), intent: out.intent as string | undefined, summary: out.summary as string | undefined };
  });

// ---------- 3) Build the portfolio list from our own website ----------
export const importPortfolio = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => z.object({ url: z.string().min(4) }).parse(d))
  .handler(async ({ data }) => {
    const pages = await crawlSite(data.url);
    if (!pages.length) throw new Error("تعذّر قراءة الموقع");
    const out = await ask(
      "You catalogue a photographer/filmmaker's portfolio website. Identify pages that show a specific project/work (not home, contact, about, blog index). Return JSON only.",
      "PAGES:\n" + pages.map((p) => `URL: ${p.url}\nTITLE: ${p.title}\n${p.text}`).join("\n\n") + "\n\n" +
        'Return JSON: {"items":[{"title":"short project title incl. client if shown","url":"page url","tags":"type and sector, e.g. documentary, ngo, refugees, food, event, commercial, hotel"}]}',
    );
    const items = (out.items as { title: string; url: string; tags: string }[] | undefined) ?? [];
    return { lines: items.map((i) => `${i.title} | ${i.url} | ${i.tags}`).join("\n"), pages: pages.length };
  });
