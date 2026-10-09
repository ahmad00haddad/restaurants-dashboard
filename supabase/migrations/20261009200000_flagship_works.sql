-- Ahmad's flagship works (chosen by him): the AI always prefers these. Idempotent: lines already starred are untouched.
UPDATE public.app_settings
SET data = jsonb_set(data, '{portfolio}', to_jsonb(regexp_replace(
      coalesce(data->>'portfolio', ''),
      '^(rajaa|Ezwitti|QRTA|Minecraft Education Documentary|they are there for each other|Em Sherif Café|loccitane|Astrolabe Matcha Campaign|KhanZaid) \|',
      '★ \1 |', 'gn'))),
    updated_at = now()
WHERE id = 1;
