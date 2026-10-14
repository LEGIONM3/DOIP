import { Link, useRouterState } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import {
  getWorkspaceForRoute,
  getActiveToolForRoute,
  type WorkspaceDefinition,
} from "@/lib/workspaces";
import { useSim } from "@/sim/store";
import { contextStore, useOperationalContext } from "@/sim/contextStore";
import { Sparkles, ArrowRight, ShieldAlert, Cpu, ChevronLeft } from "lucide-react";

export function WorkspaceHeader({
  workspaceOverride,
}: {
  workspaceOverride?: WorkspaceDefinition;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const role = useSim((s) => s.role);
  const selectedEntityId = useOperationalContext((s) => s.selectedEntityId);
  const selectedIncidentId = useOperationalContext((s) => s.selectedIncidentId);
  const activeRunId = useOperationalContext((s) => s.activeRunId);

  const workspace = workspaceOverride || getWorkspaceForRoute(pathname);
  const activeTool = getActiveToolForRoute(pathname);
  const Icon = workspace.icon;

  const visibleTools = workspace.tools.filter((t) => {
    if (t.adminOnly && role !== "admin") return false;
    if (t.plannerOnly && role !== "admin" && role !== "planner") return false;
    return true;
  });

  return (
    <div className="shrink-0 border-b border-border bg-surface/90 px-3 py-2 backdrop-blur-sm">
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        {/* Workspace Identity, Back Navigation & Breadcrumb Hierarchy */}
        <div className="flex items-center gap-2.5">
          {/* Quick In-App Back Navigation Button */}
          <button
            type="button"
            onClick={() => window.history.back()}
            className="flex items-center gap-1 border border-border bg-raised px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:border-primary/60 hover:bg-surface hover:text-foreground transition-colors shrink-0"
            title="Backward page routing (Alt+Left)"
            aria-label="Back to previous page"
          >
            <ChevronLeft className="size-3 text-primary" />
            <span className="font-semibold">BACK</span>
          </button>

          <div className="flex size-7 items-center justify-center border border-border bg-raised text-primary shrink-0">
            <Icon className="size-4" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
              <Link
                to="/"
                className="text-muted-foreground hover:text-foreground transition-colors"
                title="Command Center Home"
              >
                DOIP
              </Link>
              <span className="text-muted-foreground/40">/</span>
              <Link
                to={workspace.defaultRoute}
                data-testid="ws-breadcrumb-hub"
                aria-label={`Go to ${workspace.name} hub`}
                className={cn(
                  "uppercase tracking-wider transition-colors",
                  pathname === workspace.defaultRoute
                    ? "font-bold text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
                title={`Go to ${workspace.name} hub`}
              >
                {workspace.name.toUpperCase()}
              </Link>
              {activeTool && activeTool.to !== workspace.defaultRoute && (
                <>
                  <span className="text-muted-foreground/40">/</span>
                  <span className="font-mono font-bold text-primary">
                    {activeTool.code}
                  </span>
                </>
              )}
              <span className="ml-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground/80">
                {workspace.code} · {visibleTools.length} TOOLS
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground">{workspace.description}</p>
          </div>
        </div>

        {/* Operational Context Badges (if any active entity / incident / run selected) */}
        {(selectedEntityId || selectedIncidentId || activeRunId) && (
          <div className="flex items-center gap-1.5 self-start font-mono text-[10px] md:self-auto">
            <span className="text-muted-foreground">ACTIVE CTX:</span>
            {activeRunId && (
              <span className="border border-border bg-raised px-1.5 py-0.5 text-primary">
                RUN: {activeRunId}
              </span>
            )}
            {selectedEntityId && (
              <span className="border border-border bg-raised px-1.5 py-0.5 text-foreground">
                ENTITY: {selectedEntityId}
              </span>
            )}
            {selectedIncidentId && (
              <span className="border border-sev-high/40 bg-sev-high/10 px-1.5 py-0.5 text-sev-high">
                INCIDENT: {selectedIncidentId}
              </span>
            )}
            <button
              onClick={() => {
                contextStore.selectEntity(null);
                contextStore.selectIncident(null);
                contextStore.selectRun(null);
              }}
              className="text-muted-foreground hover:text-foreground"
              title="Clear active context"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Workspace Secondary Navigation Tabs */}
      <div className="mt-2 flex flex-wrap items-center gap-1 border-t border-border/60 pt-1.5">
        <span className="mr-1 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
          VIEWS:
        </span>
        {visibleTools.map((tool) => {
          const ToolIcon = tool.icon;
          const active = pathname === tool.to;
          return (
            <Link
              key={tool.to}
              to={tool.to}
              className={cn(
                "inline-flex items-center gap-1.5 border px-2 py-1 text-xs transition-colors",
                active
                  ? "border-primary/60 bg-raised font-medium text-primary shadow-sm"
                  : "border-transparent text-muted-foreground hover:border-border hover:bg-raised hover:text-foreground",
              )}
              title={tool.description}
            >
              <ToolIcon className="size-3.5 shrink-0" />
              <span>{tool.shortLabel || tool.label}</span>
              <span className="font-mono text-[9px] opacity-60">{tool.code}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
