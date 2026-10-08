import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useLeadActions, useTeamSettings } from "@/hooks/useLeads";
import { useToast } from "@/hooks/useToast";
import { DEFAULT_TEAM, type TeamSettings } from "@/lib/leads";
import { useServerFn } from "@tanstack/react-start";
import { importPortfolio } from "@/lib/ai.functions";

export const Route = createFileRoute("/_authenticated/settings")({
  head: () => ({ meta: [{ title: "FAII — Settings" }] }),
  component: SettingsPage,
});

const FIELDS: [keyof TeamSettings, string, number][] = [
  ["senderName", "اسمك", 1],
  ["senderRole", "صفتك", 1],
  ["company", "اسم الاستوديو", 1],
  ["whoWeAre", "من أنتم (بصدق، بكلامك)", 3],
  ["services", "خدماتكم — سطر لكل خدمة ولمن تناسب", 7],
  ["portfolioSite", "موقعك الذي عليه أعمالك", 1],
  ["portfolio", "البورتفوليو — سطر لكل عمل: العنوان | الرابط | كلمات (ngo, documentary, food, event…)", 10],
  ["priceGuide", "دليل أسعار (اختياري — إن تُرك فارغاً لن يذكر الذكاء أرقاماً)", 2],
  ["focus", "الأولوية", 2],
];

function SettingsPage() {
  const { data } = useTeamSettings();
  const act = useLeadActions();
  const toast = useToast();
  const [s, setS] = useState<TeamSettings>(DEFAULT_TEAM);
  const readSite = useServerFn(importPortfolio);
  const [reading, setReading] = useState(false);
  const pull = async () => {
    setReading(true);
    try {
      const r = await readSite({ data: { url: s.portfolioSite } });
      setS((x) => ({ ...x, portfolio: r.lines }));
      toast.push(`قرأت ${r.pages} صفحة — راجع القائمة ثم احفظ`);
    } catch (e) {
      toast.push((e as Error).message, "error");
    } finally {
      setReading(false);
    }
  };
  useEffect(() => { if (data) setS(data); }, [data]);

  return (
    <div dir="rtl" className="max-w-3xl mx-auto p-4 space-y-3 text-sm">
      <div className="flex justify-between"><b className="text-lg">الإعدادات</b><Link to="/" className="underline">رجوع</Link></div>
      <p className="text-muted-foreground">الذكاء يقرأ هذه المعلومات قبل كل رسالة. كلما كانت حقيقية ودقيقة، كانت الرسائل أقرب لك.</p>
      {FIELDS.map(([k, label, rows]) => (
        <label key={k} className="block space-y-1">
          <span>{label}</span>
          {rows === 1 ? (
            <input className="w-full rounded border border-border bg-background px-2 py-1.5" value={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.value })} />
          ) : (
            <textarea dir={k === "portfolio" ? "ltr" : "rtl"} rows={rows} className="w-full rounded border border-border bg-background px-2 py-1.5" value={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.value })} />
          )}
          {k === "portfolioSite" && (
            <button type="button" disabled={!s.portfolioSite || reading} onClick={pull} className="mt-1 px-3 py-1.5 rounded border border-border disabled:opacity-40">
              {reading ? "يقرأ موقعك…" : "اقرأ أعمالي من الموقع واملأ البورتفوليو"}
            </button>
          )}
        </label>
      ))}
      <button className="px-4 py-2 rounded bg-primary text-primary-foreground" onClick={() => act.saveSettings(s).then(() => toast.push("حُفظ"), (e) => toast.push(e.message, "error"))}>حفظ</button>
    </div>
  );
}
