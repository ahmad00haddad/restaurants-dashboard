-- Ahmad is a Director & Cinematographer (not a photographer).
UPDATE public.app_settings
SET data = data
  || jsonb_build_object('senderRole', 'Director & Cinematographer')
  || jsonb_build_object('whoWeAre', replace(replace(replace(coalesce(data->>'whoWeAre', ''), 'مصور ومخرج', 'مخرج ومدير تصوير'), 'مخرج ومصوّر', 'مخرج ومدير تصوير'), 'مصوّر ومخرج', 'مخرج ومدير تصوير')),
  updated_at = now()
WHERE id = 1;
