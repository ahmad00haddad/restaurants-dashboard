-- Buying signals (tenders / comms hiring / events) + deal value.
ALTER TABLE public.leads
  ADD COLUMN IF NOT EXISTS signal text,          -- e.g. "Hiring: Communications Officer" / "RFQ: video production"
  ADD COLUMN IF NOT EXISTS signal_url text,
  ADD COLUMN IF NOT EXISTS signal_until date,    -- closing date of the opportunity
  ADD COLUMN IF NOT EXISTS deal_value numeric;
CREATE INDEX IF NOT EXISTS leads_signal_idx ON public.leads(signal_until) WHERE signal IS NOT NULL;

CREATE OR REPLACE FUNCTION public.ingest_leads(rows jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path = public AS $$
DECLARE r jsonb; t public.leads; hit uuid; n int; ins int := 0; mer int := 0;
BEGIN
  FOR r IN SELECT * FROM jsonb_array_elements(rows) LOOP
    IF coalesce(r->>'name', '') = '' THEN CONTINUE; END IF;
    t := jsonb_populate_record(NULL::public.leads, r);
    SELECT k.phone_key, k.domain, k.name_key INTO t.phone_key, t.domain, t.name_key FROM public.leads_keys_of(t) k;
    SELECT id INTO hit FROM public.leads
      WHERE (t.phone_key IS NOT NULL AND phone_key = t.phone_key)
         OR (t.domain IS NOT NULL AND domain = t.domain)
         OR name_key = t.name_key
         -- signals come without a city: match the organisation by name alone
         OR (t.signal IS NOT NULL AND split_part(name_key, '|', 1) = split_part(t.name_key, '|', 1))
      LIMIT 1;
    IF hit IS NULL THEN
      INSERT INTO public.leads(kind, name, category, city, address, phone, email, website, instagram, facebook, linkedin,
                               youtube, tiktok, rating, maps_url, about, source, signal, signal_url, signal_until)
      VALUES (coalesce(t.kind, 'other'), t.name, t.category, t.city, t.address, t.phone, t.email, t.website, t.instagram,
              t.facebook, t.linkedin, t.youtube, t.tiktok, t.rating, t.maps_url, t.about, t.source,
              t.signal, t.signal_url, t.signal_until)
      ON CONFLICT DO NOTHING;
      GET DIAGNOSTICS n = ROW_COUNT;
      ins := ins + n;
    ELSE
      UPDATE public.leads SET
        email = coalesce(email, t.email), website = coalesce(website, t.website), phone = coalesce(phone, t.phone),
        instagram = coalesce(instagram, t.instagram), facebook = coalesce(facebook, t.facebook),
        linkedin = coalesce(linkedin, t.linkedin), youtube = coalesce(youtube, t.youtube), tiktok = coalesce(tiktok, t.tiktok),
        rating = coalesce(rating, t.rating), maps_url = coalesce(maps_url, t.maps_url), about = coalesce(about, t.about),
        category = coalesce(category, t.category), address = coalesce(address, t.address),
        -- a fresh signal replaces an old one
        signal = coalesce(t.signal, signal), signal_url = coalesce(t.signal_url, signal_url),
        signal_until = coalesce(t.signal_until, signal_until)
      WHERE id = hit;
      mer := mer + 1;
    END IF;
  END LOOP;
  RETURN jsonb_build_object('inserted', ins, 'merged', mer);
END $$;
