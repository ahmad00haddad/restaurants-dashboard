
-- Profiles table
CREATE TABLE public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  display_name TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON public.profiles TO authenticated;
GRANT ALL ON public.profiles TO service_role;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users view own profile" ON public.profiles FOR SELECT TO authenticated USING (auth.uid() = id);
CREATE POLICY "Users update own profile" ON public.profiles FOR UPDATE TO authenticated USING (auth.uid() = id);
CREATE POLICY "Users insert own profile" ON public.profiles FOR INSERT TO authenticated WITH CHECK (auth.uid() = id);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, display_name, avatar_url)
  VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)), NEW.raw_user_meta_data->>'avatar_url')
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END; $$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = public;
CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- Restaurants (shared global pool, per-user can manage rows they own + see all)
CREATE TABLE public.restaurants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  external_id TEXT UNIQUE,
  title TEXT NOT NULL,
  phone TEXT,
  website TEXT,
  address TEXT,
  street TEXT,
  city TEXT,
  rank INTEGER NOT NULL DEFAULT 9999,
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX restaurants_rank_idx ON public.restaurants(rank);
CREATE INDEX restaurants_title_idx ON public.restaurants USING gin (to_tsvector('simple', title));
GRANT SELECT, INSERT, UPDATE, DELETE ON public.restaurants TO authenticated;
GRANT ALL ON public.restaurants TO service_role;
ALTER TABLE public.restaurants ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated read restaurants" ON public.restaurants FOR SELECT TO authenticated USING (true);
CREATE POLICY "Authenticated insert restaurants" ON public.restaurants FOR INSERT TO authenticated WITH CHECK (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated update restaurants" ON public.restaurants FOR UPDATE TO authenticated USING (auth.uid() IS NOT NULL);
CREATE POLICY "Authenticated delete restaurants" ON public.restaurants FOR DELETE TO authenticated USING (auth.uid() IS NOT NULL);

-- Per-user CRM state for each restaurant
CREATE TYPE public.crm_status AS ENUM ('new', 'email', 'whatsapp', 'meeting');
CREATE TABLE public.crm_states (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  restaurant_id UUID NOT NULL REFERENCES public.restaurants(id) ON DELETE CASCADE,
  status public.crm_status NOT NULL DEFAULT 'new',
  favorite BOOLEAN NOT NULL DEFAULT false,
  notes TEXT,
  follow_up DATE,
  tags TEXT[] NOT NULL DEFAULT '{}',
  deal_value NUMERIC,
  history JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, restaurant_id)
);
CREATE INDEX crm_states_user_idx ON public.crm_states(user_id);
CREATE INDEX crm_states_user_status_idx ON public.crm_states(user_id, status);
GRANT SELECT, INSERT, UPDATE, DELETE ON public.crm_states TO authenticated;
GRANT ALL ON public.crm_states TO service_role;
ALTER TABLE public.crm_states ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users manage own crm" ON public.crm_states FOR ALL TO authenticated
  USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- updated_at trigger
CREATE OR REPLACE FUNCTION public.touch_updated_at() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql SET search_path = public;
CREATE TRIGGER trg_restaurants_updated BEFORE UPDATE ON public.restaurants FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
CREATE TRIGGER trg_crm_states_updated BEFORE UPDATE ON public.crm_states FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
CREATE TRIGGER trg_profiles_updated BEFORE UPDATE ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
