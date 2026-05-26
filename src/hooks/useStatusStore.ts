import { useEffect, useState, useCallback } from "react";
import type { Status } from "@/lib/restaurants";

const KEY = "faii.status.v1";

type StatusMap = Record<string, Status>;

function read(): StatusMap {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}");
  } catch {
    return {};
  }
}

export function useStatusStore() {
  const [map, setMap] = useState<StatusMap>({});

  useEffect(() => {
    setMap(read());
  }, []);

  const setStatus = useCallback((id: string, status: Status) => {
    setMap((prev) => {
      const next = { ...prev, [id]: status };
      try {
        localStorage.setItem(KEY, JSON.stringify(next));
      } catch {}
      return next;
    });
  }, []);

  const getStatus = useCallback(
    (id: string): Status => map[id] ?? "new",
    [map],
  );

  return { map, setStatus, getStatus };
}
