import { useMemo, useState } from "react";
import {
  SEGMENT_META,
  STATUS_META,
  buildEmailMessage,
  buildWhatsAppMessage,
  waLink,
  type Restaurant,
  type Status,
} from "@/lib/restaurants";
import {
  X,
  Phone,
  Globe,
  MapPin,
  Star,
  MessageCircle,
  Mail,
  Copy,
  CheckCircle2,
  Calendar,
} from "lucide-react";

interface Props {
  restaurant: Restaurant | null;
  status: Status;
  onStatusChange: (s: Status) => void;
  onClose: () => void;
}

export function ActionPanel({ restaurant, status, onStatusChange, onClose }: Props) {
  const [tab, setTab] = useState<"whatsapp" | "email">("whatsapp");
  const [copied, setCopied] = useState(false);

  const messages = useMemo(() => {
    if (!restaurant) return null;
    return {
      whatsapp: buildWhatsAppMessage(restaurant),
      email: buildEmailMessage(restaurant),
    };
  }, [restaurant]);

  if (!restaurant) {
    return (
      <aside className="hidden xl:flex w-96 shrink-0 flex-col border-r border-border bg-surface/60 items-center justify-center text-center px-8">
        <div className="w-14 h-14 rounded-full bg-gold-soft flex items-center justify-center mb-4">
          <MessageCircle className="w-6 h-6 text-gold" />
        </div>
        <div className="font-semibold text-foreground">اختر مطعماً</div>
        <div className="text-xs text-muted-foreground mt-2 leading-6">
          عند اختيار أي مطعم من الجدول، تظهر هنا تفاصيله ورسائل تواصل مخصصة جاهزة للإرسال.
        </div>
      </aside>
    );
  }

  const seg = SEGMENT_META[restaurant.segment];
  const currentMsg =
    tab === "whatsapp" ? messages!.whatsapp : messages!.email.body;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(currentMsg);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  const sendWA = () => {
    if (!restaurant.phone) return;
    window.open(waLink(restaurant.phone, messages!.whatsapp), "_blank");
    onStatusChange("whatsapp");
  };

  const sendEmail = () => {
    const m = messages!.email;
    window.open(
      `mailto:?subject=${encodeURIComponent(m.subject)}&body=${encodeURIComponent(m.body)}`,
      "_blank",
    );
    onStatusChange("email");
  };

  return (
    <aside className="hidden xl:flex w-96 shrink-0 flex-col border-r border-border bg-surface/80">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-3 bg-gradient-hero">
        <div className="min-w-0">
          <div className="text-[10px] tracking-widest uppercase text-muted-foreground">
            تفاصيل المطعم
          </div>
          <h2 className="text-lg font-bold text-foreground truncate mt-0.5">
            {restaurant.title}
          </h2>
          <div className="flex items-center gap-2 mt-1.5">
            <span
              className={`text-[11px] px-2 py-0.5 rounded-md border ${
                restaurant.segment === "premium"
                  ? "bg-gold-soft text-gold border-gold/30"
                  : restaurant.segment === "medium"
                  ? "bg-emerald-soft text-emerald border-emerald/30"
                  : "bg-accent text-muted-foreground border-border"
              }`}
            >
              {seg.label}
            </span>
            <span className="text-xs text-muted-foreground">{restaurant.category}</span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-md hover:bg-accent flex items-center justify-center text-muted-foreground"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-5 space-y-5">
        {/* Info */}
        <div className="space-y-2.5 text-sm">
          {restaurant.phone && (
            <InfoRow icon={<Phone className="w-4 h-4" />} label="هاتف">
              <a
                href={`tel:${restaurant.phone.replace(/\s/g, "")}`}
                className="text-foreground tabular-nums hover:text-gold"
              >
                {restaurant.phone}
              </a>
            </InfoRow>
          )}
          {restaurant.website && (
            <InfoRow icon={<Globe className="w-4 h-4" />} label="الموقع">
              <a
                href={restaurant.website}
                target="_blank"
                rel="noreferrer"
                className="text-emerald hover:underline truncate inline-block max-w-[200px]"
              >
                {restaurant.website.replace(/^https?:\/\//, "")}
              </a>
            </InfoRow>
          )}
          {restaurant.address && (
            <InfoRow icon={<MapPin className="w-4 h-4" />} label="العنوان">
              <span className="text-foreground">{restaurant.address}</span>
            </InfoRow>
          )}
          <InfoRow icon={<Star className="w-4 h-4 fill-current" />} label="التقييم">
            <span className="text-gold tabular-nums">{restaurant.rating} / 5.0</span>
          </InfoRow>
        </div>

        {/* Status selector */}
        <div>
          <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-2">
            تحديث الحالة
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {(Object.keys(STATUS_META) as Status[]).map((s) => {
              const meta = STATUS_META[s];
              const active = status === s;
              return (
                <button
                  key={s}
                  onClick={() => onStatusChange(s)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md border text-xs transition-all ${
                    active
                      ? "border-gold/40 bg-gold-soft text-foreground"
                      : "border-border text-muted-foreground hover:border-border-strong hover:text-foreground"
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${meta.dot}`} />
                  {meta.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Message generator */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-[11px] tracking-widest uppercase text-muted-foreground">
              رسالة تواصل مخصصة
            </div>
            <button
              onClick={copy}
              className="text-[11px] inline-flex items-center gap-1 text-muted-foreground hover:text-gold"
            >
              {copied ? (
                <>
                  <CheckCircle2 className="w-3 h-3 text-emerald" /> نُسخت
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" /> نسخ
                </>
              )}
            </button>
          </div>

          <div className="flex gap-1 mb-2 bg-surface-2 p-1 rounded-md">
            <TabBtn active={tab === "whatsapp"} onClick={() => setTab("whatsapp")}>
              <MessageCircle className="w-3.5 h-3.5" /> واتساب
            </TabBtn>
            <TabBtn active={tab === "email"} onClick={() => setTab("email")}>
              <Mail className="w-3.5 h-3.5" /> إيميل
            </TabBtn>
          </div>

          {tab === "email" && (
            <div className="mb-2 px-3 py-2 rounded-md bg-surface-2 border border-border">
              <div className="text-[10px] uppercase text-muted-foreground tracking-widest">
                العنوان
              </div>
              <div className="text-xs text-foreground mt-0.5">
                {messages!.email.subject}
              </div>
            </div>
          )}

          <div className="rounded-md bg-background border border-border p-3 text-xs leading-7 text-foreground/90 whitespace-pre-wrap max-h-72 overflow-y-auto scrollbar-thin">
            {currentMsg}
          </div>
        </div>
      </div>

      <div className="border-t border-border p-4 space-y-2 bg-surface-2/40">
        <button
          disabled={!restaurant.phone}
          onClick={sendWA}
          className="w-full inline-flex items-center justify-center gap-2 py-2.5 rounded-md bg-emerald text-background font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <MessageCircle className="w-4 h-4" />
          فتح واتساب مع الرسالة الجاهزة
        </button>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={sendEmail}
            className="inline-flex items-center justify-center gap-1.5 py-2 rounded-md bg-accent text-foreground text-xs hover:bg-accent/70"
          >
            <Mail className="w-3.5 h-3.5" /> إرسال إيميل
          </button>
          <button
            onClick={() => onStatusChange("meeting")}
            className="inline-flex items-center justify-center gap-1.5 py-2 rounded-md bg-gold text-primary-foreground text-xs font-semibold hover:opacity-90"
          >
            <Calendar className="w-3.5 h-3.5" /> حجز اجتماع
          </button>
        </div>
      </div>
    </aside>
  );
}

function InfoRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 px-3 py-2 rounded-md bg-surface-2/50 border border-border">
      <div className="flex items-center gap-2 text-muted-foreground text-xs">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-sm text-left">{children}</div>
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 rounded text-xs transition-all ${
        active
          ? "bg-card text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}
