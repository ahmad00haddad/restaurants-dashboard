import { useCallback, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import type { Status } from "@/lib/restaurants";

export interface RestaurantState {
  status?: Status;
  favorite?: boolean;
  notes?: string;
  followUp?: string; // YYYY-MM-DD
  tags?: string[];
  dealValue?: number;
  updatedAt?: number;
  history?: { at: number; status: Status }[];
}

interface DbRow {
  restaurant_id: string;
  status: Status;
  favorite: boolean;
  notes: string | null;
  follow_up: string | null;
  tags: string[];
  deal_value: number | null;
  history: unknown;
  updated_at: string;
}

type Store = Record<string, RestaurantState>;

const QK = ["crm-states"] as const;

function rowToState(row: DbRow): RestaurantState {
  return {
    status: row.status,
    favorite: row.favorite,
    notes: row.notes ?? undefined,
    followUp: row.follow_up ?? undefined,
    tags: row.tags ?? [],
    dealValue: row.deal_value ?? undefined,
    history: Array.isArray(row.history) ? (row.history as { at: number; status: Status }[]) : [],
    updatedAt: new Date(row.updated_at).getTime(),
  };
}

async function fetchAll(userId: string): Promise<Store> {
  const { data, error } = await supabase
    .from("crm_states")
    .select("restaurant_id, status, favorite, notes, follow_up, tags, deal_value, history, updated_at")
    .eq("user_id", userId);
  if (error) throw error;
  const out: Store = {};
  for (const r of (data ?? []) as DbRow[]) out[r.restaurant_id] = rowToState(r);
  return out;
}

async function upsertOne(
  userId: string,
  restaurantId: string,
  cur: RestaurantState,
  patch: Partial<RestaurantState> & { historyAppend?: { at: number; status: Status } },
) {
  const baseHistory = cur.history ?? [];
  const history = patch.historyAppend ? [...baseHistory, patch.historyAppend] : (patch.history ?? baseHistory);

  const payload = {
    user_id: userId,
    restaurant_id: restaurantId,
    status: patch.status ?? cur.status ?? "new",
    favorite: patch.favorite ?? cur.favorite ?? false,
    notes: patch.notes ?? cur.notes ?? null,
    follow_up: patch.followUp ?? cur.followUp ?? null,
    tags: patch.tags ?? cur.tags ?? [],
    deal_value: patch.dealValue ?? cur.dealValue ?? null,
    history,
  };
  const { error } = await supabase
    .from("crm_states")
    .upsert(payload, { onConflict: "user_id,restaurant_id" });
  if (error) throw error;
}

export function useCrmStore() {
  const qc = useQueryClient();
  const userIdQuery = useQuery({
    queryKey: ["auth-user-id"],
    queryFn: async () => {
      const { data } = await supabase.auth.getUser();
      return data.user?.id ?? null;
    },
    staleTime: 5 * 60_000,
  });
  const userId = userIdQuery.data ?? null;

  const { data: store = {} } = useQuery({
    queryKey: QK,
    queryFn: () => fetchAll(userId!),
    enabled: !!userId,
    staleTime: 30_000,
  });

  // Realtime: refresh crm state on any change for this user
  useEffect(() => {
    if (!userId) return;
    const ch = supabase
      .channel(`crm-${userId}`)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "crm_states", filter: `user_id=eq.${userId}` },
        () => qc.invalidateQueries({ queryKey: QK }),
      )
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, [userId, qc]);

  const ready = !userIdQuery.isLoading && (!userId || !!store);

  const persist = useCallback(
    async (id: string, patch: Partial<RestaurantState> & { historyAppend?: { at: number; status: Status } }) => {
      if (!userId) return;
      // Merge from live cache (avoids race with a stale separate SELECT).
      const prev = qc.getQueryData<Store>(QK) ?? {};
      const cur = prev[id] ?? {};
      const nextHistory = patch.historyAppend
        ? [...(cur.history ?? []), patch.historyAppend]
        : (patch.history ?? cur.history);
      const merged: RestaurantState = { ...cur, ...patch, history: nextHistory, updatedAt: Date.now() };
      qc.setQueryData<Store>(QK, { ...prev, [id]: merged });
      try {
        await upsertOne(userId, id, cur, patch);
      } catch (e) {
        // Rollback on failure
        qc.setQueryData<Store>(QK, prev);
        throw e;
      }
    },
    [userId, qc],
  );

  const setStatus = useCallback((id: string, status: Status) => {
    persist(id, { status, historyAppend: { at: Date.now(), status } });
  }, [persist]);

  const setStatusBulk = useCallback(async (ids: string[], status: Status) => {
    for (const id of ids) await persist(id, { status, historyAppend: { at: Date.now(), status } });
  }, [persist]);

  const update = useCallback((id: string, patch: Partial<RestaurantState>) => {
    persist(id, patch);
  }, [persist]);

  const toggleFavorite = useCallback((id: string) => {
    const cur = store[id]?.favorite ?? false;
    persist(id, { favorite: !cur });
  }, [persist, store]);

  const addTag = useCallback((id: string, tag: string) => {
    const t = tag.trim();
    if (!t) return;
    const tags = Array.from(new Set([...(store[id]?.tags ?? []), t]));
    persist(id, { tags });
  }, [persist, store]);

  const removeTag = useCallback((id: string, tag: string) => {
    const tags = (store[id]?.tags ?? []).filter((x) => x !== tag);
    persist(id, { tags });
  }, [persist, store]);

  const importStore = useCallback(async (data: Store) => {
    if (!userId) return;
    for (const [id, s] of Object.entries(data)) {
      await upsertOne(userId, id, s);
    }
    qc.invalidateQueries({ queryKey: QK });
  }, [userId, qc]);

  const exportStore = useCallback(() => store, [store]);

  const clearAll = useCallback(async () => {
    if (!userId) return;
    const { error } = await supabase.from("crm_states").delete().eq("user_id", userId);
    if (error) throw error;
    qc.invalidateQueries({ queryKey: QK });
  }, [userId, qc]);

  const getState = useCallback((id: string): RestaurantState => store[id] ?? {}, [store]);
  const getStatus = useCallback((id: string): Status => (store[id]?.status ?? "new") as Status, [store]);

  const todayCount = useMemo(() => {
    const start = new Date(); start.setHours(0, 0, 0, 0);
    const t = start.getTime();
    let n = 0;
    for (const s of Object.values(store)) {
      for (const h of s.history ?? []) if (h.at >= t && h.status !== "new") n++;
    }
    return n;
  }, [store]);

  const allTags = useMemo(() => {
    const map = new Map<string, number>();
    for (const s of Object.values(store)) {
      for (const t of s.tags ?? []) map.set(t, (map.get(t) ?? 0) + 1);
    }
    return [...map.entries()].map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count);
  }, [store]);

  return {
    store, ready, getState, getStatus, setStatus, setStatusBulk,
    update, toggleFavorite, todayCount, addTag, removeTag,
    importStore, exportStore, clearAll, allTags,
  };
}
