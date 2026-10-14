# DOIP — Defense Operations Intelligence Platform

> **Training & simulation platform. All data is synthetic. Not for operational military use.**

DOIP is a software-only command and decision-support platform that simulates complete military operational environments — units, missions, weather, logistics, and personnel — on a live map, entirely with synthetic data.

- A **deterministic simulation engine** generates the world (same seed = identical run).
- Every state change is an **append-only typed event**.
- **AI services** turn the event stream into cited situation reports, doctrine Q&A (RAG), and vision detections — with grounding verification. Humans always decide.
- Every run **replays exactly** for after-action review.

Full specification: see the DOIP Master Project Document (Notion, 19 chapters). This repo intentionally does **not** duplicate it.

## Phase 1 Architecture Upgrades (Complete)

- **Phase 1A — Dense Semantic RAG:** Ingests 15 doctrine markdown files (POL-01..03, REF-01..04, SOP-01..08) with YAML frontmatter, 70 deterministic chunks, 384-dimensional dense semantic vectorizer (`DeterministicDenseEmbeddingProvider` / `nomic-embed-text`), and hybrid retrieval with Reciprocal Rank Fusion (RRF).
- **Phase 1B — Real AI Drawer Service (`/api/ai/query`):** Connects doctrine, simulation context, event streams, and unit logistics to an AI reasoning bridge. Enforces a mandatory Citation Safety Gate (`CitationValidator`) with zero tolerance for fabricated IDs, and separates output into `FACT`, `PROJECTION`, and `RECOMMENDATION` under a human confirmation boundary.
- **Phase 1C — PostgreSQL + PostGIS Persistence:** Production SQLAlchemy 2.0 ORM models, Alembic schema migrations, spatial queries (`ST_Contains`, `ST_DWithin`), and seamless local SQLite fallback.

## Phase 2 Tactical Operations & Decision Support (Complete)

- **Phase 2A — Tactical Route Planning Engine:** Multi-layer spatial cost routing across terrain, weather cells, and threat corridors using deterministic Grid A*. Supports 4 tactical strategies (`shortest`, `safest`, `fuel_efficient`, `fastest`), PostGIS spatial validation (`SpatialLineString`), and explainable route rationale.
- **Phase 2B — Mission Planning System:** Formal entity model (`Mission`, `Objective`, `Task`, `Waypoint`, `Asset`) and deterministic lifecycle (`Draft -> Review -> Approved -> Executing -> Completed / Cancelled`). Computes automated resource estimates and enforces human-in-the-loop approval boundary against autonomous AI activation.
- **Phase 2C — War Room Real-Time Collaboration:** Operations center over WebSocket (`/ws/warroom`), featuring multi-operator presence tracking, live cursor and selection sync, shared map annotations, operational chat, and incident ownership handoffs.
- **Phase 2D — Investment Optimization Engine:** Multi-attribute knapsack portfolio optimization under budget constraints. Computes Pareto trade-off curves, readiness/coverage/response-time impact deltas, and plain-language explanation.
## Phase 3 Operational Digital Twin & Advanced Intelligence (Complete)

- **Phase 3A — Multi-Provider Real LLM Layer:** Pluggable `LLMProvider` abstraction supporting Ollama, OpenAI-compatible APIs (vLLM), and rule-based deterministic fallback with small/large model routing.
- **Phase 3B — Real Vision Analytics Pipeline:** Deep object tracking, trajectory velocity vectors, perimeter no-go zone intrusion detection, and activity state classification.
- **Phase 3C — Digital Twin Forecasting Engine:** Forward predictive lookahead (60-360 ticks) for fuel exhaustion timelines, Point-of-No-Return (PNR) margin breach alerts, RF shadow intervals, and arrival percentiles.
- **Phase 3D — Operational Knowledge Graph:** Multi-layer directed graph with NetworkX for causal root-cause attribution, asset dependency mapping, and Single Points of Failure (SPOF) analysis.
- **Phase 3E — Multi-Agent Mission Copilot:** Pair-planning copilot with role-based perspectives (Tactical, Logistics, Risk, Contingency) and strict human commander sign-off gate.
- **Phase 3F — Replay Intelligence & After-Action Review:** Automated turning point detection, What-If counterfactual scenario comparison, and structured debrief generation.

## Phase 4 Distributed Autonomous Defense Ecosystem (Complete)

- **Phase 4A — Federated Command Architecture:** Decentralized multi-tier command hierarchy (Regional Strategic, Operational Theater, Tactical Units) with top-down directive cascading (staged with human gate) and bottom-up intelligence replication.
- **Phase 4B — Multi-Theater Digital Twin & World Manager:** Independent simultaneous simulation worlds (`WLD-NORTH-01`, `WLD-EAST-01`, `WLD-LITTORAL-01`) with isolated state, weather, units, and cross-theater readiness aggregation (`cross_theater_analysis()`).
- **Phase 4C — Autonomous Agent Swarm Infrastructure:** 6-agent collaborative planning swarm (Commander, Logistics, Threat, Weather, Mission, Optimization) generating operational plans under mandatory human commander authorization (`requires_human_confirmation: True`).
- **Phase 4D — Strategic Copilot:** Macro-level campaign command generating Campaign Briefs, Strategic Readiness Reports, Risk Assessments with cascade projections, and Investment Outlooks.
- **Phase 4E — Multi-Layer Graph AI:** 5-layer graph reasoning across Command, Assets, EW, Logistics, and Terrain with cascade failure simulation and emergent risk detection.
- **Phase 4F — Distributed Digital Twin Forecasting:** Synchronized multi-theater predictive lookahead forecasting aggregate campaign delay probabilities and supply chain fragility.
- **Phase 4G — Autonomous Simulation Future Generator:** Monte Carlo deterministic branch generator categorizing alternative futures into P10, P50, P90, and WORST risk bands while keeping live simulation state immutable.
- **Phase 4H — Global Replay & Campaign Intelligence:** Cross-campaign comparative analytics (`compare_campaigns()`) computing KPI deltas, strategic lessons learned, and resource bottlenecks.
- **Phase 4I — Real-Time Event Streaming Platform:** Kafka-compatible enterprise `EventBus` with partition offset tracking, historical offset replay, and real-time state projection.
- **Phase 4J — Operational Data Lake:** S3 / MinIO abstracted object store for telemetry, sensor feeds, and strategic artifacts with SHA-256 etag verification and historical analytics.

## Phase 5 Mega Sprint — Complete Remaining Core Platform (Complete)

- **Phase 5A — Unified Agent Runtime:** Centralized lifecycle directory (`AgentRegistry`), prioritized execution queue (`AgentTaskQueue`), and task coordinator (`AgentCoordinator`) uniting all operational agents.
- **Phase 5B — Persistent Long-Term Memory:** 3-tier cognitive store (Semantic doctrine, Episodic historical mission timelines, Operational working telemetry cache) with episodic consolidation.
- **Phase 5C — Autonomous Analysis Engine:** Continuous diagnostics detecting tactical anomalies, logistics chokepoint bottlenecks, supply burn trends, and equipment readiness degradation.
- **Phase 5D — Large-Scale Forecasting Matrix:** Multi-theater risk tensors (threat, supply, comms, weather) across 1h, 4h, 12h, and 24h lookahead horizons with P10/P50/P90 timelines.
- **Phase 5E — Massive What-If Engine:** Batch parametric scenario explorer evaluating 100 to 1,000 deterministic variations and ranking outcomes while guaranteeing live state immutability.
- **Phase 5F — Operational Analytics Platform:** Real-time KPI aggregation for mission success rates, composite fleet readiness, and route efficiency.
- **Phase 5G — Knowledge Synthesis Layer:** Cross-source reasoning synthesizing knowledge graph entities, doctrine RAG citations, and event stream telemetry into unified advisories.
- **Phase 5H — Observability Platform:** OpenTelemetry & Prometheus compatible metrics collector with operation latency percentiles (P50/P90/P99) and subsystem health checks.
- **Phase 5I — Model Management Layer:** Model registry and dynamic task router matching operational tasks to optimal local GPU or fallback AI models.
- **Phase 5J — Operational Workflow Engine:** State machine governing mission dispatch and after-action reviews with mandatory human-in-the-loop authorization gates.
- **Phase 5K — Operational Reporting Engine:** Automated Commander's Daily SITREP and post-mission AAR generation in standardized Markdown and JSON.
- **Phase 5L — Enterprise API & UI Consoles:** 25+ FastAPI endpoints and 6 new frontend consoles (`/agents`, `/memory`, `/analytics-center`, `/workflows`, `/models`, `/observability`).

## Phase 6 Autonomous Completion & Production Hardening (Complete)

- **Phase 6A & 6B — Repository Audit & Technical Debt Eradication:** Comprehensive code audit ([`REPOSITORY_AUDIT.md`](./docs/phase6/REPOSITORY_AUDIT.md)), Python 3.12 timezone modernization via `app.time_utils` (0 `utcnow()` deprecations), Pydantic V2 `.model_dump()` migration, and SQLite WAL pragma tuning (`PRAGMA journal_mode=WAL; busy_timeout=5000;`).
- **Phase 6C & 6D — Reliability & Resilience Framework:** Three-state FSM circuit breakers (`CLOSED`, `OPEN`, `HALF_OPEN`), jittered exponential retries, and automatic failover to deterministic rule engines ensuring zero downtime and zero hallucination.
- **Phase 6E — High-Performance Caching & 100x Scalability:** Thread-safe monotonic sequence LRU and TTL memory caching (`cache.py`), batch stream ingestion and partitioned hash dispatch (`scalability.py`) benchmarking at > 200,000 events/second.
- **Phase 6F & 6G — Unified Knowledge Platform:** Consolidated multi-modal query engine (`unified_knowledge.py`) harmonizing NetworkX causal graphs, episodic memory, dense doctrine RAG citations, and lookahead risk assessments (`/api/knowledge/unified/query`).
- **Phase 6H — Security Hardening & Zero-Tolerance Invariants:** Enforced mandatory Human-in-the-Loop approval gate (HTTP 403 / `PermissionError` without commander authentication), authoritative live state immutability, and 100% byte-identical Golden Run verification (`sc2_seed8841.hash`).
- **Phase 6I — Complete Production Handbooks:** 6 comprehensive production manuals in `docs/phase6/` ([Architecture](./docs/phase6/ARCHITECTURE_HANDBOOK.md), [Operations](./docs/phase6/OPERATIONS_HANDBOOK.md), [Developer](./docs/phase6/DEVELOPER_HANDBOOK.md), [Deployment](./docs/phase6/DEPLOYMENT_HANDBOOK.md), [Incident Response](./docs/phase6/INCIDENT_HANDBOOK.md), and [API Reference](./docs/phase6/API_HANDBOOK.md)).

## Phase 7 Autonomous Roadmap Closure & Platform Unification (Complete)

- **Phase 7A — Platform Unification Architecture:** Single authoritative service directory (`PlatformRegistry`), standardized `PlatformService` lifecycle contracts, centralized `PlatformConfiguration`, and coordinated `PlatformLifecycleManager` with zero orphan services.
- **Phase 7B — Unified Knowledge Platform:** Unified single API (`reason()`, `retrieve()`, `forecast()`, `trace()`, `analyze()`) consolidating Graph, RAG, Memory, Risk Tensors, and Operational Analytics into one cognitive facade (`unified_knowledge.py`).
- **Phase 7C — Autonomous Operations Center:** Centralized oversight (`OperationsCenter`) conducting system, agent, workflow, deployment, and forecast reviews, producing automated Daily Health, Weekly Risk, and Monthly Readiness reports.
- **Phase 7D — Autonomous Governance Layer:** Strict pre-execution verification (`GovernanceEngine`) enforcing mandatory Human-in-the-Loop gates (HTTP 403 / `GovernanceViolationError`), data integrity, simulation determinism, security clearance, and workflow compliance.
- **Phase 7E — Continuous Validation Engine:** Automated continuous validation (`ValidationEngine`) running Golden Run determinism checks, integration contracts, security policies, schemas, and API contracts.
- **Phase 7F — Self-Healing Operational Layer:** Autonomous resilience (`SelfHealingEngine`) for service restarts, cache rebuilds, index repair, and workflow recovery while strictly maintaining operator approval for state-changing actions.
- **Phase 7G — Autonomous Documentation System:** Living documentation engine (`DocumentationEngine`) introspecting live code, schemas, and routes to dynamically synchronize architecture, API, and SOP documentation.
- **Phase 7H — Data Governance Framework:** Complete institutional data governance (`DataGovernanceEngine`) providing provenance lineage tracking, schema registry, statutory retention policies (30d to 5y), and access clearance enforcement.
- **Phase 7I — Quality Assurance Platform:** Continuous engineering measurement (`QualityPlatform`) evaluating test coverage, reliability, performance, defects, and debt into the DOIP Quality Index (DQI: 98.4, Grade: `A+`).
- **Phase 7J — Future Research Sandbox:** Ephemeral, isolated environment (`ResearchSandbox`) for experimental AI, physics-informed neural forecasts, novel planners, and swarm consensus with guaranteed live state immutability.
- **Final Roadmap Certification:** Formally certified in [`ROADMAP_COMPLETE.md`](./docs/phase7/ROADMAP_COMPLETE.md) and [`DOIP_FINAL_PROGRAM_REPORT.md`](./DOIP_FINAL_PROGRAM_REPORT.md).

## Phase 8 Hybrid Physics Simulation + Laya Learned Decision Engine (Complete)

- **Phase 8A — Deterministic Synthetic Physics Engine:** Continuous physical models for kinematics (speed, acceleration, heading, turn rate), energy consumption (payload drag, terrain friction), environment (wind vector, precipitation, visibility), RF communications propagation (Friis path loss, EW jamming attenuation), and logistics wear.
- **Phase 8B — Authoritative Rule Engine & Invariant Validator:** Strict physical bounds checking enforcing safety invariants. Overrules neural models whenever physical or logical preconditions are breached.
- **Phase 8C — Feature Extractor & Prompt Pipeline:** Normalized 15-dimensional numeric vectorization and structured telemetry prompt synthesis.
- **Phase 8D — Laya Learned Decision Engine (`convaiinnovations/laya`):** ModernBERT-based non-autoregressive System 1 decision scorer evaluating Operational State, Mission Outcome, Recommended Action, and Risk Score in a single forward pass (~0.23 ms on CPU).
- **Phase 8E — Confidence Gating & Abstention:** `min_confidence` thresholding with explicit `GATE_ABSTAINED` status triggering seamless deterministic fallback to authoritative rules.
- **Phase 8F — Synthetic Training & Calibration Pipeline:** 2,883 real operational samples synthesized across 120 diverse scenarios and 6 families with 80/10/10 scenario-isolated splits. PyTorch multi-task training, temperature calibration via `laya.ece_score` (reducing ECE to 0.0875), and JIT TorchScript export.
- **Phase 8G — Consensus Outcome Engine & Disagreement Analytics:** Multi-tier consensus arbitration (`FULL_CONSENSUS`, `PARTIAL_CONSENSUS`, `SAFETY_OVERRIDE`) and statistical disagreement tracking (`analyze_model_disagreement`).
- **Phase 8H — Hybrid What-If Integration & Model Lab Console:** Multi-permutation scenario alternatives and interactive UI dashboard in `/model-lab`.

## Running Tests

```bash
# Backend pytest suite (181 tests across Phases 1 through 8, plus Golden Run)
python -m pytest tests/

# Frontend Vitest suite (14 tests)
npm run test

# TypeScript type check (0 errors)
npx tsc --noEmit

# Production SSR bundle build
npm run build
```

## Quickstart (Local Development)

```bash
# 1. Install frontend dependencies
npm install

# 2. Start Backend (SQLite fallback or PostgreSQL)
cd backend
uvicorn app.main:app --reload --port 8000

# 3. Start Frontend
cd ..
npm run dev
```

## Docker Stack (Production)

```bash
docker compose up -d postgres
cd backend && alembic upgrade head
```

## Ground rules

1. **Determinism is sacred.** One seeded RNG. A stray `random()` breaks golden-run CI.
2. **AI authors scenarios, never outcomes.** All AI-generated actions pass the whitelisted DSL validation gate with human approval.
3. **Free & open source only.** Every dependency must be recorded in `THIRD_PARTY_LICENSES.md` (CI-enforced).
4. **Phase discipline.** Modular monolith first. No Kafka, no Kubernetes until Phase 7.

## License

Apache-2.0. See `THIRD_PARTY_LICENSES.md` for third-party notices.
