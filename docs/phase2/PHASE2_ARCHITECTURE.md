# DOIP Phase 2 Architecture Specification
## Tactical Operations & Decision Support Expansion

**Lead Architect:** ARCHITECT Agent (ECC Multi-Agent Execution Protocol)  
**Program:** Defense Operations Intelligence Platform (DOIP)  
**Version:** 2.0.0  

---

## 1. System Topology & Subsystem Overview

Phase 2 builds upon the completed Phase 1 foundation (Dense Semantic RAG, Citation Validator, Real AI Drawer, and PostgreSQL/PostGIS persistence). It expands DOIP into an active decision-support and tactical planning platform without compromising determinism or human-in-the-loop safety.

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        DOIP FRONTEND SHELL                             │
│  Route Planner  ·  Mission Planner  ·  War Room  ·  Optimizer  ·  Red  │
└───────┬───────────────────┬─────────────────┬──────────────────┬───────┘
        │                   │                 │                  │
        ▼                   ▼                 ▼                  ▼
┌──────────────┐    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Phase 2A:   │    │  Phase 2B:   │   │  Phase 2C:   │   │  Phase 2D/E: │
│ Tactical A*  │    │   Mission    │   │   War Room   │   │  Optimizer & │
│ Route Engine │    │   Planner    │   │  WS Collab   │   │   Red Team   │
└───────┬──────┘    └───────┬──────┘   └───────┬──────┘   └───────┬──────┘
        │                   │                  │                  │
        ▼                   ▼                  ▼                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI SERVICE GATEWAY                         │
│  /api/routes  ·  /api/missions  ·  /ws/warroom  ·  /api/optimizer     │
│  /api/redteam  ·  /api/ai/query (P1)  ·  /scenarios/validate (DSL)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        ▼                                                       ▼
┌────────────────────────────────┐            ┌────────────────────────────────┐
│   POSTGRESQL + POSTGIS (PROD)  │            │     SQLITE FALLBACK (DEV)      │
│  Spatial Linestrings, Polygons │            │  JSON Geo Fallback + Math      │
│  Alembic Migration Managed     │            │  Zero External Dependency      │
└────────────────────────────────┘            └────────────────────────────────┘
```

---

## 2. Subsystem Architectural Contracts

### 2.1 Phase 2A — Tactical Route Planning Engine (`routing.py`)
- **Core Algorithm:** Deterministic 2D/3D Grid A* Pathfinding.
- **Cost Function:**
  $$\text{Cost}(u, v) = \text{Dist}(u, v) \cdot \Big[ W_{\text{base}} + C_{\text{terrain}}(v) + C_{\text{weather}}(v) + C_{\text{threat}}(v) + C_{\text{fuel}}(u,v) + C_{\text{time}}(u,v) \Big]$$
- **Hard Constraints:** Prohibited ingress into active No-Fly Zones (NFZ) or Restricted Operational Areas. Evaluated via PostGIS `ST_Contains` / `ST_Intersects` (with ray-casting fallback).
- **Supported Strategies:**
  1. `shortest`: Minimizes Euclidean path length ($W_{\text{base}} = 1.0$, small penalties).
  2. `safest`: Heavily penalizes threat envelopes ($C_{\text{threat}} \times 10.0$) and active storm cells ($C_{\text{weather}} \times 5.0$).
  3. `fuel_efficient`: Penalizes steep elevation changes, headwinds, and detour acceleration.
  4. `fastest`: Follows primary transit corridors; avoids speed-degrading terrain and crosswinds.
- **Explainability:** Returns a step-by-step rationale for why the chosen route bypasses specific threats or terrain bottlenecks.

### 2.2 Phase 2B — Mission Planning System (`mission_planner.py`)
- **Entities:** `Mission`, `MissionObjective`, `MissionTask`, `Waypoint`, `AssetAssignment`.
- **Deterministic Lifecycle:**
  $$\text{Draft} \longrightarrow \text{Review} \longrightarrow \text{Approved} \longrightarrow \text{Executing} \longrightarrow \begin{cases} \text{Completed} \\ \text{Cancelled} \end{cases}$$
- **Resource Estimation:**
  - Duration: Calculated from route length divided by assigned unit cruise speeds.
  - Fuel Consumption: Estimated from base fuel consumption rate + climb/payload factors.
  - Risk Scoring: Aggregate exposure to threats and weather along planned waypoints ($0.0 \le \text{Risk} \le 1.0$).
- **AI Planning Integration:** The AI Drawer accepts natural language mission requests (e.g. *"Plan convoy escort mission to Sector 4"*), generates a structured mission proposal, and stages it as `Draft`.
- **Safety Boundary:** AI is strictly prohibited from transitioning a mission to `Approved` or `Executing`. Transitioning requires explicit human operator signature.

### 2.3 Phase 2C — War Room Real-Time Collaboration (`warroom.py`)
- **WebSocket Gateway:** `/ws/warroom` with JSON-RPC/event protocol and JWT role authentication.
- **Operator Presence:** Tracks active operators, client focus, and role badges (`analyst`, `operator`, `planner`, `admin`). Emits heartbeat pings every 15 seconds.
- **Shared Tactical Map:** Broadcasts cursor positions, selected tactical entities (units, incidents), and map annotations (points, lines, polygons).
- **Incident Coordination:** Supports incident task board (`TODO`, `IN_PROGRESS`, `DONE`), assigning incidents to specific operators, and recording handoff audit trails.

### 2.4 Phase 2D — Investment Optimization Engine (`optimizer.py`)
- **Mathematical Formulation:** Multi-attribute portfolio optimization (Mixed-Integer Linear Programming / Knapsack formulation).
- **Decision Variables:**
  - Asset Procurement / Refit: UAVs, Patrol Vehicles, Comms Encryption Upgrades, Radar Relays.
  - Logistics Sizing: Forward Depot Fuel Capacity, Ammo Caches, Maintenance Bays.
  - Personnel / Training: Tactical Operators, Drone Pilots, Field Medics.
- **Objective Function:** Maximize aggregate operational score:
  $$\max \quad \alpha \cdot \text{Readiness} + \beta \cdot \text{Coverage} + \gamma \cdot \text{ResponseTime} + \delta \cdot \text{FuelResilience} - \lambda \cdot \text{BudgetCost}$$
- **Constraint Matrix:** Total expenditure $\le \text{Budget}$; Asset counts $\le \text{Capacity}$; Minimum doctrine reserves maintained.
- **What-If Evaluation:** Compares baseline capability scores against proposed investment portfolios.

### 2.5 Phase 2E — Red Team Adversarial Planner (`redteam.py`)
- **Function:** Automated red-teaming to stress-test mission plans and route vulnerabilities.
- **Inject Categories:**
  - `AMBUSH`: Hostile contact at choke-point or high-risk route segment.
  - `COMMS_JAMMING`: RF electronic warfare causing telemetry loss.
  - `FUEL_LEAK`: Supply disruption reducing operational radius.
  - `SEVERE_WEATHER`: Microburst or sandstorm impairing UAV visibility.
  - `ROUTE_OBSTACLE`: IED / blocked corridor forcing tactical reroute.
- **Safety Boundary:**
  - Red Team outputs strictly structured **proposals** (`RedTeamScenario`, `ProposedInject`).
  - Every inject MUST conform to DOIP DSL syntax (`INJECT_WEATHER`, `TRIGGER_INCIDENT`, `JAM_COMMS`).
  - Injects MUST pass the `dsl_parser.py` validation gate.
  - Injects CANNOT mutate simulation state without human planner approval.

---

## 3. Database Schema Layout (Phase 2 Additions)

Alembic Migration: `versions/7a0e8d19bc23_phase2_tactical_schemas.py`

1. `missions`: Primary mission record, lifecycle status, risk score, estimated duration and fuel.
2. `mission_tasks`: Ordered sequence of mission objectives and assigned units.
3. `waypoints`: Spatially indexed waypoint sequence with PostGIS geometry.
4. `routes`: Persisted optimal paths, strategy used, distance, duration, and GeoJSON coordinates.
5. `route_segments`: Granular segments with terrain/threat cost breakdown.
6. `warroom_presence`: Active operator presence, current screen, and heartbeat timestamp.
7. `warroom_tasks`: Collaborative operational tasks with incident links and assignments.
8. `warroom_assignments`: Incident-to-operator ownership mapping and handoff history.
9. `optimizer_runs`: Investment optimization run inputs (budget, priorities) and outputs.
10. `optimizer_results`: Granular asset allocation recommendations and expected KPI deltas.
11. `redteam_scenarios`: Staged adversarial stress scenarios and risk analysis.
12. `redteam_injects`: DSL-formatted proposed adversarial injects with approval state.
