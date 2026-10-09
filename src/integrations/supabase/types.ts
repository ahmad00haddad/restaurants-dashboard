export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      app_settings: {
        Row: {
          data: Json
          id: number
          updated_at: string
        }
        Insert: {
          data?: Json
          id?: number
          updated_at?: string
        }
        Update: {
          data?: Json
          id?: number
          updated_at?: string
        }
        Relationships: []
      }
      crm_states: {
        Row: {
          created_at: string
          deal_value: number | null
          favorite: boolean
          follow_up: string | null
          history: Json
          id: string
          notes: string | null
          restaurant_id: string
          status: Database["public"]["Enums"]["crm_status"]
          tags: string[]
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          deal_value?: number | null
          favorite?: boolean
          follow_up?: string | null
          history?: Json
          id?: string
          notes?: string | null
          restaurant_id: string
          status?: Database["public"]["Enums"]["crm_status"]
          tags?: string[]
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          deal_value?: number | null
          favorite?: boolean
          follow_up?: string | null
          history?: Json
          id?: string
          notes?: string | null
          restaurant_id?: string
          status?: Database["public"]["Enums"]["crm_status"]
          tags?: string[]
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "crm_states_restaurant_id_fkey"
            columns: ["restaurant_id"]
            isOneToOne: false
            referencedRelation: "restaurants"
            referencedColumns: ["id"]
          },
        ]
      }
      lead_messages: {
        Row: {
          body: string
          channel: string
          created_at: string
          created_by: string | null
          direction: string
          draft: boolean
          id: string
          lead_id: string
          review: string | null
          review_note: string | null
          sent_at: string | null
          subject: string | null
          tg_message_id: number | null
        }
        Insert: {
          body: string
          channel: string
          created_at?: string
          created_by?: string | null
          direction: string
          draft?: boolean
          id?: string
          lead_id: string
          review?: string | null
          review_note?: string | null
          sent_at?: string | null
          subject?: string | null
          tg_message_id?: number | null
        }
        Update: {
          body?: string
          channel?: string
          created_at?: string
          created_by?: string | null
          direction?: string
          draft?: boolean
          id?: string
          lead_id?: string
          review?: string | null
          review_note?: string | null
          sent_at?: string | null
          subject?: string | null
          tg_message_id?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "lead_messages_lead_id_fkey"
            columns: ["lead_id"]
            isOneToOne: false
            referencedRelation: "leads"
            referencedColumns: ["id"]
          },
        ]
      }
      leads: {
        Row: {
          about: string | null
          address: string | null
          category: string | null
          city: string | null
          created_at: string
          deal_value: number | null
          deleted_at: string | null
          domain: string | null
          email: string | null
          facebook: string | null
          followups: number
          id: string
          instagram: string | null
          kind: string
          linkedin: string | null
          maps_url: string | null
          name: string
          name_key: string | null
          needs_reply: boolean
          next_action_at: string | null
          notes: string | null
          phone: string | null
          phone_key: string | null
          profile: Json | null
          rating: number | null
          score: number | null
          signal: string | null
          signal_until: string | null
          signal_url: string | null
          source: string | null
          status: string
          tiktok: string | null
          updated_at: string
          website: string | null
          youtube: string | null
        }
        Insert: {
          about?: string | null
          address?: string | null
          category?: string | null
          city?: string | null
          created_at?: string
          deal_value?: number | null
          deleted_at?: string | null
          domain?: string | null
          email?: string | null
          facebook?: string | null
          followups?: number
          id?: string
          instagram?: string | null
          kind?: string
          linkedin?: string | null
          maps_url?: string | null
          name: string
          name_key?: string | null
          needs_reply?: boolean
          next_action_at?: string | null
          notes?: string | null
          phone?: string | null
          phone_key?: string | null
          profile?: Json | null
          rating?: number | null
          score?: number | null
          signal?: string | null
          signal_until?: string | null
          signal_url?: string | null
          source?: string | null
          status?: string
          tiktok?: string | null
          updated_at?: string
          website?: string | null
          youtube?: string | null
        }
        Update: {
          about?: string | null
          address?: string | null
          category?: string | null
          city?: string | null
          created_at?: string
          deal_value?: number | null
          deleted_at?: string | null
          domain?: string | null
          email?: string | null
          facebook?: string | null
          followups?: number
          id?: string
          instagram?: string | null
          kind?: string
          linkedin?: string | null
          maps_url?: string | null
          name?: string
          name_key?: string | null
          needs_reply?: boolean
          next_action_at?: string | null
          notes?: string | null
          phone?: string | null
          phone_key?: string | null
          profile?: Json | null
          rating?: number | null
          score?: number | null
          signal?: string | null
          signal_until?: string | null
          signal_url?: string | null
          source?: string | null
          status?: string
          tiktok?: string | null
          updated_at?: string
          website?: string | null
          youtube?: string | null
        }
        Relationships: []
      }
      profiles: {
        Row: {
          avatar_url: string | null
          created_at: string
          display_name: string | null
          id: string
          updated_at: string
        }
        Insert: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string | null
          id: string
          updated_at?: string
        }
        Update: {
          avatar_url?: string | null
          created_at?: string
          display_name?: string | null
          id?: string
          updated_at?: string
        }
        Relationships: []
      }
      restaurants: {
        Row: {
          address: string | null
          city: string | null
          created_at: string
          created_by: string | null
          deleted_at: string | null
          email: string | null
          external_id: string | null
          id: string
          phone: string | null
          rank: number
          street: string | null
          title: string
          updated_at: string
          website: string | null
        }
        Insert: {
          address?: string | null
          city?: string | null
          created_at?: string
          created_by?: string | null
          deleted_at?: string | null
          email?: string | null
          external_id?: string | null
          id?: string
          phone?: string | null
          rank?: number
          street?: string | null
          title: string
          updated_at?: string
          website?: string | null
        }
        Update: {
          address?: string | null
          city?: string | null
          created_at?: string
          created_by?: string | null
          deleted_at?: string | null
          email?: string | null
          external_id?: string | null
          id?: string
          phone?: string | null
          rank?: number
          street?: string | null
          title?: string
          updated_at?: string
          website?: string | null
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          created_at: string
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
      ingest_leads: { Args: { rows: Json }; Returns: Json }
      leads_keys_of: {
        Args: { t: Database["public"]["Tables"]["leads"]["Row"] }
        Returns: {
          domain: string
          name_key: string
          phone_key: string
        }[]
      }
    }
    Enums: {
      app_role: "admin" | "user"
      crm_status: "new" | "email" | "whatsapp" | "meeting"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["admin", "user"],
      crm_status: ["new", "email", "whatsapp", "meeting"],
    },
  },
} as const
