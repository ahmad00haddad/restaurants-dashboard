import { useEffect, useState, useCallback } from "react";

const KEY = "faii.settings.v1";

export interface Settings {
  senderName: string;
  senderRole: string;
  signature: string;
  discountPct: number; // 0-50
  currency: string;
  portfolioUrl: string;
}

export const DEFAULT_SETTINGS: Settings = {
  senderName: "أحمد حداد",
  senderRole: "Creative Director",
  signature: "FAII HOUSE — Cinematic Studio",
  discountPct: 10,
  currency: "د.أ",
  portfolioUrl: "https://behance.net/ahmad00haddad",
};

export function useSettings() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(raw) });
    } catch {}
    setReady(true);
  }, []);

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      try { localStorage.setItem(KEY, JSON.stringify(next)); } catch {}
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setSettings(DEFAULT_SETTINGS);
    try { localStorage.removeItem(KEY); } catch {}
  }, []);

  return { settings, update, reset, ready };
}
