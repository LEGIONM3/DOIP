# DOIP Phase 7 — Platform Unification Architecture
## Standardized Service Directory, Lifecycle Management & Zero Fragmentation
### ECC Global Engineering Program — Phase 7A Blueprint

---

## 1. Executive Intent & Architectural Unification

Prior to Phase 7, the Defense Operations Intelligence Platform (DOIP) evolved across six feature and hardening phases, resulting in over a dozen powerful but distinct subsystems:
- Deterministic Discrete-Event Simulation Core
- Tactical Route Planning & Spatial Cost Grids
- Task DAG Mission Planning & Status State Machines
- Real-Time War Room WebSocket Collaboration Hub
- Dual-Mode Persistence (PostgreSQL 16 + PostGIS & SQLite WAL)
- Multi-Tier Command Federation & Multi-Theater Digital Twins
- Autonomous Planning Agent Swarms & Persistent Long-Term Memory
- Large-Scale Risk Tensor Forecasting & Massive What-If Explorer
- Operational Analytics, OpenTelemetry Observability & Automated Reporting
- Resilience Circuit Breakers & Monotonic Sequence LRU Caching

**Phase 7A eliminates architectural fragmentation** by unifying all subsystems under a single, cohesive platform foundation:
1. **`PlatformRegistry`**: Single authoritative directory of all system services.
2. **`PlatformService`**: Common polymorphic interface and lifecycle contracts.
3. **`PlatformConfiguration`**: Centralized operational parameter governance.
4. **`PlatformLifecycleManager`**: Orchestrated bootstrapping, health verification, and clean shutdown.

```text
                               ┌─────────────────────────────┐
                               │     PlatformRegistry        │
                               │  - Service Directory        │
                               │  - Health State Aggregator  │
                               └──────────────┬──────────────┘
                                              │
                      ┌───────────────────────┼───────────────────────┐
                      ▼                       ▼                       ▼
            ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
            │   Simulation     │    │     Routing      │    │     Missions     │
            │   Subsystem      │    │    Subsystem     │    │    Subsystem     │
            └──────────────────┘    └──────────────────┘    └──────────────────┘
                      ▼                       ▼                       ▼
            ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
            │    Knowledge     │    │   Forecasting    │    │    Federation    │
            │    Subsystem      │    │    Subsystem     │    │    Subsystem     │
            └──────────────────┘    └──────────────────┘    └──────────────────┘
                      ▼                       ▼                       ▼
            ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
            │   Agent Swarm    │    │    Workflows     │    │   Observability  │
            │    Subsystem     │    │    Subsystem     │    │    Subsystem     │
            └──────────────────┘    └──────────────────┘    └──────────────────┘
                      ▼                       ▼                       ▼
            ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
            │   Governance     │    │   Self-Healing   │    │  Data & Quality  │
            │    Subsystem     │    │    Subsystem     │    │    Subsystems    │
            └──────────────────┘    └──────────────────┘    └──────────────────┘
```

---

## 2. Core Service Directory (`PlatformRegistry`)

Every operational subsystem implements the `PlatformService` interface and registers at system boot time. No orphan services or duplicate execution paths are permitted.

| Service Identifier | Subsystem | Dependencies | Primary Functionality |
|---|---|---|---|
| `deterministic_sim_engine` | `simulation` | None | Pure fixed-step discrete-event simulator enforcing golden seed verification. |
| `tactical_routing_engine` | `routing` | `deterministic_sim_engine` | Multi-factor Grid A* route planning against dynamic threat corridors. |
| `mission_planning_engine` | `planning` | `tactical_routing_engine` | Task DAG mission creation with mandatory human authorization gate. |
| `warroom_collaboration_hub` | `collaboration`| None | Real-time WebSocket hub for presence, task claims, and incident handoffs. |
| `unified_knowledge_platform`| `knowledge` | None | Unified cognitive facade: Graph + RAG + Memory + Risk Tensors. |
| `digital_twin_forecaster` | `forecasting` | `deterministic_sim_engine` | Multi-tick forward lookahead for fuel, RF silence, and threat intersections. |
| `command_federation_engine` | `federation` | None | Hierarchical tree federation (National -> Regional -> Operational -> Tactical). |
| `agent_runtime_platform` | `autonomy` | `unified_knowledge_platform`| Centralized agent directory, task queue, and swarm execution coordinator. |
| `operational_workflow_engine`| `workflows` | `mission_planning_engine` | Deterministic state machine governing mission lifecycle and approvals. |
| `observability_and_resilience`| `operations` | None | OpenTelemetry metrics, circuit breakers, and monotonic LRU cache. |
| `autonomous_governance_engine`| `governance` | None | Pre-execution compliance, determinism validation, and HITL gatekeeper. |
| `self_healing_operational_layer`| `reliability`| `observability_and_resilience`| Autonomous circuit reset, cache rebuild, index repair, and workflow rollback. |
| `data_governance_framework` | `data` | None | Lineage tracking, schema registry, audit compliance, and retention policy. |
| `quality_assurance_platform`| `quality` | None | Continuous metric scoring, test tracking, and DOIP Quality Index (DQI). |
| `future_research_sandbox` | `research` | None | Isolated ephemeral sandbox for experimental AI and novel simulations. |

---

## 3. Standardized PlatformService Contract

Each service provides standard lifecycle methods:
- `start() -> None`: Initializes resources, warms local caches, and sets status to `HEALTHY`.
- `stop() -> None`: Flushes buffers, releases locks, and transitions to `STOPPED`.
- `health_check() -> Dict[str, Any]`: Evaluates operational health, returning status (`HEALTHY`, `DEGRADED`, `FAILED`).
- `to_dict() -> Dict[str, Any]`: Serializes service metadata, dependencies, and operational metrics.

---

## 4. PlatformLifecycleManager

The lifecycle manager coordinates system startup and shutdown:
1. **Bootstrap Sequence**:
   - Initializes database engines (PostgreSQL/PostGIS or tuned SQLite WAL).
   - Registers all 15 core services in `PlatformRegistry`.
   - Starts all services and verifies initial health checks.
2. **Shutdown Sequence**:
   - Broadcasts termination notice to connected War Room clients.
   - Flushes pending telemetry stream batches via `BatchProcessor`.
   - Stops registered services in reverse dependency order.

---

## 5. REST & Operational Inspection Endpoints

- `GET /api/platform/services`: Returns comprehensive catalog of registered services.
- `GET /api/platform/health`: Returns aggregated health score and individual service statuses.
- `POST /api/platform/bootstrap`: Programmatically triggers platform bootstrap.
