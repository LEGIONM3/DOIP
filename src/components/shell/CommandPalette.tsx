import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import { simStore, useSim } from "@/sim/store";
import { contextStore } from "@/sim/contextStore";
import { canOperate } from "@/lib/doip";
import { WORKSPACES, ROLE_PROFILES, type WorkspaceId } from "@/lib/workspaces";
import type { Role } from "@/sim/types";
import { toast } from "sonner";
import {
  Compass,
  Play,
  Sparkles,
  Boxes,
  Users,
  Activity,
  Shield,
  UserCheck,
} from "lucide-react";

export function CommandPalette({
  open,
  setOpen,
}: {
  open: boolean;
  setOpen: (v: boolean) => void;
  onSelectWorkspace?: (ws: WorkspaceId) => void;
}) {
  const navigate = useNavigate();
  const role = useSim((s) => s.role);
  const userName = useSim((s) => s.userName);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (e.key === "/" && !typing) {
        e.preventDefault();
        setOpen(true);
      }
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  const go = (to: string) => {
    setOpen(false);
    void navigate({ to });
  };

  const switchWorkspace = (ws: WorkspaceId, route: string) => {
    setOpen(false);
    contextStore.setWorkspace(ws);
    void navigate({ to: route });
    toast.info(`Switched to ${ws.toUpperCase()} workspace`);
  };

  const act = (label: string, fn: () => void, needsOperator = true) => {
    setOpen(false);
    if (needsOperator && !canOperate(role)) {
      toast.error("Read-only role", { description: `${label} requires operator access or above.` });
      return;
    }
    fn();
    toast.success(label);
  };

  const switchRole = (newRole: Role) => {
    setOpen(false);
    const profile = ROLE_PROFILES[newRole];
    simStore.login(newRole, profile.name);
    toast.info(`Role switched to ${newRole.toUpperCase()}`);
    void navigate({ to: profile.defaultRoute });
  };

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search tools, switch workspace, or run tactical command…" />
      <CommandList>
        <CommandEmpty>No matching workspace, tool, or command.</CommandEmpty>

        {/* 1. Primary Workspaces */}
        <CommandGroup heading="Seven Primary Workspaces">
          {WORKSPACES.filter((ws) => !ws.adminOnly || role === "admin").map((ws) => {
            const Icon = ws.icon;
            return (
              <CommandItem
                key={ws.id}
                value={`workspace ${ws.name} ${ws.code} ${ws.shortName}`}
                onSelect={() => switchWorkspace(ws.id, ws.defaultRoute)}
              >
                <Icon className="size-4 text-primary" />
                <span className="font-medium">{ws.name}</span>
                <span className="ml-auto font-mono text-[9px] text-muted-foreground">{ws.code}</span>
              </CommandItem>
            );
          })}
        </CommandGroup>

        <CommandSeparator />

        {/* 2. Tools Grouped by Workspace */}
        {WORKSPACES.filter((ws) => !ws.adminOnly || role === "admin").map((ws) => {
          const visibleTools = ws.tools.filter((t) => {
            if (t.adminOnly && role !== "admin") return false;
            if (t.plannerOnly && role !== "admin" && role !== "planner") return false;
            return true;
          });

          return (
            <CommandGroup key={ws.id} heading={ws.name}>
              {visibleTools.map((tool) => {
                const Icon = tool.icon;
                return (
                  <CommandItem
                    key={tool.to}
                    value={`${tool.label} ${tool.code} ${ws.name} ${tool.shortLabel}`}
                    onSelect={() => go(tool.to)}
                  >
                    <Icon className="size-4" />
                    <span>{tool.label}</span>
                    <span className="ml-auto font-mono text-[9px] text-muted-foreground">
                      {tool.code}
                    </span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          );
        })}

        <CommandSeparator />

        {/* 3. Run Control Actions */}
        <CommandGroup heading="Simulation Controls">
          <CommandItem value="pause simulation" onSelect={() => act("Run paused", () => simStore.pause())}>
            Pause deterministic simulation
          </CommandItem>
          <CommandItem
            value="resume simulation"
            onSelect={() => act("Run resumed", () => simStore.resume())}
          >
            Resume simulation
          </CommandItem>
          <CommandItem value="stop simulation" onSelect={() => act("Run stopped", () => simStore.stop())}>
            Stop and snapshot simulation
          </CommandItem>
          <CommandItem
            value="acknowledge all alerts"
            onSelect={() =>
              act("All alerts acknowledged", () => {
                const st = simStore.getState();
                Object.values(st.world.alerts)
                  .filter((a) => !a.acked)
                  .forEach((a) => simStore.ackAlert(a.id, userName || "operator"));
              })
            }
          >
            Acknowledge all pending alerts
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        {/* 4. Quick Profile Switching */}
        <CommandGroup heading="Role Profiles (Demo Identity)">
          {(Object.keys(ROLE_PROFILES) as Role[]).map((r) => {
            const p = ROLE_PROFILES[r];
            return (
              <CommandItem
                key={r}
                value={`switch role ${r} ${p.name} ${p.callsign}`}
                onSelect={() => switchRole(r)}
              >
                <UserCheck className="size-4 text-primary" />
                <span>Switch to {r.toUpperCase()} Profile ({p.name})</span>
                <span className="ml-auto font-mono text-[9px] text-muted-foreground">
                  {p.callsign}
                </span>
              </CommandItem>
            );
          })}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
