import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  WORKSPACES,
  ROLE_PROFILES,
  getWorkspaceForRoute,
  getActiveToolForRoute,
  getAvailableWorkspacesForRole,
  getDefaultRouteForRole,
} from "@/lib/workspaces";
import { contextStore } from "@/sim/contextStore";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { SideNav } from "./SideNav";

// Mock TanStack router Link and useRouterState
let currentPathname = "/";
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, className, onClick }: any) => (
    <a
      href={to}
      className={className}
      onClick={(e) => {
        if (onClick) onClick(e);
      }}
    >
      {children}
    </a>
  ),
  useRouterState: ({ select }: any) => {
    return select({ location: { pathname: currentPathname } });
  },
}));

// Mock Sim store
let currentRole = "admin";
vi.mock("@/sim/store", () => ({
  useSim: (selector: any) => {
    const mockState = {
      role: currentRole,
      world: { tick: 100 },
    };
    return selector(mockState);
  },
}));

describe("Unified Command Center Workspaces & Profile System", () => {
  beforeEach(() => {
    currentPathname = "/";
    currentRole = "admin";
  });

  describe("Phase 2 — Seven Primary Workspaces Registry", () => {
    it("defines exactly 7 primary workspaces covering all required operational domains", () => {
      expect(WORKSPACES).toHaveLength(7);

      const workspaceIds = WORKSPACES.map((w) => w.id);
      expect(workspaceIds).toEqual([
        "command",
        "simulation",
        "intelligence",
        "readiness",
        "collaboration",
        "analytics",
        "governance",
      ]);
    });

    it("verifies every workspace has metadata, icons, and non-empty tool arrays", () => {
      WORKSPACES.forEach((ws) => {
        expect(ws.name).toBeTruthy();
        expect(ws.code).toMatch(/^WS[1-7]$/);
        expect(ws.icon).toBeDefined();
        expect(ws.description).toBeTruthy();
        expect(ws.defaultRoute).toBeTruthy();
        expect(ws.tools.length).toBeGreaterThan(0);

        // Every tool must have valid path, label, code, and icon
        ws.tools.forEach((tool) => {
          expect(tool.to).toBeTruthy();
          expect(tool.label).toBeTruthy();
          expect(tool.code).toMatch(/^S\d+$/);
          expect(tool.icon).toBeDefined();
        });
      });
    });

    it("maps operational screens S2 through S31 across the 7 workspaces", () => {
      const allToolCodes = new Set<string>();
      WORKSPACES.forEach((ws) => {
        ws.tools.forEach((t) => allToolCodes.add(t.code));
      });

      // Verify operational screens S2 through S31 are all accounted for (S1 is /login entry)
      for (let i = 2; i <= 31; i++) {
        expect(allToolCodes.has(`S${i}`)).toBe(true);
      }
      expect(allToolCodes.size).toBe(30);
    });
  });

  describe("Phase 4 — Profile-Aware Capabilities & Navigation", () => {
    it("configures Admin role with full access across all 7 workspaces", () => {
      const adminProfile = ROLE_PROFILES.admin;
      expect(adminProfile.role).toBe("admin");
      expect(adminProfile.canOperate).toBe(true);
      expect(adminProfile.canPlan).toBe(true);
      expect(adminProfile.canAdmin).toBe(true);
      expect(adminProfile.canApproveDirectives).toBe(true);
      expect(adminProfile.allowedWorkspaces).toHaveLength(7);
      expect(adminProfile.defaultRoute).toBe("/dashboard");

      const availableWorkspaces = getAvailableWorkspacesForRole("admin");
      expect(availableWorkspaces).toHaveLength(7);
    });

    it("configures Planner role with mission planning and without admin governance", () => {
      const plannerProfile = ROLE_PROFILES.planner;
      expect(plannerProfile.role).toBe("planner");
      expect(plannerProfile.canPlan).toBe(true);
      expect(plannerProfile.canAdmin).toBe(false);
      expect(plannerProfile.defaultRoute).toBe("/planner");
      expect(plannerProfile.allowedWorkspaces).not.toContain("governance");

      const availableWorkspaces = getAvailableWorkspacesForRole("planner");
      expect(availableWorkspaces.some((w) => w.id === "governance")).toBe(false);

      // Verify admin-only tools are filtered out for Planner
      const simWs = availableWorkspaces.find((w) => w.id === "simulation");
      expect(simWs?.tools.some((t) => t.adminOnly)).toBe(false);
    });

    it("configures Operator role with real-time tactical operations and landing on Live Map", () => {
      const operatorProfile = ROLE_PROFILES.operator;
      expect(operatorProfile.role).toBe("operator");
      expect(operatorProfile.canOperate).toBe(true);
      expect(operatorProfile.canPlan).toBe(false);
      expect(operatorProfile.canAdmin).toBe(false);
      expect(operatorProfile.defaultRoute).toBe("/");

      const defaultRoute = getDefaultRouteForRole("operator");
      expect(defaultRoute).toBe("/");
    });

    it("configures Viewer role as read-only observer without state-changing permissions", () => {
      const viewerProfile = ROLE_PROFILES.viewer;
      expect(viewerProfile.role).toBe("viewer");
      expect(viewerProfile.canOperate).toBe(false);
      expect(viewerProfile.canPlan).toBe(false);
      expect(viewerProfile.canAdmin).toBe(false);
      expect(viewerProfile.canApproveDirectives).toBe(false);

      // Verify planner-only and admin-only tools are stripped for viewer
      const availableWorkspaces = getAvailableWorkspacesForRole("viewer");
      availableWorkspaces.forEach((ws) => {
        ws.tools.forEach((tool) => {
          expect(tool.adminOnly).toBeFalsy();
          expect(tool.plannerOnly).toBeFalsy();
        });
      });
    });
  });

  describe("Route Resolution & Stable URLs", () => {
    it("correctly resolves each route to its corresponding parent workspace", () => {
      expect(getWorkspaceForRoute("/").id).toBe("command");
      expect(getWorkspaceForRoute("/dashboard").id).toBe("command");
      expect(getWorkspaceForRoute("/run").id).toBe("simulation");
      expect(getWorkspaceForRoute("/replay").id).toBe("simulation");
      expect(getWorkspaceForRoute("/whatif").id).toBe("simulation");
      expect(getWorkspaceForRoute("/scenario-editor").id).toBe("simulation");
      expect(getWorkspaceForRoute("/sitrep").id).toBe("intelligence");
      expect(getWorkspaceForRoute("/doctrine").id).toBe("intelligence");
      expect(getWorkspaceForRoute("/graph").id).toBe("intelligence");
      expect(getWorkspaceForRoute("/model-lab").id).toBe("intelligence");
      expect(getWorkspaceForRoute("/logistics").id).toBe("readiness");
      expect(getWorkspaceForRoute("/personnel").id).toBe("readiness");
      expect(getWorkspaceForRoute("/warroom").id).toBe("collaboration");
      expect(getWorkspaceForRoute("/workflows").id).toBe("collaboration");
      expect(getWorkspaceForRoute("/analytics").id).toBe("analytics");
      expect(getWorkspaceForRoute("/observability").id).toBe("analytics");
      expect(getWorkspaceForRoute("/admin").id).toBe("governance");
      expect(getWorkspaceForRoute("/models").id).toBe("governance");
    });

    it("falls back safely to Command Center for unmapped paths", () => {
      expect(getWorkspaceForRoute("/unknown-subpath").id).toBe("command");
    });

    it("resolves active tool metadata within a workspace", () => {
      const tool = getActiveToolForRoute("/replay");
      expect(tool).not.toBeNull();
      expect(tool?.label).toBe("Total Replay & Scrub");
      expect(tool?.code).toBe("S6");
    });
  });

  describe("Phase 5 — Cross-Feature Workflow Integration & Context Contracts", () => {
    it("preserves entity and task context when handing off to Mission Planner", () => {
      contextStore.handoffToPlanner({ unitId: "UAV-ALPHA", taskId: "TASK-RECON-99" });
      const state = contextStore.getState();

      expect(state.activeWorkspace).toBe("simulation");
      expect(state.selectedEntityId).toBe("UAV-ALPHA");
      expect(state.selectedTaskId).toBe("TASK-RECON-99");
    });

    it("preserves run ID context when handing off from Run Control to Timeline Replay", () => {
      contextStore.handoffToReplay({ runId: "RUN-TEST-0042" });
      const state = contextStore.getState();

      expect(state.activeWorkspace).toBe("simulation");
      expect(state.activeRunId).toBe("RUN-TEST-0042");
    });

    it("preserves scenario ID and prefill prompt when branching to What-If", () => {
      contextStore.handoffToWhatIf({
        scenarioId: "SCENARIO-EAST-FLANK",
        prompt: "Simulate loss of radar radar-01",
      });
      const state = contextStore.getState();

      expect(state.activeWorkspace).toBe("simulation");
      expect(state.activeScenarioId).toBe("SCENARIO-EAST-FLANK");
      expect(state.aiPrefillPrompt).toBe("Simulate loss of radar radar-01");
    });

    it("triggers AI Drawer with contextual incident prefill", () => {
      contextStore.handoffToAi({
        prompt: "Evaluate fuel critical threshold for Convoy Charlie",
        incidentId: "INC-99",
        entityId: "CONVOY-C",
      });
      const state = contextStore.getState();

      expect(state.aiDrawerOpen).toBe(true);
      expect(state.aiPrefillPrompt).toBe("Evaluate fuel critical threshold for Convoy Charlie");
      expect(state.selectedIncidentId).toBe("INC-99");
      expect(state.selectedEntityId).toBe("CONVOY-C");
    });

    it("links active incident into Causal Knowledge Graph workspace", () => {
      contextStore.handoffToGraph({ incidentId: "INC-887" });
      const state = contextStore.getState();

      expect(state.activeWorkspace).toBe("intelligence");
      expect(state.selectedIncidentId).toBe("INC-887");
    });

    it("manages pending approvals counter and clamps to zero", () => {
      contextStore.setPendingApprovalsCount(3);
      expect(contextStore.getState().pendingApprovalsCount).toBe(3);

      contextStore.decrementPendingApproval();
      expect(contextStore.getState().pendingApprovalsCount).toBe(2);

      contextStore.decrementPendingApproval();
      contextStore.decrementPendingApproval();
      expect(contextStore.getState().pendingApprovalsCount).toBe(0);

      // Decrement below 0 is clamped
      contextStore.decrementPendingApproval();
      expect(contextStore.getState().pendingApprovalsCount).toBe(0);
    });
  });

  describe("UI Shell Components Integration", () => {
    it("renders WorkspaceHeader with workspace identity and secondary tool tabs", () => {
      currentPathname = "/run";
      render(<WorkspaceHeader />);

      // Workspace title
      expect(screen.getByText("SIMULATION & MISSION")).toBeDefined();
      expect(screen.getByText(/Deterministic run execution/i)).toBeDefined();

      // Tool links within simulation workspace
      expect(screen.getByText("Run Control")).toBeDefined();
      expect(screen.getByText("Planner")).toBeDefined();
      expect(screen.getByText("Replay")).toBeDefined();
      expect(screen.getByText("What-If")).toBeDefined();
    });

    it("renders SideNav with 7 workspace groups in full view", () => {
      currentRole = "admin";
      render(<SideNav collapsed={false} onToggle={() => {}} role="admin" />);

      // Check workspace headers
      expect(screen.getByText("Command Center")).toBeDefined();
      expect(screen.getByText("Simulation & Mission")).toBeDefined();
      expect(screen.getByText("Intelligence & AI")).toBeDefined();
      expect(screen.getByText("Resources & Readiness")).toBeDefined();
      expect(screen.getByText("Collaboration & Command")).toBeDefined();
      expect(screen.getByText("Analytics & System Health")).toBeDefined();
      expect(screen.getByText("Administration & Governance")).toBeDefined();
    });
  });
});
