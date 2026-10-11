import { useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import type { Opportunity, OppStatus } from "@/lib/opportunities";

const db = supabase as any; // new table; regenerated types cover it after Lovable syncs the migration

export function useOpportunities() {
  return useQuery({
    queryKey: ["opportunities"],
    refetchInterval: 60_000,
    retry: false, // the table may not exist yet (migration not applied): show an empty radar, not an error loop
    queryFn: async (): Promise<Opportunity[]> => {
      const { data, error } = await db.from("opportunities").select("*").order("deadline", { ascending: true, nullsFirst: false }).limit(1000);
      if (error) {
        if (/relation|does not exist|schema cache/i.test(error.message)) return [];
        throw error;
      }
      return data as Opportunity[];
    },
  });
}

export function useOpportunityActions() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["opportunities"] });
  return {
    setStatus: async (id: string, status: OppStatus) => {
      const { error } = await db.from("opportunities").update({ status }).eq("id", id);
      if (error) throw error;
      refresh();
    },
    setNotes: async (id: string, notes: string) => {
      const { error } = await db.from("opportunities").update({ notes }).eq("id", id);
      if (error) throw error;
      refresh();
    },
    add: async (o: Partial<Opportunity>) => {
      const { error } = await db.from("opportunities").insert({ ...o, source: "manual", status: "saved" });
      if (error) throw error;
      refresh();
    },
  };
}
