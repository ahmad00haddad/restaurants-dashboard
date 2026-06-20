import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import seedJson from "@/data/restaurants.json";
import {
  detectCategory,
  detectSegment,
  ratingFromRank,
  type RawRestaurant,
  type Restaurant,
} from "@/lib/restaurants";
import { getGlobalQueryClient } from "@/lib/query-client";

const QK = ["restaurants"] as const;

interface DbRow {
  id: string;
  external_id: string | null;
  title: string;
  phone: string | null;
  website: string | null;
  address: string | null;
  street: string | null;
  city: string | null;
  rank: number;
}

function rowToRestaurant(row: DbRow): Restaurant {
  const base: RawRestaurant = {
    title: row.title,
    phone: row.phone,
    website: row.website ?? undefined,
    address: row.address,
    street: row.street,
    city: row.city,
    rank: row.rank,
  };
  return {
    ...base,
    id: row.id,
    segment: detectSegment(base),
    category: detectCategory(row.title),
    rating: ratingFromRank(row.rank),
  };
}

async function fetchAll(): Promise<Restaurant[]> {
  // Need all rows; default Supabase limit is 1000. Use range to ensure full set.
  const out: Restaurant[] = [];
  const STEP = 1000;
  for (let from = 0; ; from += STEP) {
    const { data, error } = await supabase
      .from("restaurants")
      .select("id, external_id, title, phone, website, address, street, city, rank")
      .order("rank", { ascending: true })
      .range(from, from + STEP - 1);
    if (error) throw error;
    if (!data || data.length === 0) break;
    out.push(...(data as DbRow[]).map(rowToRestaurant));
    if (data.length < STEP) break;
  }
  return out;
}

export function useRestaurants(): Restaurant[] {
  const { data } = useQuery({
    queryKey: QK,
    queryFn: fetchAll,
    staleTime: 60_000,
  });
  return data ?? [];
}

export function useRestaurantsQuery() {
  return useQuery({ queryKey: QK, queryFn: fetchAll, staleTime: 60_000 });
}

function invalidate() {
  getGlobalQueryClient()?.invalidateQueries({ queryKey: QK });
}

export async function deleteRestaurants(ids: string[]) {
  if (ids.length === 0) return;
  const { error } = await supabase.from("restaurants").delete().in("id", ids);
  if (error) throw error;
  invalidate();
}

export async function updateRestaurant(id: string, patch: Partial<RawRestaurant>) {
  const { error } = await supabase
    .from("restaurants")
    .update({
      title: patch.title,
      phone: patch.phone,
      website: patch.website ?? null,
      address: patch.address,
      street: patch.street,
      city: patch.city,
      rank: patch.rank,
    })
    .eq("id", id);
  if (error) throw error;
  invalidate();
}

export interface NewRestaurantInput {
  title: string;
  phone?: string | null;
  website?: string;
  address?: string | null;
  street?: string | null;
  city?: string | null;
  rank?: number;
}

export async function addRestaurant(input: NewRestaurantInput): Promise<string | null> {
  const { data: maxRow } = await supabase
    .from("restaurants")
    .select("rank")
    .order("rank", { ascending: false })
    .limit(1)
    .maybeSingle();
  const nextRank = input.rank && input.rank > 0 ? input.rank : (maxRow?.rank ?? 0) + 1;
  const { data, error } = await supabase
    .from("restaurants")
    .insert({
      title: input.title.trim(),
      phone: input.phone?.trim() || null,
      website: input.website?.trim() || null,
      address: input.address?.trim() || null,
      street: input.street?.trim() || null,
      city: input.city?.trim() || "إربد",
      rank: nextRank,
    })
    .select("id")
    .single();
  if (error) throw error;
  invalidate();
  return data?.id ?? null;
}

/**
 * Re-upserts all seed restaurants from the JSON file (idempotent — won't duplicate
 * existing seeded rows because of the external_id unique constraint).
 * Effectively brings back any seed entry someone deleted.
 */
export async function restoreAllRestaurants() {
  const seed = seedJson as RawRestaurant[];
  const BATCH = 200;
  for (let i = 0; i < seed.length; i += BATCH) {
    const slice = seed.slice(i, i + BATCH).map((r, j) => ({
      external_id: `seed-${r.rank}-${i + j}`,
      title: r.title,
      phone: r.phone,
      address: r.address,
      street: r.street,
      city: r.city,
      rank: r.rank,
    }));
    const { error } = await supabase
      .from("restaurants")
      .upsert(slice, { onConflict: "external_id", ignoreDuplicates: true });
    if (error) throw error;
  }
  invalidate();
}

export function restaurantStats() {
  const qc = getGlobalQueryClient();
  const list = (qc?.getQueryData(QK) as Restaurant[] | undefined) ?? [];
  return { total: list.length, deleted: 0, edited: 0, added: 0 };
}
