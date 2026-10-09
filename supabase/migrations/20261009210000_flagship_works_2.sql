-- More flagship works + usage limits chosen by Ahmad. Idempotent.
UPDATE public.app_settings
SET data = jsonb_set(data, '{portfolio}', to_jsonb(
      regexp_replace(regexp_replace(regexp_replace(regexp_replace(
        coalesce(data->>'portfolio', ''),
        '^(1st-Film|Arafah) \|', '★ \1 |', 'gn'),
        '^رحلة صورة \| ([^ |]+) \|[^\n]*$', '★ رحلة صورة | \1 | documentary, photography, people story', 'gn'),
        '^(Duroub School \| (?:(?!ONLY)[^\n])*)$', '\1, ONLY for schools', 'gn'),
        '^(khanzaid - Ramadan 2025 \| (?:(?!ONLY)[^\n])*)$', '\1, ONLY around Ramadan or for Ramadan campaigns', 'gn'))),
    updated_at = now()
WHERE id = 1;
