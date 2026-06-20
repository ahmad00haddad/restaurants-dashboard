import type { QueryClient } from "@tanstack/react-query";

let _qc: QueryClient | null = null;

export function setGlobalQueryClient(qc: QueryClient) {
  _qc = qc;
}

export function getGlobalQueryClient(): QueryClient | null {
  return _qc;
}
