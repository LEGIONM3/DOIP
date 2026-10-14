import { useState, useEffect } from "react";
import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import {
  Bell,
  LogOut,
  Search,
  Sparkles,
  ShieldCheck,
  CheckSquare,
  Compass,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  User,
  Sliders,
  HelpCircle,
} from "lucide-react";
import { formatSimClockZ, gridRef } from "@/lib/doip";
import { simStore, useSim } from "@/sim/store";
import { cn } from "@/lib/utils";
import {
  WORKSPACES,
  ROLE_PROFILES,
  getWorkspaceForRoute,
  getAvailableWorkspacesForRole,
  getDefaultRouteForRole,
  type WorkspaceId,
} from "@/lib/workspaces";
import { contextStore, useOperationalContext } from "@/sim/contextStore";
import type { Role } from "@/sim/types";
import { toast } from "sonner";

export function TopBar({
  onOpenPalette,
  onToggleAi,
  aiOpen,
  onOpenShortcuts,
}: {
  onOpenPalette: () => void;
  onToggleAi: () => void;
  aiOpen: boolean;
  onOpenShortcuts?: () => void;
}) {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const tick = useSim((s) => s.world.tick);
  const units = useSim((s) => s.world.units);
  const status = useSim((s) => s.status);
  const speed = useSim((s) => s.speed);
  const role = useSim((s) => s.role);
  const userName = useSim((s) => s.userName);
  const pendingApprovalsCount = useOperationalContext((s) => s.pendingApprovalsCount);

  const [profileOpen, setProfileOpen] = useState(false);
  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);

  const unacked = useSim((s) => Object.values(s.world.alerts).filter((a) => !a.acked).length);
  const critical = useSim(
    (s) =>
      Object.values(s.world.alerts).filter((a) => !a.acked && a.severity === "critical").length,
  );

  const currentWorkspace = getWorkspaceForRoute(pathname);

  const statusColor =
    status === "RUNNING"
      ? "text-success"
      : status === "PAUSED"
        ? "text-sev-medium"
        : status === "REPLAY"
          ? "text-primary"
          : "text-muted-foreground";

  const list = Object.values(units);
  const center = list.length
    ? {
        lat: list.reduce((a, u) => a + u.lat, 0) / list.length,
        lon: list.reduce((a, u) => a + u.lon, 0) / list.length,
      }
    : null;

  // Click outside and Escape handling for topbar dropdowns
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target?.closest("[data-topbar-menu]")) {
        setWorkspaceMenuOpen(false);
        setProfileOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setWorkspaceMenuOpen(false);
        setProfileOpen(false);
      }
    };
    window.addEventListener("mousedown", handleOutsideClick);
    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("mousedown", handleOutsideClick);
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  const handleRoleSwitch = (newRole: Role) => {
    const profile = ROLE_PROFILES[newRole];
    simStore.login(newRole, profile.name);
    setProfileOpen(false);
    toast.info(`Switched to ${profile.role.toUpperCase()} profile`, {
      description: `${profile.name} (${profile.callsign}) · ${profile.blurb}`,
    });
    // Check if current workspace or tool is accessible for new role
    const allowed = getAvailableWorkspacesForRole(newRole);
    const wsAllowed = allowed.some((ws) => ws.id === currentWorkspace.id);
    if (!wsAllowed || pathname === "/admin" || pathname === "/models") {
      const landingRoute = getDefaultRouteForRole(newRole);
      void navigate({ to: landingRoute });
    }
  };

  return (
    <header className="flex h-10 shrink-0 items-center justify-between border-b border-border bg-surface px-3">
      {/* Left Section: Backward/Forward Navigation, Workspace, Telemetry */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Backward & Forward Page Routing Controls */}
        <div className="flex items-center border border-border bg-raised">
          <button
            type="button"
            onClick={() => window.history.back()}
            className="flex size-7 items-center justify-center text-muted-foreground transition-colors hover:bg-surface hover:text-foreground active:scale-95"
            title="Go back to previous page (Alt+Left)"
            aria-label="Back"
          >
            <ChevronLeft className="size-3.5" />
          </button>
          <div className="h-4 w-px bg-border/60" />
          <button
            type="button"
            onClick={() => window.history.forward()}
            className="flex size-7 items-center justify-center text-muted-foreground transition-colors hover:bg-surface hover:text-foreground active:scale-95"
            title="Go forward to next page (Alt+Right)"
            aria-label="Forward"
          >
            <ChevronRight className="size-3.5" />
          </button>
        </div>

        {/* Workspace Breadcrumb & Switcher */}
        <div className="relative" data-topbar-menu>
          <button
            onClick={() => setWorkspaceMenuOpen((v) => !v)}
            className="flex items-center gap-1.5 border border-border bg-raised px-2 py-1 font-mono text-xs text-foreground transition-colors hover:border-primary/60"
            title="Switch Workspace"
          >
            <currentWorkspace.icon className="size-3.5 text-primary" />
            <span className="font-semibold uppercase tracking-wider">
              {currentWorkspace.shortName}
            </span>
            <ChevronDown className="size-3 text-muted-foreground" />
          </button>

          {workspaceMenuOpen && (
            <div
              className="absolute left-0 top-full z-50 mt-1 w-56 border border-border bg-surface p-1 shadow-2xl"
              onMouseLeave={() => setWorkspaceMenuOpen(false)}
            >
              <div className="px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                Primary Workspaces
              </div>
              {WORKSPACES.map((ws) => {
                const WsIcon = ws.icon;
                const isSelected = ws.id === currentWorkspace.id;
                return (
                  <Link
                    key={ws.id}
                    to={ws.defaultRoute}
                    onClick={() => setWorkspaceMenuOpen(false)}
                    className={cn(
                      "flex items-center gap-2 px-2 py-1.5 text-xs transition-colors",
                      isSelected
                        ? "bg-raised font-medium text-primary"
                        : "text-muted-foreground hover:bg-raised hover:text-foreground",
                    )}
                  >
                    <WsIcon className="size-3.5 text-primary" />
                    <span>{ws.name}</span>
                    <span className="ml-auto font-mono text-[9px] text-muted-foreground/60">
                      {ws.code}
                    </span>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Zulu Sim Clock */}
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="text-muted-foreground">SIM</span>
          <span className="tabular-nums font-semibold text-foreground">{formatSimClockZ(tick)}</span>
        </div>

        {/* Tactical Grid Ref */}
        <div
          className="hidden items-center gap-2 font-mono text-xs md:flex"
          title="Grid reference of map center"
        >
          <span className="text-muted-foreground">GRID</span>
          <span className="tabular-nums text-muted-foreground">
            {center ? gridRef(center.lat, center.lon) : "—— ———— ————"}
          </span>
        </div>

        {/* Engine Status */}
        <div className={cn("hidden items-center gap-1.5 font-mono text-xs sm:flex", statusColor)}>
          <span className="size-1.5 rounded-full bg-current" />
          <span>{status}</span>
        </div>

        {/* Sim Speed Selector */}
        <div className="hidden items-center gap-1 font-mono text-[11px] lg:flex">
          {[0.5, 1, 2, 4, 8].map((s) => (
            <button
              key={s}
              onClick={() => {
                simStore.setSpeed(s);
                toast.success(`Speed set to ${s}x`);
              }}
              className={cn(
                "px-1 py-0.5 transition-colors",
                speed === s
                  ? "bg-primary text-primary-foreground font-bold"
                  : "text-muted-foreground hover:bg-raised hover:text-foreground",
              )}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>

      {/* Right Section: Indicators, Global Palette, Profile, AI Drawer */}
      <div className="flex items-center gap-2">
        {/* Pending Approvals (HITL Gate Indicator) */}
        {pendingApprovalsCount > 0 && (
          <Link
            to="/workflows"
            className="flex items-center gap-1 border border-purple-500/50 bg-purple-950/40 px-2 py-0.5 font-mono text-xs text-purple-300 transition-colors hover:bg-purple-900/50"
            title="Pending Human-in-the-Loop workflow authorization gates"
          >
            <ShieldCheck className="size-3.5 text-purple-400" />
            <span>{pendingApprovalsCount} PENDING HITL</span>
          </Link>
        )}

        {/* Unacknowledged Alerts Pill */}
        {unacked > 0 && (
          <Link
            to="/dashboard"
            className={cn(
              "flex items-center gap-1 border px-2 py-0.5 font-mono text-xs transition-colors",
              critical > 0
                ? "border-sev-critical/60 bg-sev-critical/10 text-sev-critical animate-pulse"
                : "border-sev-medium/60 bg-sev-medium/10 text-sev-medium",
            )}
            title={`${unacked} unacknowledged alerts (${critical} critical)`}
          >
            <Bell className="size-3" />
            <span>{unacked} ALERTS</span>
          </Link>
        )}

        {/* Command Palette Trigger */}
        <button
          onClick={onOpenPalette}
          className="flex items-center gap-1 border border-border bg-raised px-2 py-1 font-mono text-xs text-muted-foreground hover:text-foreground"
          title="Command Palette (Ctrl+K or /)"
        >
          <Search className="size-3.5" />
          <span className="hidden sm:inline">PALETTE</span>
          <kbd className="hidden sm:inline text-[9px] opacity-60">⌘K</kbd>
        </button>

        {/* Keyboard Shortcuts Trigger */}
        {onOpenShortcuts && (
          <button
            onClick={onOpenShortcuts}
            className="flex size-7 items-center justify-center border border-border bg-raised text-muted-foreground hover:text-foreground"
            title="Keyboard Shortcuts (?)"
          >
            <HelpCircle className="size-3.5" />
          </button>
        )}

        {/* Profile & Role Management Menu */}
        <div className="relative" data-topbar-menu>
          <button
            onClick={() => setProfileOpen((o) => !o)}
            className="flex items-center gap-1.5 border border-border bg-raised px-2 py-1 font-mono text-xs text-foreground hover:border-primary/60"
            title="Operator Profile & Role Settings"
          >
            <User className="size-3.5 text-primary" />
            <span className="hidden md:inline font-semibold">{userName || role}</span>
            <span className="text-[10px] uppercase text-muted-foreground">({role})</span>
            <ChevronDown className="size-3 text-muted-foreground" />
          </button>

          {profileOpen && (
            <div
              className="absolute right-0 top-full z-50 mt-1 w-64 border border-border bg-surface p-2 shadow-2xl"
              onMouseLeave={() => setProfileOpen(false)}
            >
              <div className="border-b border-border pb-1.5 mb-2">
                <div className="font-mono text-xs font-bold text-foreground">
                  {userName || "Active Operator"}
                </div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-primary">
                  ROLE: {role}
                </div>
              </div>

              <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground mb-1">
                Switch Role Profile
              </div>
              <div className="space-y-1">
                {(Object.keys(ROLE_PROFILES) as Role[]).map((r) => {
                  const p = ROLE_PROFILES[r];
                  const isCurrent = role === r;
                  return (
                    <button
                      key={r}
                      onClick={() => handleRoleSwitch(r)}
                      className={cn(
                        "w-full text-left p-1.5 text-xs transition-colors border",
                        isCurrent
                          ? "border-primary/60 bg-raised text-primary"
                          : "border-transparent text-muted-foreground hover:border-border hover:bg-raised hover:text-foreground",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold uppercase">{r}</span>
                        <span className="font-mono text-[9px]">{p.callsign}</span>
                      </div>
                      <div className="text-[10px] text-muted-foreground truncate">{p.name}</div>
                    </button>
                  );
                })}
              </div>

              <div className="border-t border-border mt-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    simStore.logout();
                    setProfileOpen(false);
                    void navigate({ to: "/" });
                  }}
                  className="flex w-full items-center gap-1.5 px-2 py-1 text-xs text-red-400 hover:bg-red-950/40"
                >
                  <LogOut className="size-3.5" />
                  <span>Exit Session (Logout)</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Contextual AI Drawer Trigger */}
        <button
          onClick={onToggleAi}
          className={cn(
            "flex items-center gap-1.5 border px-2 py-1 font-mono text-xs transition-colors",
            aiOpen
              ? "border-purple-500/60 bg-purple-950/50 text-purple-300"
              : "border-border bg-raised text-muted-foreground hover:border-purple-500/50 hover:text-purple-300",
          )}
          title="Contextual AI Copilot Drawer (Cmd+J)"
        >
          <Sparkles className="size-3.5 text-purple-400" />
          <span className="hidden sm:inline">AI COPILOT</span>
        </button>
      </div>
    </header>
  );
}
