import { Link, useLocation } from "@tanstack/react-router";
import { LayoutDashboard, BarChart3, Bell, CalendarClock, Settings as SettingsIcon } from "lucide-react";

interface Props {
  followUpsCount: number;
  overdueCount: number;
  onOpenFollowUps: () => void;
  onOpenCommand: () => void;
  onOpenSettings: () => void;
}

export function TopNav({ followUpsCount, overdueCount, onOpenFollowUps, onOpenCommand, onOpenSettings }: Props) {
  const loc = useLocation();
  const path = loc.pathname;

  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-full bg-card border border-border">
      <NavLink to="/" active={path === "/"} icon={<LayoutDashboard className="w-3.5 h-3.5" />}>
        لوحة التواصل
      </NavLink>
      <NavLink to="/insights" active={path.startsWith("/insights")} icon={<BarChart3 className="w-3.5 h-3.5" />}>
        التحليلات
      </NavLink>
      <div className="w-px h-5 bg-border mx-1" />
      <button
        onClick={onOpenCommand}
        className="inline-flex items-center gap-2 text-[11px] text-muted-foreground hover:text-foreground px-2 py-1.5 rounded-full"
        title="بحث سريع (Ctrl+K)"
      >
        <kbd className="px-1.5 py-0.5 rounded bg-surface-2 border border-border text-[10px]">⌘K</kbd>
        بحث سريع
      </button>
      <button
        onClick={onOpenFollowUps}
        className="relative inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full hover:bg-accent text-foreground"
        title="المتابعات"
      >
        {overdueCount > 0 ? <Bell className="w-4 h-4 text-destructive animate-pulse" /> : <CalendarClock className="w-4 h-4 text-gold" />}
        {followUpsCount > 0 && (
          <span className={`text-[10px] font-bold tabular-nums px-1.5 rounded-full ${
            overdueCount > 0 ? "bg-destructive text-destructive-foreground" : "bg-gold text-primary-foreground"
          }`}>
            {followUpsCount}
          </span>
        )}
      </button>
      <button
        onClick={onOpenSettings}
        title="الإعدادات"
        className="inline-flex items-center justify-center w-8 h-8 rounded-full hover:bg-accent text-muted-foreground hover:text-gold"
      >
        <SettingsIcon className="w-4 h-4" />
      </button>
    </div>
  );
}

function NavLink({
  to, active, icon, children,
}: { to: string; active: boolean; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className={`inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition-all ${
        active ? "bg-gold text-primary-foreground font-semibold" : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {icon}
      {children}
    </Link>
  );
}
