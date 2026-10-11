-- Opportunity radar: photo / film competitions, festivals, grants, fellowships, open calls, tenders and jobs that are NOT clients.
-- The PC agent fills it every day (tools/agent/radar.py); the site shows it sorted by deadline.

CREATE TABLE IF NOT EXISTS public.opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  organizer text,
  kind text NOT NULL DEFAULT 'competition',   -- competition | festival | grant | fellowship | residency | open_call | tender | job
  field text NOT NULL DEFAULT 'both',          -- photo | film | both
  scope text NOT NULL DEFAULT 'international', -- international | regional | local
  url text UNIQUE,
  deadline date,
  prize text,
  fee text,
  eligibility text,
  description text,
  evidence text,                               -- the exact words in the source that justify the deadline / eligibility
  fit int,                                     -- 0-100, computed in code
  status text NOT NULL DEFAULT 'new',          -- new | saved | applying | submitted | won | skip
  notes text,
  source text,                                 -- seed | radar | manual
  last_checked date,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS opportunities_deadline_idx ON public.opportunities(deadline NULLS LAST);
CREATE INDEX IF NOT EXISTS opportunities_status_idx ON public.opportunities(status);

CREATE OR REPLACE FUNCTION public.opportunities_touch() RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
BEGIN NEW.updated_at := now(); RETURN NEW; END $$;
DROP TRIGGER IF EXISTS opportunities_touch ON public.opportunities;
CREATE TRIGGER opportunities_touch BEFORE UPDATE ON public.opportunities FOR EACH ROW EXECUTE FUNCTION public.opportunities_touch();

ALTER TABLE public.opportunities ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Members all opportunities" ON public.opportunities;
CREATE POLICY "Members all opportunities" ON public.opportunities FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'))
  WITH CHECK (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'));
GRANT ALL ON public.opportunities TO authenticated, service_role;

-- Seeds: well-known recurring programmes (official pages only). Deadlines are unknown on purpose: the agent reads each page
-- and fills the current deadline; until then the site shows "تحقق من الموقع".
INSERT INTO public.opportunities (title, organizer, kind, field, scope, url, description, source) VALUES
 ('World Press Photo Contest', 'World Press Photo Foundation', 'competition', 'photo', 'international', 'https://www.worldpressphoto.org/contest', 'Annual photojournalism and documentary photography contest, open to professional photographers worldwide.', 'seed'),
 ('Sony World Photography Awards', 'World Photography Organisation', 'competition', 'photo', 'international', 'https://www.worldphoto.org/sony-world-photography-awards', 'Annual global photography awards with Professional, Open, Youth and Student competitions.', 'seed'),
 ('Pictures of the Year International', 'POYi', 'competition', 'photo', 'international', 'https://www.poy.org', 'Long-running photojournalism competition.', 'seed'),
 ('Siena International Photo Awards', 'Siena Awards', 'competition', 'photo', 'international', 'https://www.sienawards.com', 'International photo awards with a festival in Siena.', 'seed'),
 ('International Photography Awards (IPA)', 'Lucie Foundation', 'competition', 'photo', 'international', 'https://www.photoawards.com', 'Annual awards for professional, non-professional and student photographers.', 'seed'),
 ('Magnum Foundation grants and fellowships', 'Magnum Foundation', 'grant', 'photo', 'international', 'https://www.magnumfoundation.org', 'Funding and fellowships for documentary photographers and storytellers.', 'seed'),
 ('Camerimage (cinematography festival)', 'Camerimage', 'festival', 'film', 'international', 'https://camerimage.pl', 'The festival of the art of cinematography: competitions for feature, documentary and short cinematography.', 'seed'),
 ('Clermont-Ferrand International Short Film Festival', 'Sauve qui peut le court metrage', 'festival', 'film', 'international', 'https://clermont-filmfest.org', 'The largest short film festival; open call for submissions each year.', 'seed'),
 ('Sundance Film Festival submissions', 'Sundance Institute', 'festival', 'film', 'international', 'https://www.sundance.org/festivals', 'Submissions for shorts, documentary and features.', 'seed'),
 ('Hot Docs Canadian International Documentary Festival', 'Hot Docs', 'festival', 'film', 'international', 'https://hotdocs.ca', 'Documentary festival with an open call for films and a forum.', 'seed'),
 ('IDFA (International Documentary Film Festival Amsterdam)', 'IDFA', 'festival', 'film', 'international', 'https://www.idfa.nl', 'Documentary festival with competitions and the IDFA Bertha Fund.', 'seed'),
 ('Locarno Film Festival submissions', 'Locarno Film Festival', 'festival', 'film', 'international', 'https://www.locarnofestival.ch', 'Festival with short film and feature competitions.', 'seed'),
 ('Hubert Bals Fund', 'IFFR', 'grant', 'film', 'international', 'https://iffr.com/en/iffr-pro/hubert-bals-fund', 'Development, production and post-production support for filmmakers from the Global South, including the Arab region.', 'seed'),
 ('Berlinale Talents', 'Berlinale', 'fellowship', 'film', 'international', 'https://www.berlinale-talents.de', 'Talent programme for emerging film professionals.', 'seed'),
 ('Cannes Lions (advertising and brand film awards)', 'Cannes Lions', 'competition', 'film', 'international', 'https://www.canneslions.com', 'Awards for advertising, brand film and creative work.', 'seed'),
 ('Red Sea Fund and Souk (Red Sea International Film Festival)', 'Red Sea Film Foundation', 'grant', 'film', 'regional', 'https://redseafilm.foundation', 'Grants and the Souk programme for Arab and African filmmakers.', 'seed'),
 ('Doha Film Institute grants', 'Doha Film Institute', 'grant', 'film', 'regional', 'https://www.dohafilminstitute.com/financing', 'Grant programme for Arab and international filmmakers; rounds with set deadlines.', 'seed'),
 ('AFAC grants (Arab Fund for Arts and Culture)', 'AFAC', 'grant', 'both', 'regional', 'https://www.arabculturefund.org', 'Grants for Arab artists and filmmakers: documentary, short film, photography and more.', 'seed'),
 ('Royal Film Commission Jordan', 'Royal Film Commission', 'open_call', 'film', 'local', 'https://film.jo', 'Jordan''s national film body: funds, training, festivals and calls for Jordanian filmmakers.', 'seed'),
 ('El Gouna Film Festival (CineGouna)', 'El Gouna Film Festival', 'festival', 'film', 'regional', 'https://elgounafilmfestival.com', 'Festival and CineGouna platform for Arab film projects.', 'seed')
ON CONFLICT (url) DO NOTHING;
