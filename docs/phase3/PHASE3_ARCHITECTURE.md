# Phase 3 Architecture: Operational Digital Twin & Advanced Intelligence Layer

**Program:** Defense Operations Intelligence Platform (DOIP)  
**Author:** CHIEF_ARCHITECT (ECC Multi-Agent Execution Protocol)  
**Phase:** 3  
**Status:** Approved  

---

## 1. System Topology Overview

Phase 3 extends DOIP from a tactical command simulator into a complete Operational Digital Twin platform. The system operates as six interconnected layers:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             BROWSER FRONTEND                                │
│   Knowledge Graph Explorer │ Mission Copilot │ Forecast Viewer │ Vision UI  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ REST / WebSocket
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                            FASTAPI CORE LAYER                               │
│  /api/llm/*  /api/vision/*  /api/digital-twin/*  /api/graph/*  /api/copilot/*   │
└──────┬───────────────┬────────────────┬─────────────────┬─────────────┬─────┘
       │               │                │                 │             │
┌──────▼─────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌───────▼──────┐  ┌───▼───────┐
│ Real LLM   │  │ Real Vision │  │ Digital Twin│  │ Knowledge    │  │ Replay    │
│ Provider   │  │ Analytics   │  │ Forecast    │  │ Graph (Causal│  │ Intel &   │
│ Engine     │  │ Pipeline    │  │ Engine      │  │ NetworkX)    │  │ Run Diff  │
│ (Ollama/   │  │ (YOLO/      │  │ (Monte      │  │              │  │           │
│ OpenAI/vLLM│  │ RT-DETR)    │  │ Carlo Look- │  │ Root Cause & │  │ Turning   │
│ + Router)  │  │             │  │ ahead)      │  │ Dependency   │  │ Points    │
└──────┬─────┘  └──────┬──────┘  └──────┬──────┘  └───────┬──────┘  └───┬───────┘
       │               │                │                 │             │
       └───────────────┴────────────────┼─────────────────┴─────────────┘
                                        │
┌───────────────────────────────────────▼─────────────────────────────────────┐
│                    PERSISTENCE & SPATIAL ENGINE                             │
│   PostgreSQL + PostGIS (primary) / SQLite Dual-Mode Fallback (dev)          │
│   knowledge_graph_nodes │ vision_detections │ forecast_runs │ copilot_sess  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Subsystem Interfaces and Data Contracts

### 2.1 Phase 3A: Real LLM Intelligence Layer
- **Interface:** `LLMProvider` abstract base class with implementations:
  - `OllamaProvider` (local models: `llama3`, `mistral`, `qwen2.5`)
  - `OpenAIProvider` (OpenAI-compatible APIs, vLLM endpoints)
  - `RuleGroundedFallbackProvider` (deterministic rule-grounded fallback)
- **Model Routing:**
  - *Small Model* (e.g. `qwen2.5:3b`, `llama3.2:3b`): Intent classification, entity extraction, metadata tagging.
  - *Large Model* (e.g. `llama3:8b`, `mistral:7b`): Strategic reasoning, C2 situation reports, causal explanation.
- **Methods:** `generate()`, `stream()`, `summarize()`, `classify()`, `reason()`.

### 2.2 Phase 3B: Real Vision Analytics Pipeline
- **Interface:** `VisionProvider` with detection, classification, and tracking capabilities:
  - Detects vehicles, UAVs, personnel, obstacles, and environmental cells.
  - Multi-frame tracking assigning persistent `track_id`s with trajectory histories.
  - Perimeter / zone intrusion detection using PostGIS spatial containment.
  - Activity state analysis: `nominal`, `in_transit`, `stalled`, `intruding`, `suspicious`.
- **Persistence:** Tables `vision_detections` and `vision_tracks`.

### 2.3 Phase 3C: Digital Twin Forecasting Engine
- **Interface:** `DigitalTwinForecaster.forecast(horizon_hours, confidence, scenario_id)`:
  - Takes live world state + historical events + mission waypoints + weather cells.
  - Runs predictive multi-tick lookahead (60 to 360 ticks).
  - Produces:
    - Fuel exhaustion timelines (per unit and depot).
    - Communications degradation zones and RF silence windows.
    - Threat escalation probabilities.
    - Expected mission transit delay percentiles ($P_{10}, P_{50}, P_{90}$).
  - Safety Boundary: Forecasts are read-only projections and NEVER mutate simulation state.

### 2.4 Phase 3D: Knowledge Graph & Causal Analysis
- **Model:** NetworkX in-memory directed multi-graph persisted to relational tables:
  - `knowledge_graph_nodes` (id, entity_type, label, properties)
  - `knowledge_graph_edges` (source_id, target_id, relation_type, weight, properties)
- **Entities:** Mission, Unit, Asset, Incident, Route, Operator, Weather, Doctrine.
- **Relations:** `participates_in`, `assigned_to`, `affected_by`, `depends_on`, `caused_by`, `supports`.
- **Analysis Functions:**
  - `find_root_cause(incident_id)`: Traverses incoming causal edges to identify origin trigger (e.g., weather squall -> fuel leak -> stalled unit).
  - `find_dependencies(mission_id)`: Traverses outgoing dependency edges to identify single-point-of-failure assets.
  - `trace_incident_chain(incident_id)`: Returns full graph path from initiator to impact.

### 2.5 Phase 3E: Multi-Agent Mission Copilot
- **Interactive Multi-Agent Team:**
  - `TacticalCoordinatorAgent`: Synthesizes mission goals and constraints.
  - `LogisticsEvaluatorAgent`: Evaluates fuel, supply depots, and maintenance margins.
  - `RiskAssessorAgent`: Evaluates threat corridors and weather exposure.
  - `ContingencyPlannerAgent`: Formulates alternative egress routes and emergency branches.
- **Output:** Comprehensive Mission Copilot Brief (Proposal, Assets Required, Fuel Requirements, Risk Analysis, Threat Analysis, Alternative Routes, Contingencies).
- **Human Approval Boundary:** Copilot proposals remain staged (`proposed`); human operator confirmation is strictly required to execute or advance.

### 2.6 Phase 3F: Replay Intelligence & After Action Review
- **Timeline Intelligence:** Evaluates completed or recorded simulation runs:
  - Critical turning points (events that altered trajectory or escalated severity).
  - Missed opportunities (alternative actions that would have preserved KPIs).
  - Root cause attribution for mission failures or delays.
- **Run Comparison (What-If Diff):**
  - Compares Baseline Run vs Branch Run.
  - Computes KPI deltas, trajectory divergence distances, and incident outcome comparisons.
- **Persistence:** Table `replay_reports`.

---

## 3. Security & Operational Invariants

1. **Zero State Mutation:** No LLM, forecaster, copilot, or graph query may invoke direct mutation functions on the simulation or database without human confirmation.
2. **Deterministic Golden Run:** Simulation math and seed generation must remain 100% byte-identical to `tests/golden/sc2_seed8841.hash`.
3. **DSL Whitelist Adherence:** Any suggested automated actions must strictly conform to `dsl_parser.py` action vocabulary.
