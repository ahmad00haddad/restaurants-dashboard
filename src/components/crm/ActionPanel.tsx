import { useMemo, useState } from "react";
import {
  SEGMENT_META,
  STATUS_META,
  buildEmailMessage,
  buildWhatsAppMessage,
  normalizeJordanianPhone,
  waLink,
  leadScore,
  scoreTier,
  type Restaurant,
  type Status,
} from "@/lib/restaurants";
import {
  SERVICES,
  SERVICE_BY_KEY,
  buildProposal,
  buildServiceMessage,
  priceFor,
  openPrintableProposal,
  type ServiceKey,
} from "@/lib/services";
import type { RestaurantState } from "@/hooks/useCrmStore";
import type { Settings } from "@/hooks/useSettings";
import {
  X, Phone, Globe, MapPin, Star, MessageCircle, Mail, Copy, CheckCircle2,
  Calendar, StickyNote, History, Sparkles, Tag, FileText, Plus, Printer, DollarSign, Flame,
  Shuffle, Search as SearchIcon, Loader2, Wand2, RotateCcw,
} from "lucide-react";
import { useToast } from "@/hooks/useToast";
import { useServerFn } from "@tanstack/react-start";
import { useQueryClient } from "@tanstack/react-query";
import { scrapeEmailForRestaurant } from "@/lib/scrape.functions";
import { composeOutreach } from "@/lib/ai.functions";


interface Props {
  restaurant: Restaurant | null;
  state: RestaurantState;
  settings: Settings;
  onStatusChange: (s: Status) => void;
  onToggleFavorite: () => void;
  onUpdate: (patch: Partial<RestaurantState>) => void;
  onAddTag: (tag: string) => void;
  onRemoveTag: (tag: string) => void;
  onClose: () => void;
}

type Tab = "whatsapp" | "email" | "proposal";
type AiTone = "friendly" | "formal" | "short" | "bold";

const TONE_LABEL: Record<AiTone, string> = {
  friendly: "ودّي",
  formal: "رسمي",
  short: "مختصر",
  bold: "جريء",
};


export function ActionPanel({
  restaurant, state, settings, onStatusChange, onToggleFavorite, onUpdate, onAddTag, onRemoveTag, onClose,
}: Props) {
  const [tab, setTab] = useState<Tab>("whatsapp");
  const [copied, setCopied] = useState(false);
  const [serviceKey, setServiceKey] = useState<ServiceKey | null>(null);
  const [proposalServices, setProposalServices] = useState<Set<ServiceKey>>(new Set(["reel"]));
  const [tagInput, setTagInput] = useState("");
  const [variantNonce, setVariantNonce] = useState(0);
  const [scrapingEmail, setScrapingEmail] = useState(false);
  const [tone, setTone] = useState<AiTone>("friendly");
  const [aiLoading, setAiLoading] = useState(false);
  const [aiWa, setAiWa] = useState<string | null>(null);
  const [aiEmail, setAiEmail] = useState<{ subject?: string; body: string } | null>(null);
  const toast = useToast();
  const scrapeOne = useServerFn(scrapeEmailForRestaurant);
  const compose = useServerFn(composeOutreach);
  const qc = useQueryClient();

  const messages = useMemo(() => {
    if (!restaurant) return null;
    const wa = aiWa ?? (serviceKey
      ? buildServiceMessage(restaurant, serviceKey, settings)
      : buildWhatsAppMessage(restaurant, settings, variantNonce));
    const tpl = buildEmailMessage(restaurant, settings, variantNonce);
    const baseEmail = aiEmail
      ? { subject: aiEmail.subject ?? tpl.subject, body: aiEmail.body }
      : tpl;
    const proposal = buildProposal(restaurant, [...proposalServices], settings);
    return { whatsapp: wa, email: baseEmail, proposal };
  }, [restaurant, serviceKey, proposalServices, settings, variantNonce, aiWa, aiEmail]);

  // Reset AI drafts when switching restaurant
  const currentId = restaurant?.id ?? null;
  const [lastId, setLastId] = useState<string | null>(currentId);
  if (currentId !== lastId) {
    setLastId(currentId);
    setAiWa(null);
    setAiEmail(null);
  }

  const runAi = async () => {
    if (!restaurant) return;
    const channel: "whatsapp" | "email" = tab === "email" ? "email" : "whatsapp";
    setAiLoading(true);
    try {
      const res = await compose({
        data: {
          channel,
          tone,
          restaurant: {
            title: restaurant.title,
            category: restaurant.category,
            segment: SEGMENT_META[restaurant.segment].label,
            city: restaurant.city,
            website: restaurant.website ?? null,
            rating: restaurant.rating,
          },
          service: serviceKey ? SERVICE_BY_KEY[serviceKey].label : undefined,
          price: serviceKey ? priceFor(restaurant, serviceKey) : undefined,
          currency: settings.currency,
          sender: {
            name: settings.senderName,
            role: settings.senderRole,
            signature: settings.signature,
            portfolioUrl: settings.portfolioUrl,
          },
          notes: state.notes || undefined,
          language: "ar" as const,
        },
      });
      if (channel === "email") setAiEmail({ subject: res.subject, body: res.body });
      else setAiWa(res.body);
      toast.push("تمت كتابة رسالة مخصّصة ✍️", "success");
    } catch (e) {
      toast.push((e as Error).message || "تعذّر التوليد", "error");
    } finally {
      setAiLoading(false);
    }
  };


  if (!restaurant) {
    return (
      <aside className="hidden xl:flex w-96 shrink-0 flex-col border-r border-border bg-surface/60 items-center justify-center text-center px-8">
        <div className="w-14 h-14 rounded-full bg-gold-soft flex items-center justify-center mb-4">
          <MessageCircle className="w-6 h-6 text-gold" />
        </div>
        <div className="font-semibold text-foreground">اختر مطعماً</div>
        <div className="text-xs text-muted-foreground mt-2 leading-6">
          تظهر هنا تفاصيل المطعم، باقات الخدمات بأسعار مخصصة لشريحته، رسائل تواصل،
          عرض سعر جاهز للنسخ، ووسوم وملاحظات داخلية.
        </div>
        <div className="mt-6 text-[10px] tracking-widest uppercase text-muted-foreground/60">
          اضغط <kbd className="px-1.5 py-0.5 rounded bg-surface-2 border border-border mx-1">/</kbd> للبحث،
          <kbd className="px-1.5 py-0.5 rounded bg-surface-2 border border-border mx-1">⌘K</kbd> للوحة الأوامر
        </div>
      </aside>
    );
  }

  const seg = SEGMENT_META[restaurant.segment];
  const status = (state.status ?? "new") as Status;
  const currentMsg =
    tab === "whatsapp" ? messages!.whatsapp :
    tab === "email" ? messages!.email.body :
    messages!.proposal;
  const intlPhone = normalizeJordanianPhone(restaurant.phone);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(currentMsg);
      setCopied(true);
      toast.push("تم نسخ المحتوى", "success");
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  const sendWA = () => {
    if (!restaurant.phone) return;
    window.open(waLink(restaurant.phone, messages!.whatsapp), "_blank");
    onStatusChange("whatsapp");
    toast.push("تم فتح واتساب وتحديث الحالة");
  };

  const sendEmail = () => {
    const m = messages!.email;
    const to = restaurant.email ?? "";
    window.open(
      `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(m.subject)}&body=${encodeURIComponent(m.body)}`,
      "_blank",
    );
    onStatusChange("email");
    toast.push(to ? `تم فتح الإيميل إلى ${to}` : "تم تجهيز الإيميل");
  };

  const scrapeEmail = async () => {
    setScrapingEmail(true);
    try {
      const res = await scrapeOne({ data: { restaurantId: restaurant.id } });
      if (res.found) {
        qc.invalidateQueries({ queryKey: ["restaurants"] });
        toast.push(`تم العثور على: ${res.email}`, "success");
      } else {
        const reason =
          res.reason === "no_website" ? "لا يوجد موقع" :
          res.reason === "not_found_on_site" ? "لم نجد إيميل في الموقع" :
          "غير متوفر";
        toast.push(`تعذّر الاستخراج (${reason})`, "info");
      }
    } catch (e) {
      toast.push(`فشل: ${(e as Error).message}`, "error");
    } finally {
      setScrapingEmail(false);
    }
  };


  const toggleProposalService = (k: ServiceKey) => {
    const n = new Set(proposalServices);
    if (n.has(k)) n.delete(k); else n.add(k);
    if (n.size === 0) n.add(k); // keep at least one
    setProposalServices(n);
  };

  const addTagSubmit = () => {
    const t = tagInput.trim();
    if (!t) return;
    onAddTag(t);
    setTagInput("");
  };

  return (
    <aside className="hidden xl:flex w-[26rem] shrink-0 flex-col border-r border-border bg-surface/80">
      <div className="px-5 py-4 border-b border-border flex items-start justify-between gap-3 bg-gradient-hero">
        <div className="min-w-0">
          <div className="text-[10px] tracking-widest uppercase text-muted-foreground">تفاصيل المطعم</div>
          <h2 className="text-lg font-bold text-foreground truncate mt-0.5">{restaurant.title}</h2>
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            <span className={`text-[11px] px-2 py-0.5 rounded-md border ${
              restaurant.segment === "premium"
                ? "bg-gold-soft text-gold border-gold/30"
                : restaurant.segment === "medium"
                ? "bg-emerald-soft text-emerald border-emerald/30"
                : "bg-accent text-muted-foreground border-border"
            }`}>{seg.label}</span>
            <span className="text-xs text-muted-foreground">{restaurant.category}</span>
            {(() => {
              const sc = leadScore(restaurant);
              const tier = scoreTier(sc);
              const cls = tier.color === "gold"
                ? "bg-gold-soft text-gold border-gold/30"
                : tier.color === "emerald"
                ? "bg-emerald-soft text-emerald border-emerald/30"
                : "bg-accent text-muted-foreground border-border";
              return (
                <span title={`Lead Score ${sc}/100`} className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-md border ${cls}`}>
                  <Flame className="w-3 h-3" /> {tier.label} · {sc}
                </span>
              );
            })()}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onToggleFavorite}
            title="مفضلة"
            className={`w-8 h-8 rounded-md flex items-center justify-center hover:bg-accent ${
              state.favorite ? "text-gold" : "text-muted-foreground"
            }`}
          >
            <Star className={`w-4 h-4 ${state.favorite ? "fill-current" : ""}`} />
          </button>
          <button onClick={onClose} className="w-8 h-8 rounded-md hover:bg-accent flex items-center justify-center text-muted-foreground">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-5 space-y-5">
        {/* Info */}
        <div className="space-y-2.5 text-sm">
          {restaurant.phone && (
            <InfoRow icon={<Phone className="w-4 h-4" />} label="هاتف">
              <a href={`tel:${restaurant.phone.replace(/\s/g, "")}`} className="text-foreground tabular-nums hover:text-gold">
                {restaurant.phone}
              </a>
            </InfoRow>
          )}
          {intlPhone && (
            <InfoRow icon={<MessageCircle className="w-4 h-4" />} label="دولي">
              <span className="text-emerald tabular-nums">+{intlPhone}</span>
            </InfoRow>
          )}
          {restaurant.website && (
            <InfoRow icon={<Globe className="w-4 h-4" />} label="الموقع">
              <a href={restaurant.website} target="_blank" rel="noreferrer"
                className="text-emerald hover:underline truncate inline-block max-w-[200px]">
                {restaurant.website.replace(/^https?:\/\//, "")}
              </a>
            </InfoRow>
          )}
          <InfoRow icon={<Mail className="w-4 h-4" />} label="إيميل">
            {restaurant.email ? (
              <a href={`mailto:${restaurant.email}`} className="text-emerald hover:underline truncate inline-block max-w-[200px]">
                {restaurant.email}
              </a>
            ) : (
              <button
                onClick={scrapeEmail}
                disabled={scrapingEmail || !restaurant.website}
                title={!restaurant.website ? "لا يوجد موقع للاستخراج منه" : "استخراج الإيميل من موقع المطعم"}
                className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border border-emerald/40 bg-emerald-soft text-emerald hover:bg-emerald/20 disabled:opacity-50"
              >
                {scrapingEmail ? <Loader2 className="w-3 h-3 animate-spin" /> : <SearchIcon className="w-3 h-3" />}
                {restaurant.website ? "استخراج من الموقع" : "لا يوجد"}
              </button>
            )}
          </InfoRow>

          {restaurant.address && (
            <InfoRow icon={<MapPin className="w-4 h-4" />} label="العنوان">
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(
                  restaurant.address + " " + (restaurant.city ?? "إربد"),
                )}`}
                target="_blank" rel="noreferrer" className="text-foreground hover:text-gold"
              >
                {restaurant.address}
              </a>
            </InfoRow>
          )}
          <InfoRow icon={<Star className="w-4 h-4 fill-current" />} label="التقييم">
            <span className="text-gold tabular-nums">{restaurant.rating} / 5.0</span>
          </InfoRow>
        </div>

        {/* Status selector */}
        <div>
          <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-2">تحديث الحالة</div>
          <div className="grid grid-cols-2 gap-1.5">
            {(Object.keys(STATUS_META) as Status[]).map((s) => {
              const meta = STATUS_META[s];
              const active = status === s;
              return (
                <button
                  key={s}
                  onClick={() => onStatusChange(s)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md border text-xs transition-all ${
                    active ? "border-gold/40 bg-gold-soft text-foreground"
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

        {/* Service packages */}
        <div>
          <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-gold" /> باقات الخدمات والأسعار
          </div>
          <div className="grid grid-cols-1 gap-1.5">
            {SERVICES.map((s) => {
              const active = serviceKey === s.key;
              const price = priceFor(restaurant, s.key);
              return (
                <button
                  key={s.key}
                  onClick={() => setServiceKey(active ? null : s.key)}
                  className={`flex items-center justify-between gap-2 px-3 py-2 rounded-md border text-xs transition-all text-right ${
                    active
                      ? "border-gold/50 bg-gold-soft"
                      : "border-border bg-background hover:border-border-strong"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-base">{s.emoji}</span>
                    <div className="min-w-0">
                      <div className="font-semibold text-foreground truncate">{s.label}</div>
                      <div className="text-[10px] text-muted-foreground truncate">{s.short}</div>
                    </div>
                  </div>
                  <div className="tabular-nums text-gold font-bold whitespace-nowrap">
                    {price.toLocaleString("ar")} د.أ
                  </div>
                </button>
              );
            })}
          </div>
          {serviceKey && (
            <div className="mt-2 text-[10px] text-muted-foreground leading-5">
              📦 {SERVICE_BY_KEY[serviceKey].deliverables.join(" • ")}
              <br />⏱️ {SERVICE_BY_KEY[serviceKey].duration}
            </div>
          )}
        </div>

        {/* Tags */}
        <div>
          <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
            <Tag className="w-3 h-3" /> الوسوم
          </div>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {(state.tags ?? []).map((t) => (
              <span key={t} className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full bg-emerald-soft border border-emerald/30 text-emerald">
                {t}
                <button onClick={() => onRemoveTag(t)} className="hover:text-foreground">
                  <X className="w-2.5 h-2.5" />
                </button>
              </span>
            ))}
          </div>
          <div className="flex gap-1.5">
            <input
              value={tagInput}
              onChange={(e) => setTagInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTagSubmit())}
              placeholder="وسم جديد..."
              className="flex-1 px-3 py-1.5 rounded-md bg-background border border-border text-xs focus:border-gold/50 outline-none"
            />
            <button onClick={addTagSubmit} className="px-2 rounded-md border border-border hover:border-gold/50">
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Follow-up date */}
        <div>
          <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
            <Calendar className="w-3 h-3" /> تذكير للمتابعة
          </div>
          <div className="flex gap-2">
            <input
              type="date"
              value={state.followUp ?? ""}
              onChange={(e) => onUpdate({ followUp: e.target.value || undefined })}
              className="flex-1 px-3 py-2 rounded-md bg-background border border-border text-sm text-foreground focus:border-gold/50 outline-none"
            />
            {state.followUp && (
              <button onClick={() => onUpdate({ followUp: undefined })} className="px-3 rounded-md border border-border text-xs text-muted-foreground hover:text-foreground">
                إزالة
              </button>
            )}
          </div>
        </div>

        {/* Deal value */}
        <div>
          <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
            <DollarSign className="w-3 h-3 text-gold" /> قيمة الصفقة المتوقعة ({settings.currency})
          </div>
          <input
            type="number"
            min={0}
            value={state.dealValue ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              onUpdate({ dealValue: v === "" ? undefined : Math.max(0, Number(v)) });
            }}
            placeholder="مثال: 1200"
            className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm text-foreground focus:border-gold/50 outline-none tabular-nums"
          />
          <div className="text-[10px] text-muted-foreground mt-1">
            تُحتسب ضمن الإيرادات عند تحويل الحالة إلى "اجتماع".
          </div>
        </div>

        {/* Notes */}
        <div>
          <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
            <StickyNote className="w-3 h-3" /> ملاحظات داخلية
          </div>
          <textarea
            value={state.notes ?? ""}
            onChange={(e) => onUpdate({ notes: e.target.value })}
            placeholder="مثال: تواصلنا مع المدير أحمد، يفضّل الواتساب مساءً..."
            rows={3}
            className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm text-foreground focus:border-gold/50 outline-none resize-none"
          />
        </div>

        {/* Message generator with tabs */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="text-[11px] tracking-widest uppercase text-muted-foreground">المحتوى الجاهز</div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => { setVariantNonce((n) => n + 1); toast.push("تم توليد صيغة جديدة"); }}
                title="توليد صيغة مختلفة للرسالة — كل نسخة تختلف قليلاً حتى لا تبدو آلية"
                className="text-[11px] inline-flex items-center gap-1 text-muted-foreground hover:text-gold"
              >
                <Shuffle className="w-3 h-3" /> صيغة أخرى
              </button>
              <button onClick={copy} className="text-[11px] inline-flex items-center gap-1 text-muted-foreground hover:text-gold">
                {copied ? <><CheckCircle2 className="w-3 h-3 text-emerald" /> نُسخت</> : <><Copy className="w-3 h-3" /> نسخ</>}
              </button>
            </div>
          </div>


          <div className="flex gap-1 mb-2 bg-surface-2 p-1 rounded-md">
            <TabBtn active={tab === "whatsapp"} onClick={() => setTab("whatsapp")}>
              <MessageCircle className="w-3.5 h-3.5" /> واتساب
            </TabBtn>
            <TabBtn active={tab === "email"} onClick={() => setTab("email")}>
              <Mail className="w-3.5 h-3.5" /> إيميل
            </TabBtn>
            <TabBtn active={tab === "proposal"} onClick={() => setTab("proposal")}>
              <FileText className="w-3.5 h-3.5" /> عرض سعر
            </TabBtn>
          </div>

          {tab === "email" && (
            <div className="mb-2 px-3 py-2 rounded-md bg-surface-2 border border-border">
              <div className="text-[10px] uppercase text-muted-foreground tracking-widest">العنوان</div>
              <div className="text-xs text-foreground mt-0.5">{messages!.email.subject}</div>
            </div>
          )}

          {tab === "proposal" && (
            <div className="mb-2 p-2 rounded-md bg-surface-2 border border-border">
              <div className="text-[10px] uppercase text-muted-foreground tracking-widest mb-1.5">
                اختر الباقات للعرض
              </div>
              <div className="flex flex-wrap gap-1">
                {SERVICES.map((s) => {
                  const active = proposalServices.has(s.key);
                  return (
                    <button
                      key={s.key}
                      onClick={() => toggleProposalService(s.key)}
                      className={`text-[10px] px-2 py-1 rounded-full border ${
                        active ? "bg-gold text-primary-foreground border-gold font-semibold" : "border-border text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {s.emoji} {s.short}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="rounded-md bg-background border border-border p-3 text-xs leading-7 text-foreground/90 whitespace-pre-wrap max-h-72 overflow-y-auto scrollbar-thin">
            {currentMsg}
          </div>
        </div>

        {/* History */}
        {state.history && state.history.length > 0 && (
          <div>
            <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
              <History className="w-3 h-3" /> سجل النشاط
            </div>
            <div className="space-y-1.5">
              {[...state.history].slice(-5).reverse().map((h, i) => (
                <div key={i} className="flex items-center justify-between text-[11px] px-3 py-1.5 rounded bg-surface-2/50 border border-border">
                  <span className="flex items-center gap-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${STATUS_META[h.status].dot}`} />
                    {STATUS_META[h.status].label}
                  </span>
                  <span className="text-muted-foreground tabular-nums">
                    {new Date(h.at).toLocaleString("ar-JO", { dateStyle: "short", timeStyle: "short" })}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
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
        <div className="grid grid-cols-3 gap-2">
          <button onClick={sendEmail} className="inline-flex items-center justify-center gap-1.5 py-2 rounded-md bg-accent text-foreground text-xs hover:bg-accent/70">
            <Mail className="w-3.5 h-3.5" /> إيميل
          </button>
          <button
            onClick={() => openPrintableProposal(restaurant, [...proposalServices], settings)}
            className="inline-flex items-center justify-center gap-1.5 py-2 rounded-md bg-accent text-foreground text-xs hover:bg-accent/70"
            title="عرض سعر للطباعة/PDF"
          >
            <Printer className="w-3.5 h-3.5" /> طباعة
          </button>
          <button
            onClick={() => { onStatusChange("meeting"); toast.push("🎉 تم تسجيل اجتماع"); }}
            className="inline-flex items-center justify-center gap-1.5 py-2 rounded-md bg-gold text-primary-foreground text-xs font-semibold hover:opacity-90"
          >
            <Calendar className="w-3.5 h-3.5" /> اجتماع
          </button>
        </div>
      </div>
    </aside>
  );
}

function InfoRow({ icon, label, children }: { icon: React.ReactNode; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 px-3 py-2 rounded-md bg-surface-2/50 border border-border">
      <div className="flex items-center gap-2 text-muted-foreground text-xs">
        {icon}<span>{label}</span>
      </div>
      <div className="text-sm text-left">{children}</div>
    </div>
  );
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 rounded text-xs transition-all ${
        active ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}
