# DOIP System Architecture Handbook
## Defense Operations Intelligence Platform — Production Architecture Reference
### Phase 6 Production Hardening & Autonomous Operation

---

## 1. System Overview & Architectural Philosophy

The **Defense Operations Intelligence Platform (DOIP)** is an enterprise-grade tactical operations, digital twin simulation, and mission intelligence platform engineered for mission-critical defense environments. DOIP transitions decision support from isolated tactical lookups into a continuous, deterministic, and distributed intelligence ecosystem.

### Core Architectural Principles
1. **Mathematical Determinism**: Simulation state progression is pure and reproducible. Given the same initial scenario seed and input sequence, simulation trajectory is bit-for-bit identical across all nodes.
2. **Authoritative State Immutability**: What-If scenario branches, stochastic rollouts, and predictive lookaheads execute in isolated ephemeral memory spaces; they can never directly mutate the authoritative live simulation timeline.
3. **Mandatory Human-in-the-Loop (HITL)**: Autonomous AI reasoning proposes tactical courses of action (COAs), but kinetic operations, fire transitions, and mission execution authorization require explicit human command sign-off (`approved_by`).
4. **Air-Gapped & Offline Resilience**: DOIP operates seamlessly without internet or external cloud connectivity, providing embedded local embedding engines, local LLM orchestration (Ollama/vLLM), and automatic fallback to grounded deterministic rule engines.
5. **Dual-Mode Persistence Architecture**: High-throughput production deployments leverage PostgreSQL 16 with PostGIS spatial extensions and pgvector; austere, disconnected forward operating bases automatically fall back to tuned SQLite with Write-Ahead Logging (WAL).

---

## 2. High-Level Component Topology

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             PRESENTATION LAYER                              │
│       React 18 + TypeScript + Vite + Tailwind CSS (Blackout Design System)  │
│  ┌──────────────────────┬──────────────────────┬─────────────────────────┐  │
│  │   2D/3D Tactical Map │   AI Drawer Copilot  │   War Room Collab (WS)  │  │
│  │   Leaflet / Canvas   │   Citations & Replay │   Presence & Adjudicate │  │
│  └──────────────────────┴──────────────────────┴─────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP / REST / WebSocket
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                            API & APPLICATION LAYER                          │
│                           FastAPI / Python 3.12                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Resilience Layer: CircuitBreakers (Open/Closed/HalfOpen), Retries    │  │
│  │  Performance Layer: Thread-Safe LRU/TTL Cache, Batch Stream Engines   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────┬──────────────────────┬─────────────────────────┐  │
│  │  Tactical Routing    │  Mission Planning    │  Digital Twin Forecaster│  │
│  │  (A* / Threat Cost)  │  (Task DAG / HITL)   │  (Horizon Lookahead)    │  │
│  ├──────────────────────┼──────────────────────┼─────────────────────────┤  │
│  │  Adversarial RedTeam │  Resource Optimizer  │  Replay Intelligence    │  │
│  │  (Minimax / COAs)    │  (Linear / Knapsack) │  (AAR / Turning Points) │  │
│  ├──────────────────────┼──────────────────────┼─────────────────────────┤  │
│  │  Federated Command   │  Agent Swarm Runtime │  Workflow State Engine  │  │
│  │  (Multi-Theater Sync)│  (Cognitive Agents)  │  (Deterministic FSM)    │  │
│  └──────────────────────┴──────────────────────┴─────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │           UNIFIED KNOWLEDGE PLATFORM (KnowledgeSynthesizer)           │  │
│  │     Dense RAG (nomic-embed) + Knowledge Graph (NX) + Memory Store     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                    DETERMINISTIC CORE & PERSISTENCE                         │
│  ┌─────────────────────────────────────┬─────────────────────────────────┐  │
│  │   Deterministic Simulation Engine   │   Dual Persistence Layer        │  │
│  │   - Fixed-step Tick Loop            │   - Production: PostgreSQL 16   │  │
│  │   - Event-Sourcing Ledger           │     + PostGIS + pgvector        │  │
│  │   - Golden Run Seed Verification    │   - Fallback: SQLite (WAL Mode) │  │
│  └─────────────────────────────────────┴─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Subsystem Breakdown

### 3.1 Deterministic Simulation Engine
- **Fixed-Time Tick Progression**: The simulation state evolves over discrete ticks (nominal rate: 1 tick = 1 second of operational time).
- **Event-Sourced Architecture**: State transitions are driven by immutable discrete events (`UnitMoved`, `ContactDetected`, `MissionStatusChanged`, `SupplyConsumed`).
- **Seed Invariant Verification**: `tests/golden/sc2_seed8841.hash` guarantees that simulation mechanics across versions produce identical event hash traces.

### 3.2 Dual-Mode Persistence & Storage
- **PostgreSQL 16 / PostGIS**:
  - Leveraged in headquarters, operational command centers, and regional hubs.
  - Native spatial indexing via `GEOMETRY(Point, 4326)` for units, threat rings, and route corridors.
  - Vector similarity search for dense doctrine chunks using `pgvector` HNSW indexes.
- **SQLite Fallback Engine**:
  - Tuned with `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;` for multi-reader concurrency.
  - Memory-mapped I/O and busy timeout set to 5000ms to eliminate SQLite lock contention during stress operations.

### 3.3 Unified Knowledge Platform & Cognitive Reasoning
- **Dense Semantic RAG**:
  - Uses `nomic-embed-text` embeddings with chunk-level metadata tagging (Doctrine ID, Classification, Chapter).
  - Validates citations and extracts verbatim corroborations before presentation in the AI Drawer.
- **Operational Knowledge Graph**:
  - NetworkX-powered in-memory directed multigraph linked with relational persistence.
  - Entities: `MISSION`, `UNIT`, `ASSET`, `INCIDENT`, `ROUTE`, `OPERATOR`, `WEATHER`, `DOCTRINE`.
  - Relations: `participates_in`, `assigned_to`, `affected_by`, `depends_on`, `caused_by`, `supports`.
  - Root-cause analysis traversals and single-point-of-failure graph evaluations.
- **Unified Query Routing**:
  - `UnifiedKnowledgePlatform` unifies graph relationships, temporal episodic memory, doctrine RAG passages, and forecast risk assessments in a single synchronous call.

### 3.4 Multi-Tier Command Federation
- Hierarchical tree federation topology:
  - **National Command Node (NCN)**: Strategic intelligence synthesis and macro theater posture.
  - **Regional Theater Command (RTC)**: Multi-corps orchestration, cross-domain allocation.
  - **Operational Command Node (OCN)**: Mission management, digital twin forecasting.
  - **Tactical Forward Node (TFN)**: Edge simulation, localized sensors, tactical routing.
- Supports partitioned consensus, heartbeat sync, and distributed state reconciliation under degraded communications (PACE plans).

### 3.5 AI Intelligence Layer & Resilience Architecture
- **Model Router**:
  - Directs lightweight classification and parsing to low-latency local models.
  - Routes complex multi-factor strategic analysis to heavy reasoning engines.
  - Degrades to grounded deterministic rule engines (`RuleGroundedFallbackProvider`) if model workers disconnect.
- **Circuit Breaker System**:
  - Wraps all external I/O and compute-heavy services.
  - States: `CLOSED` (nominal), `OPEN` (diverted to fallback), `HALF_OPEN` (probing recovery).
- **High-Throughput Caching**:
  - In-memory thread-safe LRU cache with monotonic sequence tracking and expiration TTLs.

---

## 4. Data Flow Architecture

### 4.1 Telemetry Ingestion & Live Track State
```text
Sensor / AIS / ADS-B / Vision Detection
        │
        ▼
Stream Batch Processor (ScalabilityManager)
        │
        ▼
PostGIS Persistence & Event Ledger
        │
        ├───────────────────────────────┐
        ▼                               ▼
Authoritative Sim Tick Loop      WebSocket Broadcaster
        │                               │
        ▼                               ▼
Knowledge Graph Entity Sync      Operator War Room UI
```

### 4.2 Mission Planning & Execution Flow
```text
Operator Request
        │
        ▼
Tactical Route Planner & Red Team Analysis
        │
        ▼
Draft Mission Created (Status: DRAFT)
        │
        ▼
Human-in-the-Loop Approval Gate (HTTP 403 / PermissionError if unauthenticated)
        │
        ▼ [Approved with operator ID]
Mission Transitioned to EXECUTION
        │
        ▼
Deterministic Execution by Agent Swarm / Units
```

---

## 5. Security & Isolation Invariants

1. **Authentication & RBAC**: Every command endpoint verifies the calling principal's security clearance and operational role (`COMMANDER`, `OPERATOR`, `INTELLIGENCE_ANALYST`, `AUDITOR`).
2. **Audit Logging**: Every mutation, approval, and override is written to an append-only audit ledger with cryptographic SHA-256 signatures.
3. **Decoupled Simulation Sandbox**: Predictive rollouts run on deep-copied world states in memory; pointer mutations to live state are strictly prohibited by runtime assertions.
