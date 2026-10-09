CREATE TABLE IF NOT EXISTS public.agent_status (
  id int PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  last_seen timestamptz,
  model text,
  note text
);
INSERT INTO public.agent_status(id) VALUES (1) ON CONFLICT DO NOTHING;
GRANT SELECT, UPDATE ON public.agent_status TO authenticated;
GRANT ALL ON public.agent_status TO service_role;
ALTER TABLE public.agent_status ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Members read agent status" ON public.agent_status;
DROP POLICY IF EXISTS "Members update agent status" ON public.agent_status;
CREATE POLICY "Members read agent status" ON public.agent_status FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'));
CREATE POLICY "Members update agent status" ON public.agent_status FOR UPDATE TO authenticated
  USING (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'))
  WITH CHECK (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'));