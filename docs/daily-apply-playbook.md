# Daily apply run (Claude does it by hand: no scripts, no templates)

Ahmad's order (2026-10-25): every day Claude opens the opportunities we hold, studies each page in Brave, writes each message itself, and applies to as many as fit. No helper scripts, no ready-made templates, no agent-written drafts: Claude reads, thinks and writes every message fresh, one by one. Ahmad has authorised Claude to send these applications; this covers nothing outside this list.

## 1. Open the list
In Brave (Claude in Chrome tools; load them with one ToolSearch), open the FAII Sales dashboard (find its tab among the open ones, or ask Ahmad once for the address and save it here). Tabs: 🔔 فرص الآن (leads with an open signal) and 🏆 (radar calls). Work from the nearest deadline. A lead that already has a sent or queued message is skipped. If the dashboard is not reachable, read the Supabase tables `leads` (signal not null, status new) and `opportunities` (status new/saved/applying) with a one-off query, never a stored script.

## 2. Choose
Apply: tenders / RFQs / consultancies / commissions for video, film or photo; NGOs, UN agencies, parties, foundations, cultural centres in Jordan and the region; free open calls that fit a filmmaker (festivals, residencies, fellowships).
Skip: restaurants, schools, nurseries, shops (0-2% reply rate, docs/outreach-style-guide.md); anything with a fee; calls that exclude individuals and Faii House does not meet as written; sensitive-beneficiary pitches cold; contacts on tools/harvester/blocklist.txt.
About 15 a day at most. If a message cannot be made specific to them, do not send it.

## 3. Study the page
Open the announcement. Read what they want, deadline, who may apply, how to apply, required attachments, language. If it is closed or expired, mark it skipped on the dashboard with the reason. Find the real apply address or form on the page itself.

## 4. Write it yourself
Read first: docs/outreach-style-guide.md, skills ahmad-profile and soft-outreach. Then write each message from scratch for that one organisation, in their language, with a different structure from the last one. No stock sentences copied between messages. Principles from the guide: one real specific line from their page; who Ahmad is in a line; the film idea or how his work answers their exact brief; one work link near their field (behance.net/ahmad00haddad, ahmadhaddad.lovable.app, faiihouse.lovable.app); calm close with an easy exit; signature أحمد حدّاد، مخرج ومدير تصوير، FAII HOUSE. No price in writing unless a form demands a figure (then use the quote builder numbers in ahmad-profile and flag it), no client names, no invented titles, nothing the profile lacks.

## 5. Send
- Email: from Ahmad's Gmail (ahmad000haddad@gmail.com) in Brave: compose, paste, send. Check Gmail Sent first so nobody is written twice. Then record it on the lead in the dashboard (status contacted / note).
- Form or portal: fill with real profile facts (name, ahmad000haddad@gmail.com, 0799256345, links), submit, then mark it on the dashboard (🏆 submitted, with a note).
- Stop and leave it for Ahmad (report it): account creation or login, passwords, CAPTCHA, fees or payment, ID uploads, data not in the profile, legal agreements beyond the call's own terms.

## 6. Report (short, Arabic)
Applied (who, channel, subject), skipped (who, why), blocked for Ahmad (who, link, what is needed), and one line on what to change in targeting or style. Commit and push any repo change.
