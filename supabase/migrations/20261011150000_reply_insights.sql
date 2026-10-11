-- What each reply teaches us: studied by the PC agent whenever a reply (or auto-reply) arrives; shown on the site under 📊 القياس.
CREATE TABLE IF NOT EXISTS public.reply_insights (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid REFERENCES public.leads(id) ON DELETE CASCADE,
  message_id uuid,                 -- the inbound lead_messages row
  lead_kind text,
  category text NOT NULL,          -- interested | question | meeting_request | not_now | no_internal_capacity | no_budget | not_relevant | stop_contact | wrong_person | auto_reply_support_desk | auto_reply_generic | out_of_office | other
  objection text,                  -- what stands in the way, in their words
  lesson text,                     -- what it teaches (targeting, message, address)
  suggestion text,                 -- one concrete change to the system
  confidence int,
  applied boolean NOT NULL DEFAULT false,
  applied_note text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS reply_insights_message_idx ON public.reply_insights(message_id);
CREATE INDEX IF NOT EXISTS reply_insights_created_idx ON public.reply_insights(created_at DESC);
ALTER TABLE public.reply_insights ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Members all reply_insights" ON public.reply_insights;
CREATE POLICY "Members all reply_insights" ON public.reply_insights FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'))
  WITH CHECK (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'));
GRANT ALL ON public.reply_insights TO authenticated, service_role;
