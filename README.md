# FAII Sales

Marketing & sales engine for FAII HOUSE (photo/video team). Built on Lovable + Supabase.

## How it works
1. **Collect** — on your PC: `tools/harvester/run.bat` → pick a kind (ngo / org / restaurant / hotel / brand / event) and cities.
   A real browser goes through Google Maps, then reads each website for email, Instagram/LinkedIn/YouTube/TikTok and what they do.
   Output: `leads-*.json`.
2. **Import** — in the site: "⬆️ استيراد من الجامع". The database removes duplicates (same phone, same website, or same name+city).
3. **Analyse** — "🧠 حلّل 20 عميل" or "ابحث وحلّل" on a single client. The AI reads their website and decides who they are,
   what they care about, what content they need, which of your services to pitch, the idea, the opening detail and the best portfolio piece.
4. **Write** — first message / follow-up / reply, written from that profile in their language and tone. Edit → open in Gmail, WhatsApp or Instagram → logged.
5. **Replies** — paste their reply; the AI reads the intent, updates the status and drafts the answer.
6. **Today** — replies waiting, follow-ups due (day 4, then day 10), meetings, best new leads.

Settings (who you are, services, portfolio, prices) are what the AI uses for every message, so keep them accurate.
