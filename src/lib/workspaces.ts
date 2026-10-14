import type { ComponentType } from "react";
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
  Compass,
  Layers,
} from "lucide-react";
import type { Role } from "@/sim/types";

export type WorkspaceId =
  | "command"
  | "simulation"
  | "intelligence"
  | "readiness"
  | "collaboration"
  | "analytics"
  | "governance";

export interface WorkspaceTool {
  to: string;
  label: string;
  shortLabel?: string;
  code: string;
  icon: ComponentType<{ className?: string }>;
  description: string;
  adminOnly?: boolean;
  plannerOnly?: boolean;
  operatorOnly?: boolean;
}

export interface WorkspaceDefinition {
  id: WorkspaceId;
  name: string;
  shortName: string;
  code: string;
  icon: ComponentType<{ className?: string }>;
  description: string;
  defaultRoute: string;
  adminOnly?: boolean;
  plannerOnly?: boolean;
  tools: WorkspaceTool[];
}

export interface RoleCapabilities {
  role: Role;
  name: string;
  callsign: string;
  blurb: string;
  defaultWorkspace: WorkspaceId;
  defaultRoute: string;
  canOperate: boolean;
  canPlan: boolean;
  canAdmin: boolean;
  canApproveDirectives: boolean;
  canAdjudicateVision: boolean;
  allowedWorkspaces: WorkspaceId[];
}

export const WORKSPACES: WorkspaceDefinition[] = [
  {
    id: "command",
    name: "Command Center",
    shortName: "Command",
    code: "WS1",
    icon: Compass,
    description: "Operational overview, live tactical picture, and camera matrix",
    defaultRoute: "/",
    tools: [
      {
        to: "/",
        label: "Live Tactical Map",
        shortLabel: "Live Map",
        code: "S3",
        icon: Map,
        description: "Real-time synthetic tactical picture with tracks, weather, and ruler",
      },
      {
        to: "/dashboard",
        label: "Operations Dashboard",
        shortLabel: "Dashboard",
        code: "S2",
        icon: LayoutDashboard,
        description: "Composite readiness index (CRHI), module status, and open incidents",
      },
      {
        to: "/vision",
        label: "Surveillance Matrix",
        shortLabel: "Surveillance",
        code: "S9",
        icon: ScanEye,
        description: "YOLOv8 aerial feeds, thermal FLIR palettes, and detection queue",
      },
    ],
  },
  {
    id: "simulation",
    name: "Simulation & Mission",
    shortName: "Sim & Mission",
    code: "WS2",
    icon: Play,
    description: "Deterministic run execution, mission routing, and predictive lookahead",
    defaultRoute: "/planner",
    tools: [
      {
        to: "/planner",
        label: "Mission Planner",
        shortLabel: "Planner",
        code: "S5",
        icon: RouteIcon,
        description: "Grid A* tactical pathfinding across terrain, threat, and weather",
        plannerOnly: true,
      },
      {
        to: "/run",
        label: "Run Control Console",
        shortLabel: "Run Control",
        code: "S4",
        icon: Play,
        description: "PRNG seed control, speed multipliers 0.5-8x, and SHA-256 fingerprint",
      },
      {
        to: "/scenario-editor",
        label: "Scenario DSL Editor",
        shortLabel: "Scenario Editor",
        code: "S16",
        icon: FileEdit,
        description: "Visual authoring of custom inject sequences with schema validation",
        plannerOnly: true,
      },
      {
        to: "/replay",
        label: "Total Replay & Scrub",
        shortLabel: "Replay",
        code: "S6",
        icon: History,
        description: "Tick-by-tick scrubber rendered purely from immutable event logs",
      },
      {
        to: "/whatif",
        label: "What-If Theater",
        shortLabel: "What-If",
        code: "S8",
        icon: FlaskConical,
        description: "Natural language hypothetical branching with Monte Carlo ribbons",
      },
      {
        to: "/futures",
        label: "Future Explorer",
        shortLabel: "Futures",
        code: "S23",
        icon: GitFork,
        description: "Monte Carlo lookahead branching into P10, P50, P90, and WORST risk bands",
      },
      {
        to: "/forecast",
        label: "Digital Twin Forecaster",
        shortLabel: "Forecasting",
        code: "S18",
        icon: Cpu,
        description: "Forward lookahead projecting Point-of-No-Return and comms shadows",
      },
    ],
  },
  {
    id: "intelligence",
    name: "Intelligence & AI",
    shortName: "Intel & AI",
    code: "WS3",
    icon: Sparkles,
    description: "Doctrine RAG, cited situation reports, causal graph, and model evaluation",
    defaultRoute: "/sitrep",
    tools: [
      {
        to: "/sitrep",
        label: "Grounded AI SITREP",
        shortLabel: "AI SITREP",
        code: "S7",
        icon: Sparkles,
        description: "Narrative briefing where every claim cites verified event and doctrine IDs",
      },
      {
        to: "/doctrine",
        label: "Doctrine & SOP Corpus",
        shortLabel: "Doctrine RAG",
        code: "S17",
        icon: BookOpen,
        description: "Searchable corpus of 15 canonical defense policies and SOP manuals",
      },
      {
        to: "/graph",
        label: "Knowledge Graph AI",
        shortLabel: "Knowledge Graph",
        code: "S19",
        icon: Network,
        description: "NetworkX causal attribution, dependency paths, and SPOF analysis",
      },
      {
        to: "/memory",
        label: "Cognitive Memory Store",
        shortLabel: "Memory Store",
        code: "S26",
        icon: Brain,
        description: "3-tier store spanning semantic doctrine, episodic logs, and working memory",
      },
      {
        to: "/agents",
        label: "Unified Agent Runtime",
        shortLabel: "Agent Runtime",
        code: "S25",
        icon: Bot,
        description: "Operational agent lifecycle registry and prioritized task execution queue",
      },
      {
        to: "/model-lab",
        label: "Hybrid Physics & Model Lab",
        shortLabel: "Model Lab",
        code: "S31",
        icon: Sliders,
        description: "ModernBERT Laya decision engine evaluation and calibration sliders",
      },
    ],
  },
  {
    id: "readiness",
    name: "Resources & Readiness",
    shortName: "Readiness",
    code: "WS4",
    icon: Boxes,
    description: "Multi-class supply burndown, soldier biometric vitals, and procurement analysis",
    defaultRoute: "/logistics",
    tools: [
      {
        to: "/logistics",
        label: "Logistics & Sustainment",
        shortLabel: "Logistics",
        code: "S10",
        icon: Boxes,
        description: "Fuel, medkits, rations, and batteries burndown with time-to-empty projection",
      },
      {
        to: "/personnel",
        label: "Personnel Readiness",
        shortLabel: "Personnel",
        code: "S11",
        icon: HeartPulse,
        description: "Biometric vitals board, fatigue tracking, and emergency MEDEVAC dispatch",
      },
      {
        to: "/advisor",
        label: "Investment Advisor",
        shortLabel: "Advisor",
        code: "S13",
        icon: Landmark,
        description: "Knapsack portfolio optimization under budget constraints with Pareto curves",
      },
    ],
  },
  {
    id: "collaboration",
    name: "Collaboration & Command",
    shortName: "Collaboration",
    code: "WS5",
    icon: Users,
    description: "Shared war room, multi-tier federation, theater managers, and approval gates",
    defaultRoute: "/warroom",
    tools: [
      {
        to: "/warroom",
        label: "Collaborative War Room",
        shortLabel: "War Room",
        code: "S14",
        icon: Users,
        description: "Live WebSocket participant cursors, sector-scoped Kanban, and decisions",
      },
      {
        to: "/federation",
        label: "Federated Command Mesh",
        shortLabel: "Federation",
        code: "S20",
        icon: Radio,
        description: "Decentralized multi-tier command hierarchy and directive broadcast",
      },
      {
        to: "/theaters",
        label: "Multi-Theater Digital Twin",
        shortLabel: "Theaters",
        code: "S21",
        icon: Globe2,
        description: "Concurrent isolated simulation worlds with cross-theater readiness analysis",
      },
      {
        to: "/campaigns",
        label: "Strategic Campaign Swarm",
        shortLabel: "Campaign Swarm",
        code: "S22",
        icon: Bot,
        description: "6-agent collaborative planning swarm and comparative campaign retrospectives",
      },
      {
        to: "/workflows",
        label: "Workflows & Approval Gates",
        shortLabel: "Workflows",
        code: "S28",
        icon: CheckSquare,
        description: "Mission state machine governing strike dispatches with mandatory HITL gates",
      },
    ],
  },
  {
    id: "analytics",
    name: "Analytics & System Health",
    shortName: "Analytics",
    code: "WS6",
    icon: Activity,
    description: "Operations metrics, automated reports, OpenTelemetry health, and data lake",
    defaultRoute: "/analytics",
    tools: [
      {
        to: "/analytics",
        label: "Tactical Operations Analytics",
        shortLabel: "Analytics",
        code: "S12",
        icon: BarChart3,
        description: "Event frequency sparklines, incident loss ratios, and MTBF reliability",
      },
      {
        to: "/analytics-center",
        label: "Enterprise Analytics Center",
        shortLabel: "Reporting Center",
        code: "S27",
        icon: TrendingUp,
        description: "Automated Daily SITREPs, AAR document generation, and lookahead risk tensors",
      },
      {
        to: "/observability",
        label: "Enterprise Observability",
        shortLabel: "Observability",
        code: "S30",
        icon: Activity,
        description: "OpenTelemetry latency percentiles (P50/P90/P99) and Prometheus metrics",
      },
      {
        to: "/datalake",
        label: "Data Lake & Event Stream",
        shortLabel: "Data Lake",
        code: "S24",
        icon: Database,
        description: "Kafka ring-buffer bus with offset replay and S3/MinIO object store",
      },
    ],
  },
  {
    id: "governance",
    name: "Administration & Governance",
    shortName: "Admin",
    code: "WS7",
    icon: Shield,
    description: "User management, immutable audit trail, model governance, and settings",
    defaultRoute: "/admin",
    adminOnly: true,
    tools: [
      {
        to: "/admin",
        label: "Administration & Audit Log",
        shortLabel: "Admin & Audit",
        code: "S15",
        icon: Shield,
        description: "User roster sync, scenario/corpus index, and immutable exercise audit trail",
        adminOnly: true,
      },
      {
        to: "/models",
        label: "Model Governance & Router",
        shortLabel: "Model Governance",
        code: "S29",
        icon: Cpu,
        description: "Model registry, dynamic local GPU vs cloud task router, and health probes",
        adminOnly: true,
      },
    ],
  },
];

export const ROLE_PROFILES: Record<Role, RoleCapabilities> = {
  admin: {
    role: "admin",
    name: "Col. A. Verma",
    callsign: "COMMANDER-01",
    blurb: "Full strategic access across all 7 workspaces, user administration, and audit logs.",
    defaultWorkspace: "command",
    defaultRoute: "/dashboard",
    canOperate: true,
    canPlan: true,
    canAdmin: true,
    canApproveDirectives: true,
    canAdjudicateVision: true,
    allowedWorkspaces: [
      "command",
      "simulation",
      "intelligence",
      "readiness",
      "collaboration",
      "analytics",
      "governance",
    ],
  },
  planner: {
    role: "planner",
    name: "Maj. R. Sethi",
    callsign: "PLANNER-OPS",
    blurb: "Mission routing, task DAG authoring, what-if approval, and scenario injects.",
    defaultWorkspace: "simulation",
    defaultRoute: "/planner",
    canOperate: true,
    canPlan: true,
    canAdmin: false,
    canApproveDirectives: true,
    canAdjudicateVision: true,
    allowedWorkspaces: [
      "command",
      "simulation",
      "intelligence",
      "readiness",
      "collaboration",
      "analytics",
    ],
  },
  operator: {
    role: "operator",
    name: "Sgt. P. Kulkarni",
    callsign: "WATCH-OFFICER",
    blurb: "Real-time tactical control, alert acknowledgment, camera adjudication, and medevac dispatch.",
    defaultWorkspace: "command",
    defaultRoute: "/",
    canOperate: true,
    canPlan: false,
    canAdmin: false,
    canApproveDirectives: false,
    canAdjudicateVision: true,
    allowedWorkspaces: [
      "command",
      "simulation",
      "intelligence",
      "readiness",
      "collaboration",
      "analytics",
    ],
  },
  viewer: {
    role: "viewer",
    name: "Obs. L. Fernandes",
    callsign: "OBSERVER-EVAL",
    blurb: "Strict read-only evaluation across exercises with zero state mutation capabilities.",
    defaultWorkspace: "command",
    defaultRoute: "/dashboard",
    canOperate: false,
    canPlan: false,
    canAdmin: false,
    canApproveDirectives: false,
    canAdjudicateVision: false,
    allowedWorkspaces: [
      "command",
      "simulation",
      "intelligence",
      "readiness",
      "collaboration",
      "analytics",
    ],
  },
};

/** Finds which workspace a specific route pathname belongs to. */
export function getWorkspaceForRoute(pathname: string): WorkspaceDefinition {
  // Exact or prefix match on tool routes
  for (const ws of WORKSPACES) {
    for (const tool of ws.tools) {
      if (tool.to === pathname) return ws;
      if (tool.to !== "/" && pathname.startsWith(tool.to)) return ws;
    }
  }
  // Default to Command Center
  return WORKSPACES[0]!;
}

/** Returns the active tool within the current workspace for a given pathname. */
export function getActiveToolForRoute(pathname: string): WorkspaceTool | null {
  const ws = getWorkspaceForRoute(pathname);
  for (const tool of ws.tools) {
    if (tool.to === pathname) return tool;
    if (tool.to !== "/" && pathname.startsWith(tool.to)) return tool;
  }
  return ws.tools[0] || null;
}

/** Filters available workspaces and tools for a specific role. */
export function getAvailableWorkspacesForRole(role: Role | null): WorkspaceDefinition[] {
  if (!role) return WORKSPACES.filter((w) => !w.adminOnly);
  const profile = ROLE_PROFILES[role] || ROLE_PROFILES.viewer;
  return WORKSPACES.filter((ws) => profile.allowedWorkspaces.includes(ws.id)).map((ws) => ({
    ...ws,
    tools: ws.tools.filter((tool) => {
      if (tool.adminOnly && role !== "admin") return false;
      if (tool.plannerOnly && role !== "admin" && role !== "planner") return false;
      return true;
    }),
  }));
}

/** Resolves default landing route for an authenticated role. */
export function getDefaultRouteForRole(role: Role | null): string {
  if (!role) return "/";
  const profile = ROLE_PROFILES[role] || ROLE_PROFILES.viewer;
  return profile.defaultRoute;
}
