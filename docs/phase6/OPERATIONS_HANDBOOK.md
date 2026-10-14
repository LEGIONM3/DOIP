# DOIP Operations Handbook
## Defense Operations Intelligence Platform — Standard Operating Procedures (SOP)
### Phase 6 Production Hardening & Operational Readiness

---

## 1. Operational Overview & Station Roles

The **DOIP War Room & Operations Console** provides a collaborative tactical operational picture (COP) enabling distributed command teams to coordinate missions, adjudicate sensor data, run stochastic lookaheads, and execute validated courses of action (COAs).

### 1.1 Watchstander Roles & Responsibilities

| Role | Clearance / Perms | Core Operational Responsibilities |
|---|---|---|
| **Mission Commander (CDR)** | Level 4 / Full Authority | Authorizes mission transitions (`DRAFT` → `EXECUTION`), approves tactical COAs, and signs off on kinetic constraints. |
| **Tactical Operator (OPS)** | Level 3 / Operator | Plans routes, manages task DAG assignments, stages adversarial injects, and monitors asset telemetry in real time. |
| **Intelligence Analyst (INTEL)**| Level 3 / Read + Query | Queries the Unified Knowledge Platform, analyzes doctrine RAG references, reviews causal graphs, and tracks sensor contacts. |
| **Red Team Evaluator (RED)** | Level 3 / Staging | Synthesizes adversarial stress scenarios, probes route vulnerabilities, and evaluates blue force defense posture. |
| **System Administrator (SYSADMIN)**| Level 4 / Ops & Infra | Monitors resilience circuit breakers, manages cache performance, inspects telemetry buffers, and manages federation heartbeats. |

---

## 2. War Room Collaboration Procedures

### 2.1 Establishing a Session
1. **Login & Presence**: Authenticate with designated credentials. The client opens a persistent WebSocket connection to `/ws/warroom`.
2. **Channel Subscription**: Operators join the primary incident channel (`INC-DEFAULT` or mission-specific channel ID).
3. **Presence Verification**: The top-right operator strip displays active watchstanders and their assigned roles.

### 2.2 Task Delegation & Tactical Scratchpad
- **Task Creation**: Operators create sub-tasks directly from the War Room panel:
  - `POST /api/warroom/tasks` with `title`, `priority` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), and `due_tick`.
- **Assignment & Lock**: Operators claim tasks (`POST /api/warroom/tasks/{task_id}/assign`). Real-time broadcast prevents duplicate work across distributed stations.
- **Shared Scratchpad**: Notes, tactical coordinates, and spot reports are broadcast in real time across connected war room clients.

---

## 3. Mission Planning & Human-in-the-Loop Authorization

All mission transitions into active status adhere strictly to the **Mandatory Human-in-the-Loop Gate**.

```text
[Operator creates Mission]
          │
          ▼
   Status: DRAFT
          │
          ├────────────────────────────────────────┐
          │                                        │
          ▼                                        ▼
[Tactical Route Optimization]           [Red Team Vulnerability Scan]
          │                                        │
          ▼                                        ▼
   Route Verified                           Risk Matrix Evaluated
          │                                        │
          └──────────────────┬─────────────────────┘
                             │
                             ▼
                 [Commander Sign-off Required]
                             │
            ┌────────────────┴────────────────┐
            │                                 │
     No Authenticator                Approved by Commander
            │                                 │
            ▼                                 ▼
      HTTP 403 Forbidden              Status: EXECUTION
   (PermissionError Raised)            (Autonomous Swarm / Units Act)
```

### Step-by-Step Mission Execution SOP
1. **Drafting**: Create the mission definition via UI or `POST /api/missions` with target waypoints, asset allocations, and time-on-target (TOT).
2. **Route Generation**: Run `POST /api/routing/plan` to compute fuel-optimal and threat-averse paths using A* routing against live threat rings.
3. **Adversarial Evaluation**: Generate staged stress injects via `POST /api/redteam/scenarios/generate`.
4. **Approval Gate**: The Mission Commander verifies mission parameters and submits formal sign-off:
   ```json
   POST /api/missions/{mission_id}/status
   {
     "status": "execution",
     "actor": "commander_nash"
   }
   ```
   *Note: Omitting `actor` or attempting execution without commander role raises an unyielding `HTTP 403 Forbidden` error.*

---

## 4. Digital Twin Forecasting & What-If Operations

DOIP enables predictive lookahead without risking the authoritative live simulation.

### 4.1 Running a Digital Twin Forecast
1. **Horizon Selection**: Select forecast window (nominal: 2.0 hours / 120-360 simulation ticks).
2. **Execute Projection**: Call `POST /api/forecasting/run` or toggle "Predictive Horizon" on the tactical map.
3. **Key Indicator Review**:
   - **Fuel Depletion**: Verify Point-of-No-Return (PNR) ticks for all motorized and aerial units.
   - **RF Silence Windows**: Inspect VHF/HF comms blackout zones along planned corridors.
   - **Threat Escalation Intersections**: Review hostile path projections and probability of engagement.
   - **Mission Arrival Percentiles**: Assess P10 (optimistic), P50 (median), and P90 (degraded) arrival bounds.

### 4.2 Decoupled What-If Branching
- What-If simulations fork simulation state into isolated sandbox instances.
- Operators may simulate environmental disruptions (dust storms, bridge collapses, EW jamming).
- **Core Invariant**: Under no circumstances does a What-If exploration modify live unit coordinates or authoritative event logs.

---

## 5. Unified Knowledge & RAG Analysis

When tactical ambiguity arises, operators leverage the **AI Drawer Copilot**.

1. **Querying Doctrine & History**:
   - Access the copilot input in the right drawer.
   - Example Query: `"What is the standard dispersal protocol for motorized convoys encountering thermal UAS surveillance?"`
2. **Reviewing Grounded Response**:
   - The platform responds with dense RAG citations referencing specific doctrine artifacts (e.g., `SOP-03-CONVOY-OPS.md §4.2`).
   - Every citation includes verbatim corroborating text and confidence scores.
3. **Knowledge Graph Root-Cause Traversal**:
   - For recurring supply failures or route bottlenecks, open the Graph Explorer to view dependency chains (`depends_on`, `caused_by`, `affected_by`).

---

## 6. Routine System Health & Maintenance Checks

### 6.1 Daily Watchstander Health Checklist
- [ ] **Circuit Breakers**: Inspect `/api/resilience/status`. Confirm all breakers are in `CLOSED` state.
- [ ] **Cache Utilization**: Inspect `/api/cache/stats`. Confirm hit rates are > 60% and memory footprint is nominal.
- [ ] **Federation Heartbeats**: Verify upstream Regional Command sync timestamp is < 30 seconds old.
- [ ] **Golden Run Verification**: Confirm CI/CD hash check matches `sc2_seed8841.hash`.
- [ ] **PostGIS / SQLite Disk Space**: Ensure database volume has > 25% free capacity.
