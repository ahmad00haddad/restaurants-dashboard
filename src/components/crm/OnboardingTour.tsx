import { useEffect, useState } from "react";
import { X, ArrowLeft, ArrowRight, Sparkles, Users, MessageCircle, Search, Download, CheckCircle2 } from "lucide-react";

const KEY = "faii_onboarded_v2";

interface Step {
  icon: React.ReactNode;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    icon: <Sparkles className="w-6 h-6 text-gold" />,
    title: "أهلاً بك في FAII HOUSE CRM",
    body: "لوحتك الاحترافية لإدارة التواصل مع ١٬٠٠٠ مطعم في إربد. سنأخذك في جولة سريعة (٦٠ ثانية) لتصبح جاهزاً.",
  },
  {
    icon: <Users className="w-6 h-6 text-gold" />,
    title: "١) ابدأ بالفلاتر يميناً",
    body: "الشريط الجانبي يفلتر المطاعم حسب الشريحة (Premium/Medium)، الفئة، الحالة، الوسوم. جرّب اختيار «Premium» لترى أفضل ٢٠٠ مطعم فوراً.",
  },
  {
    icon: <MessageCircle className="w-6 h-6 text-gold" />,
    title: "٢) اضغط أي مطعم",
    body: "تظهر لوحة تفاصيل يسار الشاشة بها: أزرار واتساب/إيميل جاهزة بالرسالة المخصصة، ملاحظات، تذكير متابعة، ووسوم.",
  },
  {
    icon: <Search className="w-6 h-6 text-gold" />,
    title: "٣) بحث فوري (Ctrl+K)",
    body: "اضغط Ctrl+K في أي وقت للقفز مباشرة لأي مطعم بالاسم. اضغط / للتركيز على شريط البحث، K لتبديل بين الجدول و Kanban.",
  },
  {
    icon: <Download className="w-6 h-6 text-gold" />,
    title: "٤) التحليلات والإدارة",
    body: "من الشريط العلوي: «التحليلات» لقمع المبيعات والإحصاءات. «إدارة البيانات» لإضافة/تعديل/حذف مطاعم واكتشاف المكرر.",
  },
  {
    icon: <CheckCircle2 className="w-6 h-6 text-emerald" />,
    title: "جاهز!",
    body: "خطة عملك اليومية: افتح المفضلة → أرسل ١٠ رسائل واتساب → سجّل حالتها. حظاً موفقاً 🎬",
  },
];

interface Props { forceOpen?: boolean; onClose?: () => void; }

export function OnboardingTour({ forceOpen = false, onClose }: Props) {
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);

  useEffect(() => {
    if (forceOpen) { setOpen(true); setI(0); return; }
    if (typeof window === "undefined") return;
    if (!localStorage.getItem(KEY)) {
      setOpen(true);
    }
  }, [forceOpen]);

  const close = () => {
    try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ }
    setOpen(false);
    onClose?.();
  };

  if (!open) return null;
  const step = STEPS[i];
  const last = i === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-md flex items-center justify-center px-4" onClick={close}>
      <div
        className="w-full max-w-md rounded-2xl border border-gold/30 bg-card shadow-[0_25px_80px_-15px_rgba(212,168,76,0.35)] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 pt-4">
          <div className="flex items-center gap-1.5">
            {STEPS.map((_, idx) => (
              <span key={idx} className={`h-1.5 rounded-full transition-all ${idx === i ? "w-6 bg-gold" : idx < i ? "w-3 bg-gold/50" : "w-3 bg-border"}`} />
            ))}
          </div>
          <button onClick={close} className="p-1 rounded hover:bg-accent text-muted-foreground" aria-label="إغلاق">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 py-6 text-center">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-gold-soft border border-gold/30 flex items-center justify-center mb-4">
            {step.icon}
          </div>
          <h2 className="text-xl font-bold text-foreground mb-2">{step.title}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">{step.body}</p>
        </div>
        <div className="flex items-center justify-between px-5 py-4 border-t border-border bg-surface-2/50">
          <button
            onClick={close}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            تخطّي
          </button>
          <div className="flex items-center gap-2">
            {i > 0 && (
              <button
                onClick={() => setI(i - 1)}
                className="inline-flex items-center gap-1 text-xs px-3 py-1.5 rounded-full border border-border hover:bg-accent"
              >
                <ArrowRight className="w-3.5 h-3.5" /> السابق
              </button>
            )}
            <button
              onClick={() => (last ? close() : setI(i + 1))}
              className="inline-flex items-center gap-1 text-xs px-4 py-1.5 rounded-full bg-gold text-primary-foreground font-semibold hover:brightness-110"
            >
              {last ? "ابدأ الآن" : "التالي"}
              {!last && <ArrowLeft className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function resetOnboarding() {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}
