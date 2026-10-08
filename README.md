# FAII Sales

Marketing & sales engine for FAII HOUSE (photo/video team). Built on Lovable + Supabase.

## How it works
1. **Collect** — on your PC: `tools/harvester/run.bat` → pick a kind (ngo / org / restaurant / hotel / brand / event) and cities.
   A real browser goes through Google Maps, then reads each website for email, Instagram/LinkedIn/YouTube/TikTok and what they do.
   Optional **deep analysis** with [ScrapeGraphAI](https://github.com/ScrapeGraphAI/Scrapegraph-ai) on a local Ollama model (free, uses your GPU, ~15s/site; default `qwen2.5-coder:7b`, change with env `OLLAMA_MODEL`): extracts mission, programs, real project names, audiences, campaigns and comms contact, which the site's AI then uses to write.
   Output: `leads-*.json`.
   Kind `signals` = organisations in Jordan **hiring comms/media people or tendering video work right now** (ReliefWeb). Shown in the site under 🔔 فرص الآن, and the AI uses it as the reason to write today.
2. **Import** — in the site: "⬆️ استيراد من الجامع". The database removes duplicates (same phone, same website, or same name+city).
3. **Analyse** — "🧠 حلّل 20 عميل" or "ابحث وحلّل" on a single client. The AI reads their website and decides who they are,
   what they care about, what content they need, which of your services to pitch, the idea, the opening detail and the best portfolio piece.
4. **Write** — first message / follow-up / reply, written from that profile in their language and tone. Edit → open in Gmail, WhatsApp or Instagram → logged.
5. **Replies** — paste their reply; the AI reads the intent, updates the status and drafts the answer.
6. **Proposal** — once they're interested, "📄 اكتب عرضاً" writes a short proposal they can forward internally.
7. **Learning** — first messages are written with your past messages that got replies (same client type) as examples.
8. **Today** — replies waiting, follow-ups due (day 4, then day 10), meetings, best new leads.

Settings (who you are, services, portfolio, prices) are what the AI uses for every message, so keep them accurate.
