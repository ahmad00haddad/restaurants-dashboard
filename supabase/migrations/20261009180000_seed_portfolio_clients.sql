-- Seed team settings with Ahmad's real portfolio (42 works) and past clients (from ahmadhaddad.lovable.app).
-- Only fills fields that are still empty, so nothing typed in Settings is overwritten.
UPDATE public.app_settings SET data = data
  || CASE WHEN coalesce(data->>'portfolio', '') = '' THEN jsonb_build_object('portfolio', $faii$Arafah | https://www.behance.net/gallery/233502359/Arafa | ad, restaurant, food, brand
Duroub With Alma | https://www.behance.net/gallery/242646259/Duroub-With-Alma | school, education, brand film
One Thousand and One Secrets | https://www.behance.net/gallery/243985595/_ | ad, brand, commercial
sadwon pharmacy | https://www.behance.net/gallery/214879873/_ | ad, pharmacy, health, brand
Do you remember me? | https://www.behance.net/gallery/225987725/_ | short film, people story, elderly, documentary style
loccitane | https://www.behance.net/gallery/239420949/loccitane | ad, cosmetics, international brand, product
International Workers' Day - Astrolabe | https://youtu.be/fhkoZXOlETQ?si=SdLzPUAH-PZpgfPB | ad, cafe, social content, campaign
amal - Dead Sea Pandemic | https://www.behance.net/gallery/118091347/Amal-short-film | short film, tourism, pandemic, documentary style
City Voice | https://www.behance.net/gallery/97215567/_ | short film, city, community
صانع الأمل | https://www.behance.net/gallery/98788367/_ | short film, inspiration, people story
QRTA | https://www.behance.net/gallery/226584981/QRTA | documentary, education, teachers, foundation, ngo
al salwa books | https://www.behance.net/gallery/252096055/_ | ad, children, books, charity, social cause
KhanZaid | https://www.behance.net/gallery/215468403/KhanZaid- | ad, restaurant, food, heritage
بني كنانة جديلة حوران | https://www.behance.net/gallery/179156911/_ | documentary, heritage, culture, community, irbid
Erasmus event | https://www.behance.net/gallery/256801237/Erasmus-event | event film, eu programme, youth, education, ngo
EARLY | https://www.behance.net/gallery/201461427/_ | short film
تبدو غريبا | https://www.behance.net/gallery/133992723/_ | short film
not me | https://www.behance.net/gallery/109517925/_ | short film, social awareness
Douira | https://www.behance.net/gallery/107906989/_ | short film, culture
شعائر مقاومة | https://www.behance.net/gallery/173894345/_ | documentary, culture, heritage
Duroub School | https://www.behance.net/gallery/237148893/Duroub-School | school, education, institutional film
khanzaid - Ramadan 2025 | https://www.behance.net/gallery/220753233/khanzaid-Ramadan-2025 | ad, restaurant, food, ramadan campaign
WeFlowers | https://www.behance.net/gallery/172873553/WeFlowers-Women-Perfume | ad, perfume, women, product
متحف دار السرايا | https://www.behance.net/gallery/133944345/_ | documentary, museum, heritage, culture
error 017 | https://www.behance.net/gallery/94344913/Error-017-Short-Film | short film, fiction
Sillin | https://www.behance.net/gallery/84553343/Sillin- | short film, fiction
Em Sherif Café | https://www.behance.net/gallery/206884241/Em-Sherif-Cafe-Amman | ad, cafe, restaurant, hospitality, food
Minecraft Education Documentary | https://www.behance.net/gallery/256292055/Minecraft-Education-Documentary | documentary, education, technology
Ehsan Haddad Documentary | https://www.behance.net/gallery/251521863/Ehsan-Haddad-Documentary | documentary, portrait, people story
Mother's Day - Tabarak Al-Rahman | https://www.behance.net/gallery/193736153/Mothers-Day-Tabarak-Al-Rahman-Jewellery | ad, jewellery, retail, campaign
Astrolabe Matcha Campaign | https://www.behance.net/gallery/254729309/Astrolabe-Matcha-Campaign | ad, cafe, drinks, campaign
prisoner | https://www.behance.net/gallery/190660973/_ | short film, human rights, social cause
رحلة صورة | https://www.behance.net/gallery/173895049/_ | short film, photography
rajaa | https://www.behance.net/gallery/206048153/Rajaa-USAID | documentary, ngo, usaid, women, community impact
Ezwitti | https://www.behance.net/gallery/131010035/-Ezwitti | documentary, ngo, youth, community, social cause
they are there for each other | https://www.behance.net/gallery/126287243/_ | documentary, women, ngo, solidarity, social cause
A million small things | https://www.behance.net/gallery/105726903/_ | short film, social cause
road safety | https://www.behance.net/gallery/143277499/road-safety | awareness film, ngo, youth, road safety, campaign
1st-Film | https://www.behance.net/gallery/135123435/1st-Film | short film
I am Omar | https://www.behance.net/gallery/189485833/_ | short film, children, people story
نمر نفاع | https://www.behance.net/gallery/220846511/_ | ad, cars, retail, brand
Simma | https://www.behance.net/gallery/158224307/Simma-mobile-app | ad, mobile app, tech, product$faii$::text) ELSE '{}'::jsonb END
  || CASE WHEN coalesce(data->>'pastClients', '') = '' THEN jsonb_build_object('pastClients', $faii$USAID | international donor agency (US government), community & women programmes | en
Mercy Corps | international NGO, humanitarian & development | en
UNICEF | UN agency, children & youth | en
UN Women | UN agency, women's empowerment | en
Erasmus+ | EU education & youth programme | en
Global Youth Coalition for Road Safety | international youth NGO, road safety awareness | en
Community Jameel | international philanthropic organisation | en
Queen Rania Teacher Academy (QRTA) | Jordanian royal foundation, education & teachers | ar
قلبي اطمأن | humanitarian charity initiative | ar
الأقل حظاً | charity / social initiative | ar
عزوتي | community & youth initiative | ar
هن لهن | women's solidarity initiative | ar
نفرح بالحسين | community celebration / national initiative | ar
اليوبيل الفضي | institutional anniversary (25 years) | ar
بداية | social initiative | ar
ناس إربد | community storytelling, Irbid | ar
دار السلوى | children's book publisher | ar
مدرسة دروب | private school, education | ar
Leading Point | software company | en
Imdad | logistics & site services company | en
EON Dental | healthcare company | en
Kitco Arabia | food manufacturer (regional) | en
Maqsam | tech / telecom company | en
L'Occitane | international cosmetics brand | en
Em Sherif Café | upscale restaurant & café | ar
خان زيد | restaurant, Irbid | ar
عرفة | restaurant, Irbid | ar
إسطرلاب | specialty coffee roastery & café | ar
بن معروف | coffee shop | ar
كانيلا | café | ar
كريبيلو | café & desserts | ar
مكي ديلايتس | coffee roastery | ar
ذا بيكر | restaurant / bakery | ar
ذهب | restaurant & café | ar
جوهرة الشرق | sweets & desserts | ar
سلة الصياد | seafood restaurant | ar
محمص القدس | coffee roastery & nuts | ar
فوكس | restaurant / mall | ar
أزرار | café | ar
سر الدواء | pharmacy chain | ar
صيدلية صدوان | pharmacy | ar
تبارك الرحمن | jewellery store | ar
أطياب العبادلة | perfumes | ar
We Flowers | women's perfume brand | ar
Skina | skincare / cosmetics | ar
Cosmoland | cosmetics store | ar
Beauty Lounge | beauty salon | ar
كريم هايبرماركت | hypermarket | ar
نمر نفاع | retail & warehouses | ar
ليث العبيدي للسيارات | car dealership | ar
شرقي | computer store | ar
مينا | mobile phone store | ar
براند ون | men's clothing | ar
سما | agricultural & dairy company | ar
Simma | mobile app | ar
Hydrogen | gym & spa | ar
كليكس | travel & visa services | ar
Venovo | interior design & furniture | ar
البيطار | hotel & restaurant supplies | ar
قاعات الشرق | wedding & event halls | ar
Graphite Studio | creative studio | en
Jordan Craft Center | handicrafts | en$faii$::text) ELSE '{}'::jsonb END
  || CASE WHEN coalesce(data->>'portfolioSite', '') = '' THEN jsonb_build_object('portfolioSite', 'https://www.behance.net/ahmad00haddad') ELSE '{}'::jsonb END,
  updated_at = now()
WHERE id = 1;
