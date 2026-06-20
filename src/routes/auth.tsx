import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { z } from "zod";
import { Film, Loader2, Mail, Lock, ArrowLeft } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable/index";
import { useToast } from "@/hooks/useToast";

export const Route = createFileRoute("/auth")({
  head: () => ({
    meta: [
      { title: "تسجيل الدخول — FAII HOUSE" },
      { name: "description", content: "دخول إلى لوحة تواصل المطاعم — FAII HOUSE." },
    ],
  }),
  component: AuthPage,
});

const emailSchema = z.string().trim().email({ message: "بريد إلكتروني غير صالح" }).max(255);
const passwordSchema = z.string().min(8, { message: "كلمة المرور يجب أن تكون 8 أحرف على الأقل" }).max(128);

function AuthPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) navigate({ to: "/" });
    });
  }, [navigate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const emailRes = emailSchema.safeParse(email);
    if (!emailRes.success) { toast.push(emailRes.error.issues[0].message, "error"); return; }
    const passRes = passwordSchema.safeParse(password);
    if (!passRes.success) { toast.push(passRes.error.issues[0].message, "error"); return; }
    setBusy(true);
    try {
      if (mode === "signup") {
        const { error } = await supabase.auth.signUp({
          email: emailRes.data,
          password: passRes.data,
          options: {
            emailRedirectTo: window.location.origin,
            data: { full_name: name.trim() || emailRes.data.split("@")[0] },
          },
        });
        if (error) throw error;
        toast.push("تم إنشاء الحساب بنجاح", "success");
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email: emailRes.data,
          password: passRes.data,
        });
        if (error) throw error;
        toast.push("مرحباً بعودتك", "success");
      }
      navigate({ to: "/" });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "خطأ غير متوقع";
      toast.push(msg.includes("Invalid login") ? "بيانات الدخول غير صحيحة" : msg, "error");
    } finally {
      setBusy(false);
    }
  };

  const google = async () => {
    setBusy(true);
    const result = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin });
    if (result.error) {
      toast.push("تعذّر تسجيل الدخول عبر Google", "error");
      setBusy(false);
      return;
    }
    if (result.redirected) return;
    navigate({ to: "/" });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background text-foreground px-4" dir="rtl">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gold-soft border border-gold/30 mb-4">
            <Film className="w-7 h-7 text-gold" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight">FAII HOUSE</h1>
          <p className="text-sm text-muted-foreground mt-2">لوحة تواصل المطاعم — استوديو إنتاج سينمائي</p>
        </div>

        <div className="rounded-2xl border border-border bg-card p-6 shadow-xl">
          <div className="flex bg-surface-2 rounded-lg p-1 mb-6">
            <button
              onClick={() => setMode("signin")}
              className={`flex-1 text-sm font-semibold py-2 rounded-md transition-colors ${mode === "signin" ? "bg-gold text-primary-foreground" : "text-muted-foreground"}`}
            >
              دخول
            </button>
            <button
              onClick={() => setMode("signup")}
              className={`flex-1 text-sm font-semibold py-2 rounded-md transition-colors ${mode === "signup" ? "bg-gold text-primary-foreground" : "text-muted-foreground"}`}
            >
              إنشاء حساب
            </button>
          </div>

          <button
            onClick={google}
            disabled={busy}
            className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-border bg-surface-2 hover:bg-accent text-sm font-semibold disabled:opacity-50"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
            متابعة عبر Google
          </button>

          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-border" />
            <span className="text-[11px] text-muted-foreground">أو</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <form onSubmit={submit} className="space-y-3">
            {mode === "signup" && (
              <div>
                <label className="block text-xs text-muted-foreground mb-1.5">الاسم الكامل</label>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={80}
                  placeholder="اسمك"
                  className="w-full px-3 py-2.5 rounded-lg bg-surface-2 border border-border focus:border-gold/50 outline-none text-sm"
                />
              </div>
            )}
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">البريد الإلكتروني</label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full pr-9 pl-3 py-2.5 rounded-lg bg-surface-2 border border-border focus:border-gold/50 outline-none text-sm"
                  placeholder="you@studio.com"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1.5">كلمة المرور</label>
              <div className="relative">
                <Lock className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className="w-full pr-9 pl-3 py-2.5 rounded-lg bg-surface-2 border border-border focus:border-gold/50 outline-none text-sm"
                  placeholder="٨ أحرف على الأقل"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gold text-primary-foreground font-bold hover:bg-gold/90 disabled:opacity-50"
            >
              {busy && <Loader2 className="w-4 h-4 animate-spin" />}
              {mode === "signin" ? "دخول" : "إنشاء الحساب"}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          بالمتابعة فإنك توافق على شروط استخدام منصة FAII HOUSE.
        </p>
      </div>
    </div>
  );
}
