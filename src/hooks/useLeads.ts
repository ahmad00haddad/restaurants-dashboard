import { useQuery, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { DEFAULT_TEAM, type Channel, type Lead, type LeadMessage, type TeamSettings } from "@/lib/leads";

const db = supabase as any; // new tables; regenerated types will cover them after Lovable syncs the migration

async function fetchLeads(): Promise<Lead[]> {
  const out: Lead[] = [];
  for (let from = 0; ; from += 1000) {
    const { data, error } = await db.from("leads")
      .select("*") // "*" keeps working even if a later DB update is not applied yet
      .is("deleted_at", null).order("score", { ascending: false, nullsFirst: false }).range(from, from + 999);
    if (error) throw error;
    out.push(...(data as Lead[]));
    if (!data || data.length < 1000) break;
  }
  return out;
}

export function useLeads() {
  // The PC agent changes leads too (sends, statuses) — poll so the site reflects it without a reload.
  return useQuery({ queryKey: ["leads"], queryFn: fetchLeads, staleTime: 15_000, refetchInterval: 30_000 });
}

export function useLead(id: string | null) {
  return useQuery({
    queryKey: ["lead", id],
    refetchInterval: 15_000,
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

export interface Approval extends LeadMessage {
  review: string;
  review_note: string | null;
  leads: Lead;
}

export function useApprovals() {
  return useQuery({
    queryKey: ["approvals"],
    refetchInterval: 20_000,
    queryFn: async (): Promise<Approval[]> => {
      const { data, error } = await db.from("lead_messages").select("*,leads(*)")
        .in("review", ["write", "pending", "approved", "failed"]).order("created_at");
      if (error) throw error;
      return data;
    },
  });
}

/** Is the PC agent running? It writes a heartbeat every ~20s; silent for 90s (or "stopped") = off. */
export function useAgentStatus() {
  return useQuery({
    queryKey: ["agent-status"],
    refetchInterval: 15_000,
    queryFn: async () => {
      const { data } = await db.from("agent_status").select("last_seen,model,note").eq("id", 1).maybeSingle();
      const seen = data?.last_seen ? Date.now() - new Date(data.last_seen).getTime() : Infinity;
      return { online: seen < 90_000 && data?.note !== "stopped", model: data?.model as string | null, lastSeen: data?.last_seen as string | null };
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

  const importRows = async (rows: Partial<Lead>[]) => {
      let inserted = 0, merged = 0;
      for (let i = 0; i < rows.length; i += 300) {
        const { data, error } = await db.rpc("ingest_leads", { rows: rows.slice(i, i + 300) });
        if (error) throw error;
        inserted += data.inserted; merged += data.merged;
      }
      refresh();
      return { inserted, merged };
    };

  return {
    refresh,
    importRows,
    update,
    async add(lead: Partial<Lead>) {
      const { data, error } = await db.rpc("ingest_leads", { rows: [lead] });
      if (error) throw error;
      refresh();
      return data as { inserted: number; merged: number };
    },
    /** Copy the old restaurants table into leads (duplicates are merged, safe to run many times). */
    async restoreOld() {
      const rows: Partial<Lead>[] = [];
      for (let from = 0; ; from += 1000) {
        const { data, error } = await db.from("restaurants").select("title,phone,email,website,address,city").range(from, from + 999);
        if (error) throw error;
        rows.push(...(data ?? []).map((r: any) => ({ kind: "restaurant", name: r.title, phone: r.phone, email: r.email,
          website: r.website, address: r.address, city: r.city, source: "old-list" })));
        if (!data || data.length < 1000) break;
      }
      return importRows(rows);
    },
    /** Called after the message was actually sent from Gmail/WhatsApp/Instagram. */
    async logSent(lead: Lead, channel: Channel, body: string, subject?: string) {
      await db.from("lead_messages").delete().eq("lead_id", lead.id).eq("draft", true);
      await db.from("lead_messages").insert({ lead_id: lead.id, channel, direction: "out", body, subject: subject || null });
      const patch: Partial<Lead> =
        lead.status === "new" || lead.status === "skip" ? { status: "contacted", next_action_at: today(7), needs_reply: false }
        : lead.status === "contacted" ? { followups: lead.followups + 1, next_action_at: null, needs_reply: false }
        : { needs_reply: false, next_action_at: today(3) };
      await update(lead.id, patch);
    },
    async logTheirReply(lead: Lead, channel: string, body: string) {
      await db.from("lead_messages").insert({ lead_id: lead.id, channel, direction: "in", body });
      await update(lead.id, { status: lead.status === "meeting" ? "meeting" : "replied", needs_reply: true });
    },
    /** Put a draft in the approval queue — the PC agent sends it to Telegram, then from Gmail once approved. */
    async queueForApproval(leadId: string, channel: Channel, body: string, subject?: string) {
      await db.from("lead_messages").delete().eq("lead_id", leadId).eq("draft", true);
      const { error } = await db.from("lead_messages").insert({ lead_id: leadId, channel, direction: "out", draft: true, review: "pending", body, subject: subject || null });
      if (error) throw error;
      qc.invalidateQueries({ queryKey: ["approvals"] });
      refresh(leadId);
    },
    /** Ask the PC agent to write the message locally with Ollama (free); it then arrives on Telegram for approval. */
    async requestLocalWrite(leadId: string, channel: Channel, hint?: string) {
      await db.from("lead_messages").delete().eq("lead_id", leadId).eq("draft", true);
      const { error } = await db.from("lead_messages").insert({ lead_id: leadId, channel, direction: "out", draft: true, review: "write", body: "", review_note: hint || null });
      if (error) throw error;
      qc.invalidateQueries({ queryKey: ["approvals"] });
      refresh(leadId);
    },
    /** Mark the lead's current draft (written by the AI) as waiting for approval. */
    async queueDraft(leadId: string) {
      const { error } = await db.from("lead_messages").update({ review: "pending", tg_message_id: null }).eq("lead_id", leadId).eq("draft", true);
      if (error) throw error;
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
    /** Cancel queued drafts (one, or every message still waiting for the PC to write it). */
    async cancel(ids: string[]) {
      if (!ids.length) return;
      const { error } = await db.from("lead_messages").update({ review: "rejected" }).in("id", ids);
      if (error) throw error;
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
    /** Ask the PC agent to write a failed draft again. */
    async retry(id: string) {
      const { error } = await db.from("lead_messages").update({ review: "write", review_note: null, body: "", tg_message_id: null }).eq("id", id);
      if (error) throw error;
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
    async review(id: string, review: "approved" | "rejected", body?: string, subject?: string | null) {
      const { error } = await db.from("lead_messages").update({ review, ...(body != null ? { body, subject } : {}) }).eq("id", id);
      if (error) throw error;
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
    async saveSettings(s: TeamSettings) {
      const { error } = await db.from("app_settings").update({ data: s, updated_at: new Date().toISOString() }).eq("id", 1);
      if (error) throw error;
      qc.invalidateQueries({ queryKey: ["team-settings"] });
    },
  };
}
