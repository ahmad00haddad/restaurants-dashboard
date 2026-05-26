import { useEffect, useState, useCallback, useMemo } from "react";
import type { Status } from "@/lib/restaurants";

const KEY = "faii.crm.v2";
const LEGACY_KEY = "faii.status.v1";

export interface RestaurantState {
  status?: Status;
  favorite?: boolean;
  notes?: string;
  followUp?: string; // ISO date YYYY-MM-DD
  updatedAt?: number;
  history?: { at: number; status: Status }[];
}

type Store = Record<string, RestaurantState>;

function readStore(): Store {
  if (typeof window === "undefined") return {};
  try {
    const v2 = localStorage.getItem(KEY);
    if (v2) return JSON.parse(v2);
    // Migrate legacy
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
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {}
  }, []);

  const update = useCallback(
    (id: string, patch: Partial<RestaurantState>) => {
      setStore((prev) => {
        const cur = prev[id] ?? {};
        const next = {
          ...prev,
          [id]: { ...cur, ...patch, updatedAt: Date.now() },
        };
        persist(next);
        return next;
      });
    },
    [persist],
  );

  const setStatus = useCallback(
    (id: string, status: Status) => {
      setStore((prev) => {
        const cur = prev[id] ?? {};
        const history = [...(cur.history ?? []), { at: Date.now(), status }];
        const next = {
          ...prev,
          [id]: { ...cur, status, history, updatedAt: Date.now() },
        };
        persist(next);
        return next;
      });
    },
    [persist],
  );

  const setStatusBulk = useCallback(
    (ids: string[], status: Status) => {
      setStore((prev) => {
        const next = { ...prev };
        const now = Date.now();
        for (const id of ids) {
          const cur = next[id] ?? {};
          next[id] = {
            ...cur,
            status,
            updatedAt: now,
            history: [...(cur.history ?? []), { at: now, status }],
          };
        }
        persist(next);
        return next;
      });
    },
    [persist],
  );

  const toggleFavorite = useCallback(
    (id: string) => {
      setStore((prev) => {
        const cur = prev[id] ?? {};
        const next = {
          ...prev,
          [id]: { ...cur, favorite: !cur.favorite, updatedAt: Date.now() },
        };
        persist(next);
        return next;
      });
    },
    [persist],
  );

  const getState = useCallback(
    (id: string): RestaurantState => store[id] ?? {},
    [store],
  );
  const getStatus = useCallback(
    (id: string): Status => (store[id]?.status ?? "new") as Status,
    [store],
  );

  // Today's activity count
  const todayCount = useMemo(() => {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    const t = start.getTime();
    let n = 0;
    for (const s of Object.values(store)) {
      for (const h of s.history ?? []) {
        if (h.at >= t && h.status !== "new") n++;
      }
    }
    return n;
  }, [store]);

  return {
    store,
    ready,
    getState,
    getStatus,
    setStatus,
    setStatusBulk,
    update,
    toggleFavorite,
    todayCount,
  };
}
