import { useState } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  Map,
  LayoutDashboard,
  Play,
  Route as RouteIcon,
  History,
  Sparkles,
  FlaskConical,
  ScanEye,
  Boxes,
  HeartPulse,
  BarChart3,
  Landmark,
  Users,
  Shield,
  FileEdit,
  BookOpen,
  Cpu,
  Network,
  Radio,
  Globe2,
  Bot,
  GitFork,
  Database,
  Brain,
  TrendingUp,
  CheckSquare,
  Activity,
  Sliders,
  ChevronLeft,
  ChevronDown,
  Layers,
  Compass,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  WORKSPACES,
  getWorkspaceForRoute,
  getAvailableWorkspacesForRole,
  type WorkspaceDefinition,
  type WorkspaceId,
} from "@/lib/workspaces";

export interface NavItem {
  to: string;
  label: string;
  code: string;
  icon: React.ComponentType<{ className?: string }>;
  adminOnly?: boolean;
  plannerOnly?: boolean;
}

// Retain legacy NAV_ITEMS export for full backwards compatibility
export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Live Map", code: "S3", icon: Map },
  { to: "/dashboard", label: "Dashboard", code: "S2", icon: LayoutDashboard },
  { to: "/run", label: "Run Control", code: "S4", icon: Play },
  { to: "/planner", label: "Mission Planner", code: "S5", icon: RouteIcon },
  { to: "/federation", label: "Federated Mesh", code: "S20", icon: Radio },
  { to: "/theaters", label: "Multi-Theater", code: "S21", icon: Globe2 },
  { to: "/campaigns", label: "Campaign Swarm", code: "S22", icon: Bot },
  { to: "/futures", label: "Future Explorer", code: "S23", icon: GitFork },
  { to: "/datalake", label: "Data Lake & Bus", code: "S24", icon: Database },
  { to: "/doctrine", label: "Doctrine & SOPs", code: "S17", icon: BookOpen },
  { to: "/replay", label: "Replay", code: "S6", icon: History },
  { to: "/sitrep", label: "AI Sitrep", code: "S7", icon: Sparkles },
  { to: "/forecast", label: "Digital Twin", code: "S18", icon: Cpu },
  { to: "/graph", label: "Knowledge Graph", code: "S19", icon: Network },
  { to: "/whatif", label: "What-If Theater", code: "S8", icon: FlaskConical },
  { to: "/vision", label: "Vision Review", code: "S9", icon: ScanEye },
  { to: "/logistics", label: "Logistics", code: "S10", icon: Boxes },
  { to: "/personnel", label: "Personnel", code: "S11", icon: HeartPulse },
  { to: "/analytics", label: "Analytics", code: "S12", icon: BarChart3 },
  { to: "/advisor", label: "Investment Advisor", code: "S13", icon: Landmark },
  { to: "/warroom", label: "War-Room", code: "S14", icon: Users },
  { to: "/agents", label: "Agent Runtime", code: "S25", icon: Bot },
  { to: "/memory", label: "Memory Store", code: "S26", icon: Brain },
  { to: "/analytics-center", label: "Analytics Center", code: "S27", icon: TrendingUp },
  { to: "/workflows", label: "Workflows & Gates", code: "S28", icon: CheckSquare },
  { to: "/models", label: "Model Governance", code: "S29", icon: Cpu },
  { to: "/observability", label: "Observability", code: "S30", icon: Activity },
  { to: "/model-lab", label: "Model Lab", code: "S31", icon: Sliders },
  { to: "/scenario-editor", label: "Scenario Editor", code: "S16", icon: FileEdit, plannerOnly: true },
  { to: "/admin", label: "Admin", code: "S15", icon: Shield, adminOnly: true },
];

export function SideNav({
  collapsed,
  onToggle,
  role,
}: {
  collapsed: boolean;
  onToggle: () => void;
  role: string | null;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [flatView, setFlatView] = useState(false);
  const [expandedWs, setExpandedWs] = useState<Record<WorkspaceId, boolean>>({
    command: true,
    simulation: true,
    intelligence: true,
    readiness: true,
    collaboration: true,
    analytics: true,
    governance: true,
  });

  const activeWorkspace = getWorkspaceForRoute(pathname);
  const availableWorkspaces = getAvailableWorkspacesForRole(role as any);

  const toggleWorkspace = (id: WorkspaceId) => {
    setExpandedWs((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const flatItems = NAV_ITEMS.filter(
    (i) =>
      (!i.adminOnly || role === "admin") &&
      (!i.plannerOnly || role === "admin" || role === "planner"),
  );

  return (
    <nav
      className={cn(
        "flex shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-200 select-none",
        collapsed ? "w-14" : "w-64",
      )}
      aria-label="Primary"
    >
      {/* Brand Header */}
      <div className="flex h-11 items-center justify-between border-b border-border px-3">
        <div className="flex items-center gap-2 overflow-hidden">
          <span className="font-mono text-sm font-bold tracking-[0.2em] text-primary">DOIP</span>
          {!collapsed && (
            <span className="truncate text-[10px] uppercase tracking-widest text-muted-foreground">
              Command Suite
            </span>
          )}
        </div>
        {!collapsed && role && (
          <span className="font-mono text-[9px] uppercase px-1.5 py-0.5 border border-border bg-raised text-primary">
            {role}
          </span>
        )}
      </div>

      {/* Mode Switcher (Workspaces vs Flat List) */}
      {!collapsed && (
        <div className="flex items-center justify-between border-b border-border/70 px-3 py-1.5 bg-background/50">
          <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
            {flatView ? "FLAT TOOL LIST" : "7 WORKSPACES"}
          </span>
          <button
            onClick={() => setFlatView((f) => !f)}
            className="font-mono text-[9px] text-primary hover:underline"
            title="Toggle workspace grouping vs flat tool listing"
          >
            {flatView ? "Group by Workspace" : "View All (31)"}
          </button>
        </div>
      )}

      {/* Main Navigation List */}
      <div className="flex-1 overflow-y-auto p-2">
        {flatView && !collapsed ? (
          // Legacy Flat List Mode
          <ul className="space-y-0.5">
            {flatItems.map((item) => {
              const active = pathname === item.to;
              const Icon = item.icon;
              return (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    title={item.label}
                    className={cn(
                      "flex items-center gap-2 px-2 py-1.5 text-xs transition-colors",
                      active
                        ? "bg-raised font-medium text-primary border-l-2 border-primary"
                        : "text-muted-foreground hover:bg-raised hover:text-foreground",
                    )}
                  >
                    <Icon className="size-4 shrink-0" />
                    <span className="truncate">{item.label}</span>
                    <span className="ml-auto font-mono text-[9px] text-muted-foreground/60">
                      {item.code}
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        ) : (
          // Seven Primary Workspaces Mode
          <div className="space-y-2">
            {availableWorkspaces.map((ws) => {
              const WsIcon = ws.icon;
              const isCurrentWs = activeWorkspace.id === ws.id;
              const isExpanded = expandedWs[ws.id] ?? true;

              if (collapsed) {
                // Collapsed Icon View
                return (
                  <Link
                    key={ws.id}
                    to={ws.defaultRoute}
                    title={`${ws.name} (${ws.tools.length} tools)`}
                    className={cn(
                      "flex size-10 items-center justify-center border mx-auto transition-colors",
                      isCurrentWs
                        ? "border-primary/70 bg-raised text-primary"
                        : "border-transparent text-muted-foreground hover:border-border hover:bg-raised hover:text-foreground",
                    )}
                  >
                    <WsIcon className="size-5 shrink-0" />
                  </Link>
                );
              }

              // Expanded Workspace Group View
              return (
                <div key={ws.id} className="rounded-none border border-border/40 bg-surface/40">
                  {/* Workspace Group Header */}
                  <div
                    role="button"
                    tabIndex={0}
                    aria-expanded={isExpanded}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggleWorkspace(ws.id);
                      }
                    }}
                    className={cn(
                      "flex items-center justify-between px-2.5 py-1.5 transition-colors cursor-pointer select-none",
                      isCurrentWs
                        ? "bg-raised/80 text-foreground border-l-2 border-primary"
                        : "text-muted-foreground hover:bg-raised/40 hover:text-foreground",
                    )}
                    onClick={() => toggleWorkspace(ws.id)}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <WsIcon className="size-4 shrink-0 text-primary" />
                      <span className="font-mono text-xs font-semibold tracking-wider truncate">
                        {ws.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span className="font-mono text-[9px] text-muted-foreground/70">
                        {ws.tools.length}
                      </span>
                      <ChevronDown
                        className={cn(
                          "size-3 text-muted-foreground transition-transform duration-150",
                          !isExpanded && "-rotate-90",
                        )}
                      />
                    </div>
                  </div>

                  {/* Workspace Member Tools */}
                  {isExpanded && (
                    <ul className="py-1 pl-4 pr-1 space-y-0.5 border-t border-border/30 bg-background/20">
                      {ws.tools.map((tool) => {
                        const ToolIcon = tool.icon;
                        const active = pathname === tool.to;
                        return (
                          <li key={tool.to}>
                            <Link
                              to={tool.to}
                              className={cn(
                                "flex items-center gap-2 px-2 py-1 text-xs transition-colors",
                                active
                                  ? "bg-raised font-medium text-primary border-l border-primary"
                                  : "text-muted-foreground hover:bg-raised hover:text-foreground",
                              )}
                              title={tool.description}
                            >
                              <ToolIcon className="size-3.5 shrink-0" />
                              <span className="truncate">{tool.shortLabel || tool.label}</span>
                              <span className="ml-auto font-mono text-[9px] text-muted-foreground/60">
                                {tool.code}
                              </span>
                            </Link>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Collapse / Expand Toggle */}
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-2 border-t border-border px-3 py-2 text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground cursor-pointer"
      >
        <ChevronLeft className={cn("size-4 transition-transform", collapsed && "rotate-180")} />
        {!collapsed && "Collapse Sidebar"}
      </button>
    </nav>
  );
}
