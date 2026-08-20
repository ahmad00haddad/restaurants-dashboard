import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { z } from "zod";

const InputSchema = z.object({
  channel: z.enum(["whatsapp", "email"]),
  tone: z.enum(["friendly", "formal", "short", "bold"]).default("friendly"),
  restaurant: z.object({
    title: z.string(),
    category: z.string().optional(),
    segment: z.string().optional(),
    city: z.string().nullish(),
    website: z.string().nullish(),
    rating: z.number().nullish(),
  }),
  service: z.string().optional(),
  price: z.number().optional(),
  currency: z.string().default("د.أ"),
  sender: z.object({
    name: z.string(),
    role: z.string(),
    signature: z.string(),
    portfolioUrl: z.string().optional(),
  }),
  notes: z.string().optional(),
  language: z.enum(["ar", "en"]).default("ar"),
});

const TONE_AR: Record<string, string> = {
  friendly: "ودّي ودافئ، بلهجة عربية بيضاء قريبة من الكلام اليومي الأردني",
  formal: "رسمي محترف ومختصر، مناسب لمالك مطعم كبير",
  short: "قصير جداً (٣-٤ أسطر كحد أقصى) ومباشر",
  bold: "جريء ولافت يبدأ بجملة تشد الانتباه فوراً",
};

export const composeOutreach = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: unknown) => InputSchema.parse(d))
  .handler(async ({ data }) => {
    const apiKey = process.env["LOVABLE_API_KEY"];
    if (!apiKey) throw new Error("AI غير مُفعّل");

    const r = data.restaurant;
    const isEmail = data.channel === "email";

    const system = [
      "أنت كاتب مبيعات بشري محترف يعمل لدى استوديو إنتاج سينمائي اسمه FAII HOUSE في الأردن.",
      "مهمتك كتابة رسالة تواصل أولى لمطعم بهدف حجز مكالمة قصيرة أو اجتماع.",
      "قواعد إلزامية:",
      "- اكتب بالعربية فقط (إلا إن طُلب غير ذلك) وبأسلوب بشري طبيعي، ممنوع أي أسلوب يوحي أنها مكتوبة بالذكاء الاصطناعي.",
      "- ممنوع العبارات المستهلكة مثل: 'يسعدنا أن نضع بين أيديكم'، 'في ظل التطور المتسارع'، 'نحن نفخر بتقديم'.",
      "- ممنوع الإيموجي أكثر من واحد، وممنوع علامات التعجب المتعددة.",
      "- اذكر اسم المطعم مرة واحدة بشكل طبيعي، واربط الفكرة بنوع مطبخه.",
      "- اختم بسؤال بسيط يسهل الرد عليه بنعم/لا.",
      isEmail
        ? "أعد النتيجة على شكل JSON فقط: {\"subject\": \"...\", \"body\": \"...\"}"
        : "أعد النتيجة على شكل JSON فقط: {\"body\": \"...\"}",
    ].join("\n");

    const user = [
      `المطعم: ${r.title}`,
      r.category ? `نوع المطبخ: ${r.category}` : "",
      r.segment ? `الشريحة: ${r.segment}` : "",
      r.city ? `المدينة: ${r.city}` : "",
      r.website ? `الموقع: ${r.website}` : "لا يملك موقعاً إلكترونياً (نقطة يمكن استغلالها)",
      data.service ? `الخدمة المقترحة: ${data.service}${data.price ? ` بسعر ${data.price} ${data.currency}` : ""}` : "",
      data.notes ? `ملاحظات المندوب: ${data.notes}` : "",
      `المُرسِل: ${data.sender.name} — ${data.sender.role} (${data.sender.signature})`,
      data.sender.portfolioUrl ? `رابط الأعمال: ${data.sender.portfolioUrl}` : "",
      `الأسلوب المطلوب: ${TONE_AR[data.tone]}`,
      `القناة: ${isEmail ? "بريد إلكتروني" : "رسالة واتساب"}`,
      data.language === "en" ? "اكتب الرسالة بالإنجليزية بدل العربية." : "",
    ].filter(Boolean).join("\n");

    const res = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "google/gemini-3-flash",
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
        temperature: 1,
      }),
    });

    if (res.status === 429) throw new Error("تجاوزت حد الاستخدام، حاول بعد قليل");
    if (res.status === 402) throw new Error("رصيد الذكاء الاصطناعي غير كافٍ");
    if (!res.ok) throw new Error(`فشل التوليد (${res.status})`);

    const json = (await res.json()) as { choices?: { message?: { content?: string } }[] };
    const raw = json.choices?.[0]?.message?.content ?? "";
    const cleaned = raw.replace(/```json|```/g, "").trim();

    let subject: string | undefined;
    let body = cleaned;
    try {
      const parsed = JSON.parse(cleaned) as { subject?: string; body?: string };
      if (parsed.body) body = parsed.body;
      if (parsed.subject) subject = parsed.subject;
    } catch {
      // Model returned plain text — use as-is.
    }

    return { subject, body: body.trim() };
  });
