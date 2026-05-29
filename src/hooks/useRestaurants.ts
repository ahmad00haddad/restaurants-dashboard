import { useSyncExternalStore } from "react";
import {
  RESTAURANTS as SEED,
  detectCategory,
  detectSegment,
  ratingFromRank,
  type RawRestaurant,
  type Restaurant,
} from "@/lib/restaurants";

const KEY = "faii.restaurants.v1";

interface Overrides {
  deleted: string[];                                  // ids of seed entries removed
  edits: Record<string, Partial<RawRestaurant>>;      // patch by seed id
  added: Array<RawRestaurant & { id: string }>;       // brand new entries
}

const seedById = new Map(SEED.map((r) => [r.id, r]));
let overrides: Overrides = { deleted: [], edits: {}, added: [] };
let current: Restaurant[] = [];
const listeners = new Set<() => void>();

function load() {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      overrides = {
        deleted: Array.isArray(parsed.deleted) ? parsed.deleted : [],
        edits: parsed.edits && typeof parsed.edits === "object" ? parsed.edits : {},
        added: Array.isArray(parsed.added) ? parsed.added : [],
      };
    }
  } catch {}
}

function save() {
  try { localStorage.setItem(KEY, JSON.stringify(overrides)); } catch {}
}

function buildOne(base: RawRestaurant, id: string): Restaurant {
  return {
    ...base,
    id,
    segment: detectSegment(base),
    category: detectCategory(base.title),
    rating: ratingFromRank(base.rank),
  };
}

function recompute() {
  const deletedSet = new Set(overrides.deleted);
  const fromSeed: Restaurant[] = [];
  for (const r of SEED) {
    if (deletedSet.has(r.id)) continue;
    const edit = overrides.edits[r.id];
    if (edit) {
      const merged = { ...r, ...edit } as RawRestaurant;
      fromSeed.push(buildOne(merged, r.id));
    } else {
      fromSeed.push(r);
    }
  }
  const added = overrides.added.map((a) => buildOne(a, a.id));
  current = [...fromSeed, ...added];
}

load();
recompute();

const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };
const getSnapshot = () => current;
const emit = () => { listeners.forEach((l) => l()); };

export function useRestaurants(): Restaurant[] {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function getRestaurants(): Restaurant[] { return current; }
export function getRestaurantById(id: string): Restaurant | undefined {
  return current.find((r) => r.id === id);
}

export function deleteRestaurants(ids: string[]) {
  const idSet = new Set(ids);
  const newDeleted = new Set(overrides.deleted);
  for (const id of ids) if (seedById.has(id)) newDeleted.add(id);
  overrides.deleted = [...newDeleted];
  overrides.added = overrides.added.filter((a) => !idSet.has(a.id));
  for (const id of ids) delete overrides.edits[id];
  save(); recompute(); emit();
}

export function updateRestaurant(id: string, patch: Partial<RawRestaurant>) {
  if (seedById.has(id)) {
    overrides.edits[id] = { ...(overrides.edits[id] ?? {}), ...patch };
  } else {
    const a = overrides.added.find((x) => x.id === id);
    if (a) Object.assign(a, patch);
  }
  save(); recompute(); emit();
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

export function addRestaurant(input: NewRestaurantInput): string {
  const id = `new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const maxRank = current.reduce((m, r) => Math.max(m, r.rank), 0);
  const entry: RawRestaurant & { id: string } = {
    id,
    title: input.title.trim(),
    phone: input.phone?.trim() || null,
    website: input.website?.trim() || undefined,
    address: input.address?.trim() || null,
    street: input.street?.trim() || null,
    city: input.city?.trim() || "إربد",
    rank: input.rank && input.rank > 0 ? input.rank : maxRank + 1,
  };
  overrides.added.push(entry);
  save(); recompute(); emit();
  return id;
}

export function restoreAllRestaurants() {
  overrides = { deleted: [], edits: {}, added: [] };
  save(); recompute(); emit();
}

export function restaurantStats() {
  return {
    total: current.length,
    deleted: overrides.deleted.length,
    edited: Object.keys(overrides.edits).length,
    added: overrides.added.length,
  };
}
