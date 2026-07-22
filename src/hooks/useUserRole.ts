import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

export type AppRole = "admin" | "user";

async function fetchRoles(): Promise<AppRole[]> {
  const { data: auth } = await supabase.auth.getUser();
  const uid = auth.user?.id;
  if (!uid) return [];
  const { data, error } = await supabase
    .from("user_roles")
    .select("role")
    .eq("user_id", uid);
  if (error) return [];
  return (data ?? []).map((r) => r.role as AppRole);
}

export function useUserRole() {
  const { data: roles = [], isLoading } = useQuery({
    queryKey: ["user-roles"],
    queryFn: fetchRoles,
    staleTime: 5 * 60_000,
  });
  return {
    roles,
    isAdmin: roles.includes("admin"),
    loading: isLoading,
  };
}
