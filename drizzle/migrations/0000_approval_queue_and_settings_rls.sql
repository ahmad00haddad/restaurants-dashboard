CREATE INDEX IF NOT EXISTS leads_signal_idx ON public.leads(signal_until) WHERE signal IS NOT NULL;
ALTER TABLE public.lead_messages
  ADD COLUMN IF NOT EXISTS review text,
  ADD COLUMN IF NOT EXISTS review_note text,
  ADD COLUMN IF NOT EXISTS tg_message_id bigint,
  ADD COLUMN IF NOT EXISTS sent_at timestamptz;
CREATE INDEX IF NOT EXISTS lead_messages_review_idx ON public.lead_messages(review) WHERE review IS NOT NULL;
DROP POLICY IF EXISTS "Members read settings" ON public.app_settings;
CREATE POLICY "Members read settings" ON public.app_settings FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(), 'admin'::public.app_role) OR public.has_role(auth.uid(), 'user'::public.app_role));