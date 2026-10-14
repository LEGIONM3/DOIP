# DOIP — Unified Command Center & Workflow Consolidation Architecture

## Phase 1 — Comprehensive Baseline Inventory & Reality Matrix

### 1. Architectural Baseline & Test Status
- **Frontend Type Safety**: Strict TypeScript compiler (`npx tsc --noEmit`) verified with **0 errors**.
- **Frontend Unit & Component Suites**: 6 Vitest test suites, **14 tests passing, 0 failed**.
- **Backend Architecture & Integration Suites**: 48 Pytest suites, **210 tests passing, 0 failed**.
- **Production SSR Build**: Vite + Nitro SSR production build completed with **0 errors**.
- **Determinism Baseline**: `tests/golden/sc2_seed8841.hash` byte-identical match verified.

### 2. Screen & Feature Inventory Across 7 Workspaces

| Code | Route | Screen Name | Workspace | Primary Domain | Backend APIs / Sockets | Permissions | Implementation Reality |
|---|---|---|---|---|---|---|---|
| S1 | `/login` | Authentication & Entry | Command Center | Access & Identity | `/auth/login` | Public / All | 100% Implemented (Demo roles + JWT) |
| S2 | `/dashboard` | Operations Dashboard | Command Center | Overview & KPIs | `/scenarios`, `/runs`, `/audit` | Viewer+ | 100% Implemented (CRHI score, tiles) |
| S3 | `/` | Live Tactical Map | Command Center | Tactical Picture | `/ws/sim/{run_id}`, `/scenarios` | Viewer+ (Ack: Operator+) | 100% Implemented (MapLibre GL, Layers, Ruler) |
| S4 | `/run` | Run Control Console | Simulation & Mission | Execution & PRNG | `/runs`, `/scenarios`, `/audit` | Operator+ | 100% Implemented (PRNG seed, 0.5-8x, hash) |
| S5 | `/planner` | Mission Planner | Simulation & Mission | Tactical Pathfinding | `/api/routes/calculate`, `/api/missions` | Planner+ | 100% Implemented (Grid A*, Task DAG) |
| S6 | `/replay` | Total Replay & Scrub | Simulation & Mission | Retrospective | `/runs/{id}/report`, `/runs` | Viewer+ | 100% Implemented (Event folding scrubber) |
| S7 | `/sitrep` | Grounded AI SITREP | Intelligence & AI | Cited Briefings | `/sitrep`, `/api/ai/query` | Viewer+ | 100% Implemented (Citations, TTS audio) |
| S8 | `/whatif` | What-If Theater | Simulation & Mission | Branch Simulation | `/whatif`, `/whatif/history` | Operator+ (Approve: Planner+) | 100% Implemented (DSL parser, Monte Carlo) |
| S9 | `/vision` | Surveillance Matrix | Command / Intel | Neural Computer Vision | `/vision/frames`, `/vision/adjudicate` | Viewer+ (Adj: Operator+) | 100% Implemented (YOLOv8, FLIR, Tripwires) |
| S10 | `/logistics` | Logistics & Sustainment | Resources & Readiness | Supply Chain | `/runs`, Local events | Viewer+ (Dispatch: Operator+) | 100% Implemented (Burndown, TTE, Resupply) |
| S11 | `/personnel` | Personnel Readiness | Resources & Readiness | Biometrics & Vitals | Local events, `/api/warroom/tasks` | Viewer+ (Medevac: Operator+) | 100% Implemented (Vitals, Shifts, Medevac) |
| S12 | `/analytics` | Tactical Analytics | Analytics & Health | Event Analytics | `/runs`, Local events | Viewer+ | 100% Implemented (Sparklines, MTBF) |
| S13 | `/advisor` | Investment Advisor | Resources & Readiness | Capability Procurement | `/api/optimizer/solve`, `/api/optimizer/history` | Viewer+ (Solve: Planner+) | 100% Implemented (Knapsack, Pareto curves) |
| S14 | `/warroom` | Collaborative War Room | Collaboration & Command | Operations Center | `/ws/warroom`, `/api/warroom/tasks` | Viewer+ (Operate: Operator+) | 100% Implemented (WebSocket cursors, Kanban) |
| S15 | `/admin` | Admin, Corpus & Audit | Admin & Governance | Governance & RBAC | `/admin/users`, `/audit`, `/corpus/docs` | Admin Only | 100% Implemented (User DB sync, Audit log) |
| S16 | `/scenario-editor`| Scenario DSL Editor | Simulation & Mission | Scenario Authoring | `/scenarios/custom`, `/scenarios/validate` | Planner+ | 100% Implemented (DSL visual builder) |
| S17 | `/doctrine` | Doctrine & SOP Corpus | Intelligence & AI | Document RAG | `/corpus/docs`, `/api/rag/retrieve` | Viewer+ | 100% Implemented (15 doctrine docs, RRF) |
| S18 | `/forecast` | Digital Twin Forecaster | Simulation & Mission | Forward Lookahead | `/api/forecast`, `/api/forecast/history` | Viewer+ (Run: Operator+) | 100% Implemented (PNR, RF shadows, Arrival) |
| S19 | `/graph` | Knowledge Graph AI | Intelligence & AI | Causal Analysis | `/api/graph/subgraph`, `/api/graph/root-cause` | Viewer+ | 100% Implemented (NetworkX, SPOF finder) |
| S20 | `/federation` | Federated Command Mesh | Collaboration & Command | Multi-Tier Hierarchy | `/api/federation/nodes`, `/api/federation/directives`| Viewer+ (Directives: Planner+) | 100% Implemented (3-tier hierarchy, Intel sync) |
| S21 | `/theaters` | Multi-Theater Digital Twin | Collaboration & Command | Multi-World Simulation | `/api/theaters`, `/api/theaters/cross-analysis` | Viewer+ (Operate: Operator+) | 100% Implemented (Isolated worlds WLD-1..3) |
| S22 | `/campaigns` | Strategic Campaign Swarm| Collaboration & Command | Multi-Agent Swarm | `/api/strategic/campaigns`, `/api/swarm/plan` | Viewer+ (Plan: Planner+) | 100% Implemented (6-agent swarm, Briefs) |
| S23 | `/futures` | Future Explorer | Simulation & Mission | Monte Carlo Risk Bands | `/api/futures/generate`, `/api/futures` | Operator+ | 100% Implemented (P10/P50/P90/WORST bands) |
| S24 | `/datalake` | Data Lake & Event Streams| Analytics & Health | Telemetry Lake & Bus | `/api/datalake/objects`, `/api/events/replay` | Viewer+ (Publish: Operator+) | 100% Implemented (Kafka EventBus, MinIO Lake) |
| S25 | `/agents` | Unified Agent Runtime | Intelligence & AI | Agent Directory | `/api/agents`, `/api/agents/tasks` | Viewer+ (Submit: Operator+) | 100% Implemented (Registry, Task queue) |
| S26 | `/memory` | Cognitive Memory Store | Intelligence & AI | Multi-Tier Memory | `/api/memory/retrieve`, `/api/memory/remember` | Viewer+ (Store: Operator+) | 100% Implemented (Semantic/Episodic/Working) |
| S27 | `/analytics-center`| Enterprise Analytics Center | Analytics & Health | Reporting Center | `/api/analytics/dashboard`, `/api/reports` | Viewer+ (Generate: Operator+) | 100% Implemented (Daily SITREP, AAR export) |
| S28 | `/workflows` | Workflows & Approval Gates| Collaboration & Command | State Machine & HITL | `/api/workflows`, `/api/workflows/{id}/approve` | Viewer+ (Approve: Planner+) | 100% Implemented (FSM state machine, Gates) |
| S29 | `/models` | Model Governance & Router | Admin & Governance | AI Governance | `/api/models`, `/api/models/route` | Admin Only (Test: Planner+) | 100% Implemented (Task router, GPU/Cloud) |
| S30 | `/observability` | Enterprise Observability | Analytics & Health | Platform Metrics | `/api/observability/metrics`, `/prometheus` | Viewer+ | 100% Implemented (P50/P90/P99, Prometheus) |
| S31 | `/model-lab` | Hybrid Physics & Model Lab| Intelligence & AI | Hybrid AI & Calibration| `/api/laya/decide`, `/api/simulation/hybrid` | Viewer+ (Evaluate: Operator+) | 100% Implemented (ModernBERT Laya, Sliders) |

### 3. Identified UX Friction, Redundancies & Opportunities
1. **Navigation Overhead**: Previously, operators were forced to scroll a flat vertical list of 30 buttons in `SideNav.tsx`, creating severe cognitive load and navigation friction.
2. **Disconnected Handoffs**:
   - Creating an inject in Scenario Editor (`/scenario-editor`) required manual mental transfer to Run Control (`/run`).
   - Investigating an incident on the Live Map (`/`) required manual navigation to Knowledge Graph (`/graph`) or re-typing the event ID in AI Drawer.
   - Identifying a supply or medical crisis in Logistics (`/logistics`) or Personnel (`/personnel`) required manual re-entry into the War Room task board (`/warroom`) or Mission Planner (`/planner`).
   - Stopping a simulation run did not automatically offer a 1-click pathway into Total Replay (`/replay`) or After-Action Report generation.
3. **Workspace Cohesion**:
   Grouping screens into **7 Primary Workspaces** with a dedicated secondary navigation bar and contextual headers allows operators to stay immersed in their domain without losing global context.

---

## Phase 2 — The Seven Primary Workspaces Architecture

```
WORKSPACE STRUCTURE
├── 1. Command Center (/ or /dashboard)
│   ├── Operations Dashboard (S2)
│   ├── Live Tactical Map (S3)
│   └── Surveillance Camera Matrix (S9)
├── 2. Simulation & Mission (/planner)
│   ├── Mission Planner (S5)
│   ├── Run Control Console (S4)
│   ├── Scenario DSL Editor (S16)
│   ├── Total Replay & Scrubber (S6)
│   ├── What-If Theater (S8)
│   ├── Future Explorer (S23)
│   └── Digital Twin Forecaster (S18)
├── 3. Intelligence & AI (/sitrep)
│   ├── Grounded AI SITREP (S7)
│   ├── Doctrine & SOP Corpus (S17)
│   ├── Operational Knowledge Graph (S19)
│   ├── Cognitive Memory Store (S26)
│   ├── Unified Agent Runtime (S25)
│   └── Hybrid Physics & Model Lab (S31)
├── 4. Resources & Readiness (/logistics)
│   ├── Logistics & Burndown (S10)
│   ├── Personnel Biometrics & Vitals (S11)
│   └── Investment Advisor (S13)
├── 5. Collaboration & Command (/warroom)
│   ├── Collaborative War Room (S14)
│   ├── Federated Command Mesh (S20)
│   ├── Multi-Theater Digital Twin (S21)
│   ├── Strategic Campaign Swarm (S22)
│   └── Operational Workflows & Gates (S28)
├── 6. Analytics & System Health (/analytics)
│   ├── Tactical Analytics (S12)
│   ├── Enterprise Analytics Center (S27)
│   ├── Enterprise Observability (S30)
│   └── Data Lake & Event Streams (S24)
└── 7. Administration & Governance (/admin)
    ├── User Roster & RBAC (S15)
    ├── Immutable Audit Log (S15)
    ├── Scenario & Corpus Catalog (S15)
    └── Model Governance & Router (S29)
```

---

## Phase 3 — Profile-Aware Capabilities Matrix

| Profile | Callsign | Default Landing | Permitted Workspaces | State-Modifying Capabilities | Approval & HITL Authority |
|---|---|---|---|---|---|
| **Admin** | Col. A. Verma | `/dashboard` (Command) | All 7 Workspaces | Full system, user roster, audit management | Authorize all state changes, override gates |
| **Planner** | Maj. R. Sethi | `/planner` (Simulation) | 1 through 6 | Mission routes, DAG tasks, scenario DSL authoring | Authorize what-if branches & mission execution |
| **Operator** | Sgt. P. Kulkarni | `/` (Live Map) | 1 through 6 | Run control, alert ACK, vision adjudication, medevac | Submit requests; cannot bypass approval gates |
| **Viewer** | Obs. L. Fernandes | `/dashboard` (Command) | 1 through 6 (Read-Only) | Strictly 0 mutations (all action buttons disabled) | Read-only observation and audit inspection |

---

## Phase 4 — Cross-Feature Workflow Handoff Contracts

```typescript
export interface OperationalContext {
  activeWorkspace: WorkspaceId;
  activeRunId: string | null;
  activeScenarioId: string | null;
  selectedEntityId: string | null;
  selectedIncidentId: string | null;
  selectedEventId: number | null;
  selectedTaskId: string | null;
  pendingApprovalsCount: number;
}
```

### Supported Seamless Handoffs:
1. **Scenario Authoring $\rightarrow$ Simulation Execution**: In S16, clicking "Launch Scenario" loads seed & scenario into S4 Run Control and starts the deterministic engine.
2. **Incident Alert $\rightarrow$ Contextual AI & Knowledge Graph**: In S2/S3, clicking "Investigate with AI" opens the AI Drawer with the incident context; clicking "Trace Graph" opens S19 with root-cause attribution.
3. **Logistics/Personnel Warning $\rightarrow$ War Room Task & Route Plan**: In S10/S11, clicking "Dispatch Resupply" or "Dispatch MEDEVAC" creates a task in S14 War Room and loads waypoints into S5 Mission Planner.
4. **Simulation Completion $\rightarrow$ Total Replay & AAR**: In S4, when a run stops or pauses, a banner provides a direct jump to S6 Replay with the run pre-selected.
5. **Active Battle $\rightarrow$ Isolated What-If Branch**: In S3/S4, clicking "Branch What-If" carries active tick and scenario to S8 without modifying live simulation state.
6. **Model Disagreement $\rightarrow$ Observability**: In S31, high neural/rule disagreement flags direct links to S30 Observability and S29 Model Registry.
7. **AI Recommendation $\rightarrow$ Governance Sign-Off**: Directives in S7 or AI Drawer require explicit commander confirmation and log into S15 Audit Ledger.

---

## Phase 5 — Verification & Acceptance Record

1. **Frontend Vitest Test Suite**:
   - `src/components/shell/UnifiedWorkspace.test.tsx`: 18 tests passing covering 7 workspaces, role profiles, tool routing, and cross-feature handoffs.
   - `src/components/shell/AiDrawer.test.tsx`: 2 tests passing covering grounded posture, verified citations, and DSL safety boundaries.
   - `src/services/ai.test.ts`: 2 tests passing.
   - `src/services/routing.test.ts`: 3 tests passing.
   - `src/services/missions.test.ts`: 2 tests passing.
   - `src/services/optimizer.test.ts`: 2 tests passing.
   - `src/services/redteam.test.ts`: 3 tests passing.
   - **Total Frontend**: 7 test files, 32 tests passing (100%).

2. **TypeScript Strict Type Check**:
   - `npx tsc --noEmit`: 0 errors.

3. **Production SSR Build**:
   - `npm run build`: Nitro / Vite production SSR bundle compiled cleanly with 0 errors.

4. **Backend Invariants & Determinism**:
   - Mulberry32 deterministic seeded PRNG runs remain bit-identical.
   - Immutable event history and SHA-256 fingerprinting verified across all runs.
   - Mandatory human-in-the-loop gates enforced across workflows and AI directive dispatches.

