import { useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { DEFAULT_TEAM, type Channel, type Lead, type LeadMessage, type TeamSettings } from "@/lib/leads";

const db = supabase as any; // new tables; regenerated types will cover them after Lovable syncs the migration

async function fetchLeads(): Promise<Lead[]> {
  const out: Lead[] = [];
  for (let from = 0; ; from += 1000) {
    const { data, error } = await db.from("leads")
      .select("id,kind,name,category,city,address,phone,email,website,instagram,facebook,linkedin,youtube,tiktok,rating,maps_url,profile,score,status,followups,next_action_at,needs_reply,notes,source,signal,signal_url,signal_until,deal_value,created_at")
      .is("deleted_at", null).order("score", { ascending: false, nullsFirst: false }).range(from, from + 999);
    if (error) throw error;
    out.push(...(data as Lead[]));
    if (!data || data.length < 1000) break;
  }
  return out;
}

export function useLeads() {
  return useQuery({ queryKey: ["leads"], queryFn: fetchLeads, staleTime: 30_000 });
}

export function useLead(id: string | null) {
  return useQuery({
    queryKey: ["lead", id],
    enabled: !!id,
    queryFn: async () => {
      const [{ data: lead, error }, { data: msgs }] = await Promise.all([
        db.from("leads").select("*").eq("id", id).single(),
        db.from("lead_messages").select("*").eq("lead_id", id).order("created_at"),
      ]);
      if (error) throw error;
      return { lead: lead as Lead & { about: string | null }, msgs: (msgs ?? []) as LeadMessage[] };
    },
  });
}

export function useTeamSettings() {
  return useQuery({
    queryKey: ["team-settings"],
    queryFn: async (): Promise<TeamSettings> => {
      const { data } = await db.from("app_settings").select("data").eq("id", 1).maybeSingle();
      return { ...DEFAULT_TEAM, ...(data?.data ?? {}) };
    },
  });
}

export function useLeadActions() {
  const qc = useQueryClient();
  const refresh = (id?: string) => {
    qc.invalidateQueries({ queryKey: ["leads"] });
    if (id) qc.invalidateQueries({ queryKey: ["lead", id] });
  };
  const today = (plus = 0) => new Date(Date.now() + plus * 864e5).toISOString().slice(0, 10);

  const update = async (id: string, patch: Partial<Lead>) => {
    const { error } = await db.from("leads").update(patch).eq("id", id);
    if (error) throw error;
    refresh(id);
  };

  return {
    refresh,
    update,
    async add(lead: Partial<Lead>) {
      const { data, error } = await db.rpc("ingest_leads", { rows: [lead] });
      if (error) throw error;
      refresh();
      return data as { inserted: number; merged: number };
    },
    async importRows(rows: Partial<Lead>[]) {
      let inserted = 0, merged = 0;
      for (let i = 0; i < rows.length; i += 300) {
        const { data, error } = await db.rpc("ingest_leads", { rows: rows.slice(i, i + 300) });
        if (error) throw error;
        inserted += data.inserted; merged += data.merged;
      }
      refresh();
      return { inserted, merged };
    },
    /** Called after the message was actually sent from Gmail/WhatsApp/Instagram. */
    async logSent(lead: Lead, channel: Channel, body: string, subject?: string) {
      await db.from("lead_messages").delete().eq("lead_id", lead.id).eq("draft", true);
      await db.from("lead_messages").insert({ lead_id: lead.id, channel, direction: "out", body, subject: subject || null });
      const patch: Partial<Lead> =
        lead.status === "new" || lead.status === "skip" ? { status: "contacted", next_action_at: today(4), needs_reply: false }
        : lead.status === "contacted" ? { followups: lead.followups + 1, next_action_at: today(6), needs_reply: false }
        : { needs_reply: false, next_action_at: today(3) };
      await update(lead.id, patch);
    },
    async logTheirReply(lead: Lead, channel: string, body: string) {
      await db.from("lead_messages").insert({ lead_id: lead.id, channel, direction: "in", body });
      await update(lead.id, { status: lead.status === "meeting" ? "meeting" : "replied", needs_reply: true });
    },
    async saveSettings(s: TeamSettings) {
      const { error } = await db.from("app_settings").update({ data: s, updated_at: new Date().toISOString() }).eq("id", 1);
      if (error) throw error;
      qc.invalidateQueries({ queryKey: ["team-settings"] });
    },
  };
}
