# Apply run, every two days (Claude does it by hand: no scripts, no templates)

Schedule (Ahmad, 2026-10-28): Sun, Tue, Thu at 10:00, not daily. Facts about Ahmad come from the ahmad-profile skill (bios, works, gear, references/applications.md); do not re-browse his sites, and never re-research a call listed in applications.md.

Ahmad's order (2026-10-25): every day Claude opens the opportunities we hold, studies each page in Brave, writes each message itself, and applies to as many as fit. No helper scripts, no ready-made templates, no agent-written drafts: Claude reads, thinks and writes every message fresh, one by one. Ahmad has authorised Claude to send these applications; this covers nothing outside this list.

## 1. Open the list
In Brave (Claude in Chrome tools; load them with one ToolSearch), open the FAII Sales dashboard: https://restaurants-dashboard.lovable.app/ (Ahmad is signed in in Brave). Tabs: 🔔 فرص الآن (leads with an open signal) and 🏆 (radar calls). Work from the nearest deadline. A lead that already has a sent or queued message is skipped. If the dashboard is not reachable, read the Supabase tables `leads` (signal not null, status new) and `opportunities` (status new/saved/applying) with a one-off query, never a stored script.

## 1b. Wider search (mandatory when the list is thin)
If the dashboard gives fewer than about 3 easy, suitable, open calls, search the open web yourself before stopping: Japan first (AIR programmes, prefecture residencies, Japan Foundation, transartists, resartis, on-the-move, callfor.org, opencallartist.com, curatorspace), then free residencies/fellowships worldwide open to a Jordanian director-cinematographer, then video/film/photo tenders and consultancies in Jordan and the region (UNGM, ReliefWeb, Impactpool, UNjobs, tenders sites, NGO procurement pages, LinkedIn posts). Prefer email or no-login forms, free, deadline 3+ days away. Add each good find to 🏆 (＋ أضف فرصة) before applying.

## 2. Choose
PRIORITY ONE: Japan. Every Japan opportunity (residencies, festivals, funds, commissions, anything to shoot or exhibit in Japan; Ahmad's goal is to travel there) comes first, gets the deepest study of its page (exact requirements, portfolio format, language, eligibility for a Jordanian, dates) and the most careful application, before anything else. If it is not clearly suitable, say exactly why in the report; do not drop it silently.
Authorisation (Ahmad, 2026-10-25): sending is authorised ONLY for opportunities (the 🔔 and 🏆 lists), after you opened and studied the page and judged it suitable. Never for ordinary prospecting, replies to clients or anything else.
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

## 5b. Keep the board clean
Applied items disappear: 🏆 📨 قدّمت, leads status تواصلنا (the 🔔 list now shows only leads never written to). Studied and dead (closed, fee, ineligible, festival entry) = ✖ تجاهل on the card, plus a line in ahmad-profile references/applications.md. Blocked-for-Ahmad items stay visible until he acts.

## 6. Report (short, Arabic)
Applied (who, channel, subject), skipped (who, why), blocked for Ahmad (who, link, what is needed), and one line on what to change in targeting or style. Commit and push any repo change.
