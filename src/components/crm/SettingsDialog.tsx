import { useState, useEffect } from "react";
import { X, Settings as SettingsIcon, RotateCcw } from "lucide-react";
import { type Settings } from "@/hooks/useSettings";
import { useToast } from "@/hooks/useToast";

interface Props {
  open: boolean;
  onClose: () => void;
  settings: Settings;
  onSave: (patch: Partial<Settings>) => void;
  onReset: () => void;
}

export function SettingsDialog({ open, onClose, settings, onSave, onReset }: Props) {
  const [local, setLocal] = useState<Settings>(settings);
  const toast = useToast();

  useEffect(() => { if (open) setLocal(settings); }, [open, settings]);

  if (!open) return null;

  const save = () => {
    onSave(local);
    toast.push("تم حفظ الإعدادات", "success");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg rounded-2xl bg-card border border-border shadow-2xl"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-gradient-hero rounded-t-2xl">
          <div className="flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-gold" />
            <div>
              <div className="font-bold">إعدادات المُرسل والعروض</div>
              <div className="text-[11px] text-muted-foreground">تُطبَّق تلقائياً على كل الرسائل وعروض الأسعار</div>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-md hover:bg-accent flex items-center justify-center">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-5 space-y-4 max-h-[70vh] overflow-y-auto scrollbar-thin">
          <Field label="اسم المُرسل">
            <input value={local.senderName} onChange={(e) => setLocal({ ...local, senderName: e.target.value })}
              className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm focus:border-gold/50 outline-none" />
          </Field>
          <Field label="المسمى الوظيفي">
            <input value={local.senderRole} onChange={(e) => setLocal({ ...local, senderRole: e.target.value })}
              className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm focus:border-gold/50 outline-none" />
          </Field>
          <Field label="التوقيع (يُذيَّل في الرسائل)">
            <textarea value={local.signature} onChange={(e) => setLocal({ ...local, signature: e.target.value })}
              rows={2}
              className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm focus:border-gold/50 outline-none resize-none" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="نسبة الخصم على العروض (%)">
              <input type="number" min={0} max={50} value={local.discountPct}
                onChange={(e) => setLocal({ ...local, discountPct: Math.max(0, Math.min(50, Number(e.target.value) || 0)) })}
                className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm focus:border-gold/50 outline-none tabular-nums" />
            </Field>
            <Field label="العملة">
              <input value={local.currency} onChange={(e) => setLocal({ ...local, currency: e.target.value })}
                className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm focus:border-gold/50 outline-none" />
            </Field>
          </div>
          <Field label="رابط معرض الأعمال">
            <input value={local.portfolioUrl} onChange={(e) => setLocal({ ...local, portfolioUrl: e.target.value })}
              className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm focus:border-gold/50 outline-none ltr" dir="ltr" />
          </Field>
        </div>

        <div className="px-5 py-4 border-t border-border flex items-center justify-between bg-surface-2/40 rounded-b-2xl">
          <button onClick={() => { onReset(); setLocal({ ...local }); toast.push("أُعيدت الإعدادات الافتراضية", "info"); }}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
            <RotateCcw className="w-3.5 h-3.5" /> الافتراضي
          </button>
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 text-xs rounded-md border border-border hover:bg-accent">
              إلغاء
            </button>
            <button onClick={save} className="px-4 py-2 text-xs rounded-md bg-gold text-primary-foreground font-semibold hover:opacity-90">
              حفظ الإعدادات
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] tracking-widest uppercase text-muted-foreground mb-1.5">{label}</div>
      {children}
    </div>
  );
}
