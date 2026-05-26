import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type ToastTone = "success" | "info" | "error";
interface Toast {
  id: number;
  message: string;
  tone: ToastTone;
}

const ToastCtx = createContext<{ push: (msg: string, tone?: ToastTone) => void }>({
  push: () => {},
});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const push = useCallback((message: string, tone: ToastTone = "success") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, message, tone }]);
    setTimeout(() => {
      setItems((s) => s.filter((t) => t.id !== id));
    }, 2600);
  }, []);

  return (
    <ToastCtx.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-5 left-5 z-50 flex flex-col gap-2 pointer-events-none">
        {items.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto px-4 py-2.5 rounded-lg border text-sm shadow-2xl backdrop-blur-md animate-in slide-in-from-bottom-2 fade-in ${
              t.tone === "success"
                ? "bg-emerald-soft border-emerald/40 text-emerald"
                : t.tone === "error"
                ? "bg-destructive/20 border-destructive/40 text-destructive-foreground"
                : "bg-gold-soft border-gold/40 text-gold"
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast() {
  return useContext(ToastCtx);
}
