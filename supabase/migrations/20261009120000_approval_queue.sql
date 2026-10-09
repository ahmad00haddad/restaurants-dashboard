-- Approval queue: drafts wait for Ahmad's OK (Telegram or the site), then the local agent sends them from Gmail.
ALTER TABLE public.lead_messages
  ADD COLUMN IF NOT EXISTS review text,          -- pending | approved | rejected | sent | failed
  ADD COLUMN IF NOT EXISTS review_note text,     -- error message or who approved
  ADD COLUMN IF NOT EXISTS tg_message_id bigint, -- Telegram message holding the buttons
  ADD COLUMN IF NOT EXISTS sent_at timestamptz;
CREATE INDEX IF NOT EXISTS lead_messages_review_idx ON public.lead_messages(review) WHERE review IS NOT NULL;
