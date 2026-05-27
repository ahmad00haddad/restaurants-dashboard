import { useEffect, useState, useCallback, useMemo } from "react";
import type { Status } from "@/lib/restaurants";

const KEY = "faii.crm.v2";
const LEGACY_KEY = "faii.status.v1";

export interface RestaurantState {
  status?: Status;
  favorite?: boolean;
  notes?: string;
  followUp?: string; // ISO date YYYY-MM-DD
  tags?: string[];
  updatedAt?: number;
  history?: { at: number; status: Status }[];
}

type Store = Record<string, RestaurantState>;

function readStore(): Store {
  if (typeof window === "undefined") return {};
  try {
    const v2 = localStorage.getItem(KEY);
    if (v2) return JSON.parse(v2);
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy) {
      const m: Record<string, Status> = JSON.parse(legacy);
      const out: Store = {};
      for (const [id, status] of Object.entries(m)) {
        out[id] = { status, updatedAt: Date.now() };
      }
      localStorage.setItem(KEY, JSON.stringify(out));
      return out;
    }
  } catch {}
  return {};
}

export function useCrmStore() {
  const [store, setStore] = useState<Store>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setStore(readStore());
    setReady(true);
  }, []);

  const persist = useCallback((next: Store) => {
    try { localStorage.setItem(KEY, JSON.stringify(next)); } catch {}
  }, []);

  const update = useCallback((id: string, patch: Partial<RestaurantState>) => {
    setStore((prev) => {
      const cur = prev[id] ?? {};
      const next = { ...prev, [id]: { ...cur, ...patch, updatedAt: Date.now() } };
      persist(next);
      return next;
    });
  }, [persist]);

  const setStatus = useCallback((id: string, status: Status) => {
    setStore((prev) => {
      const cur = prev[id] ?? {};
      const history = [...(cur.history ?? []), { at: Date.now(), status }];
      const next = { ...prev, [id]: { ...cur, status, history, updatedAt: Date.now() } };
      persist(next);
      return next;
    });
  }, [persist]);

  const setStatusBulk = useCallback((ids: string[], status: Status) => {
    setStore((prev) => {
      const next = { ...prev };
      const now = Date.now();
      for (const id of ids) {
        const cur = next[id] ?? {};
        next[id] = { ...cur, status, updatedAt: now, history: [...(cur.history ?? []), { at: now, status }] };
      }
      persist(next);
      return next;
    });
  }, [persist]);

  const toggleFavorite = useCallback((id: string) => {
    setStore((prev) => {
      const cur = prev[id] ?? {};
      const next = { ...prev, [id]: { ...cur, favorite: !cur.favorite, updatedAt: Date.now() } };
      persist(next);
      return next;
    });
  }, [persist]);

  const addTag = useCallback((id: string, tag: string) => {
    const t = tag.trim();
    if (!t) return;
    setStore((prev) => {
      const cur = prev[id] ?? {};
      const tags = Array.from(new Set([...(cur.tags ?? []), t]));
      const next = { ...prev, [id]: { ...cur, tags, updatedAt: Date.now() } };
      persist(next);
      return next;
    });
  }, [persist]);

  const removeTag = useCallback((id: string, tag: string) => {
    setStore((prev) => {
      const cur = prev[id] ?? {};
      const tags = (cur.tags ?? []).filter((x) => x !== tag);
      const next = { ...prev, [id]: { ...cur, tags, updatedAt: Date.now() } };
      persist(next);
      return next;
    });
  }, [persist]);

  const importStore = useCallback((data: Store) => {
    setStore(data);
    persist(data);
  }, [persist]);

  const exportStore = useCallback(() => store, [store]);

  const clearAll = useCallback(() => {
    setStore({});
    persist({});
  }, [persist]);

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

  // All distinct tags across the store
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
