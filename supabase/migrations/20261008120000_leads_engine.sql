-- Unified leads (NGOs, organisations, restaurants, brands, hotels, events…) + conversations + team settings.

CREATE TABLE public.leads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL DEFAULT 'restaurant',          -- ngo | org | restaurant | brand | hotel | event | other
  name text NOT NULL,
  category text, city text, address text,
  phone text, email text, website text,
  instagram text, facebook text, linkedin text, youtube text, tiktok text,
  rating numeric, maps_url text,
  about text,                                         -- raw text read from their website
  profile jsonb,                                      -- AI profile: who they are, what they care about, what to pitch
  score int,
  status text NOT NULL DEFAULT 'new',                 -- new | contacted | replied | meeting | won | lost | skip
  followups int NOT NULL DEFAULT 0,
  next_action_at date,
  needs_reply boolean NOT NULL DEFAULT false,
  notes text, source text,
  phone_key text UNIQUE, domain text UNIQUE, name_key text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz
);
CREATE INDEX leads_kind_status_idx ON public.leads(kind, status);
CREATE INDEX leads_score_idx ON public.leads(score DESC NULLS LAST);

-- Dedupe keys are computed by the DB so every insert path (app, import, harvester) dedupes the same way.
CREATE OR REPLACE FUNCTION public.leads_keys_of(t public.leads)
RETURNS TABLE(phone_key text, domain text, name_key text) LANGUAGE plpgsql IMMUTABLE SET search_path = public AS $$
DECLARE d text;
BEGIN
  d := regexp_replace(coalesce(t.phone, ''), '\D', '', 'g');
  phone_key := CASE WHEN length(d) >= 8 THEN right(d, 9) END;
  d := lower(substring(coalesce(t.website, '') from '^(?:https?://)?(?:www\.)?([^/:?#]+)'));
  domain := CASE WHEN d IS NULL OR d = '' OR d ~ '(facebook|instagram|linktr|wa\.me|whatsapp|google|business\.site|talabat|careem|tiktok|twitter|x\.com|youtube|linkedin|wixsite|blogspot)'
                 THEN NULL ELSE d END;
  name_key := lower(regexp_replace(t.name, '[^[:alnum:]]+', '', 'g')) || '|' || lower(coalesce(trim(t.city), ''));
  RETURN NEXT;
END $$;
CREATE OR REPLACE FUNCTION public.leads_keys() RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
  SELECT k.phone_key, k.domain, k.name_key INTO NEW.phone_key, NEW.domain, NEW.name_key FROM public.leads_keys_of(NEW) k;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER leads_keys BEFORE INSERT OR UPDATE ON public.leads FOR EACH ROW EXECUTE FUNCTION public.leads_keys();

CREATE TABLE public.lead_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
  channel text NOT NULL,             -- email | whatsapp | instagram | call
  direction text NOT NULL,           -- out | in
  subject text, body text NOT NULL,
  draft boolean NOT NULL DEFAULT false,
  created_by uuid DEFAULT auth.uid(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX lead_messages_lead_idx ON public.lead_messages(lead_id, created_at);

CREATE TABLE public.app_settings (
  id int PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  data jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.app_settings(id) VALUES (1) ON CONFLICT DO NOTHING;

-- Team access: any signed-in member (admin or user role).
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Members all leads" ON public.leads FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'))
  WITH CHECK (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'));
CREATE POLICY "Members all lead_messages" ON public.lead_messages FOR ALL TO authenticated
  USING (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'))
  WITH CHECK (public.has_role(auth.uid(), 'admin') OR public.has_role(auth.uid(), 'user'));
CREATE POLICY "Members read settings" ON public.app_settings FOR SELECT TO authenticated USING (true);
CREATE POLICY "Admins write settings" ON public.app_settings FOR UPDATE TO authenticated USING (public.has_role(auth.uid(), 'admin'));
GRANT ALL ON public.leads, public.lead_messages, public.app_settings TO authenticated, service_role;

-- Bulk import with dedupe: new rows are inserted, duplicates only fill the empty fields.
CREATE OR REPLACE FUNCTION public.ingest_leads(rows jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path = public AS $$
DECLARE r jsonb; t public.leads; hit uuid; n int; ins int := 0; mer int := 0;
BEGIN
  FOR r IN SELECT * FROM jsonb_array_elements(rows) LOOP
    IF coalesce(r->>'name', '') = '' THEN CONTINUE; END IF;
    t := jsonb_populate_record(NULL::public.leads, r);
    -- compute keys the same way the trigger does
    SELECT k.phone_key, k.domain, k.name_key INTO t.phone_key, t.domain, t.name_key FROM public.leads_keys_of(t) k;
    SELECT id INTO hit FROM public.leads
      WHERE (t.phone_key IS NOT NULL AND phone_key = t.phone_key)
         OR (t.domain IS NOT NULL AND domain = t.domain)
         OR name_key = t.name_key LIMIT 1;
    IF hit IS NULL THEN
      INSERT INTO public.leads(kind, name, category, city, address, phone, email, website, instagram, facebook, linkedin,
                               youtube, tiktok, rating, maps_url, about, source)
      VALUES (coalesce(t.kind, 'other'), t.name, t.category, t.city, t.address, t.phone, t.email, t.website, t.instagram,
              t.facebook, t.linkedin, t.youtube, t.tiktok, t.rating, t.maps_url, t.about, t.source)
      ON CONFLICT DO NOTHING;
      GET DIAGNOSTICS n = ROW_COUNT;
      ins := ins + n;
    ELSE
      UPDATE public.leads SET
        email = coalesce(email, t.email), website = coalesce(website, t.website), phone = coalesce(phone, t.phone),
        instagram = coalesce(instagram, t.instagram), facebook = coalesce(facebook, t.facebook),
        linkedin = coalesce(linkedin, t.linkedin), youtube = coalesce(youtube, t.youtube), tiktok = coalesce(tiktok, t.tiktok),
        rating = coalesce(rating, t.rating), maps_url = coalesce(maps_url, t.maps_url), about = coalesce(about, t.about),
        category = coalesce(category, t.category), address = coalesce(address, t.address)
      WHERE id = hit;
      mer := mer + 1;
    END IF;
  END LOOP;
  RETURN jsonb_build_object('inserted', ins, 'merged', mer);
END $$;

GRANT EXECUTE ON FUNCTION public.ingest_leads(jsonb) TO authenticated;

-- Carry over the old restaurants (deduped) so nothing is lost.
INSERT INTO public.leads(kind, name, phone, email, website, address, city, source)
SELECT 'restaurant', title, phone, email, website, address, city, 'old-list'
FROM public.restaurants WHERE deleted_at IS NULL
ON CONFLICT DO NOTHING;
