# DOIP Phase 1 — Architecture Specification

**Author:** ARCHITECT Agent (ECC Orchestration Team)  
**Target:** DOIP Phase 1 Milestone  
**Scope:** Dense RAG + Real AI Drawer + PostgreSQL/PostGIS Architecture  
**Status:** Approved for Implementation  

---

## 1. System Overview & Invariants

DOIP is a deterministic browser-based defense operations and simulation platform.
Phase 1 enhances DOIP with three mission-critical capabilities without perturbing core invariants:
1. **Dense Semantic RAG**: Moving beyond simple term-overlap to deterministic chunking, semantic vector embeddings, and hybrid retrieval.
2. **Real AI Backend Service**: Replacing hardcoded regex/heuristics in `AiDrawer.tsx` with a multi-context AI reasoning engine backed by a strict citation safety validation pipeline.
3. **Enterprise PostgreSQL/PostGIS Persistence**: Upgrading development SQLite to an asynchronous/synchronous SQLAlchemy + Alembic PostgreSQL/PostGIS architecture with spatial capabilities, while retaining an automatic SQLite fallback for lightweight development.

### Core Invariants (AGENTS.md & Chapter 13 Rules)
- **Determinism is the Product**: The simulation engine (`backend/app/engine.py`, `backend/app/prng.py`) MUST NEVER call unseeded RNG, system wall-clock, or unordered sets. The golden run hash (`tests/golden/sc2_seed8841.hash`) MUST NOT drift.
- **AI-Service Mutation Boundary**: The LLM may observe simulation states, synthesize sitreps, project trends, and recommend tactical courses of action. The LLM **CANNOT directly mutate simulation or world state**. All actions must conform to the whitelisted DSL and require human confirmation.
- **Citation Safety & Non-Fabrication**: The LLM is never trusted to invent citations. Every factual assertion must be verified by the Citation Validator against retrieved doctrine chunk IDs or active simulation event IDs. Unverifiable citations are rejected or flagged.

---

## 2. Component Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (TanStack/React)                       │
│                                                                        │
│   ┌────────────────────┐                   ┌───────────────────────┐   │
│   │    AiDrawer.tsx    │                   │   15 Tactical Screens │   │
│   │  (SITREPS/ASK/WIF) │                   │  (Map, Sitrep, etc.)  │   │
│   └─────────┬──────────┘                   └───────────────────────┘   │
│             │                                                          │
│             │ calls src/services/ai.ts                                 │
└─────────────┼──────────────────────────────────────────────────────────┘
              │ HTTP POST /api/ai/query
              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       BACKEND (FastAPI Monolith)                       │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ AI Service Orchestrator (backend/app/ai_service.py)               │  │
│  │   1. Query Understanding & Routing                               │  │
│  │   2. Context Assembly:                                           │  │
│  │      - Doctrine Retrieval (RAG Service)                          │  │
│  │      - Live Simulation State & Telemetry (Session/Engine)        │  │
│  │      - Recent Sim Events & Alerts                                │  │
│  │      - Incidents & Logistics Data                                │  │
│  │   3. Prompt Construction & LLM Inference (Local/Ollama/Fallback) │  │
│  │   4. Strict Citation Validator (Grounded Check)                  │  │
│  │   5. Structured Output (FACT / PROJECTION / RECOMMENDATION)      │  │
│  └──────────────────┬───────────────────────────────────────────────┘  │
│                     │                                                  │
│         ┌───────────┴───────────┐                                      │
│         ▼                       ▼                                      │
│  ┌──────────────┐       ┌────────────────┐                             │
│  │ RAG Pipeline │       │ Sim & Session  │                             │
│  │ (app/rag.py) │       │ (app/engine.py)│                             │
│  └──────┬───────┘       └────────────────┘                             │
│         │                                                              │
│         ▼                                                              │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Persistence Layer (backend/app/db.py & app/models.py)            │  │
│  │ SQLAlchemy 2.0 + Alembic Migrations                              │  │
│  │ Dual Engine: PostgreSQL + PostGIS (primary) | SQLite (fallback)  │  │
│  └──────────────────┬───────────────────────────────────────────────┘  │
└─────────────────────┼──────────────────────────────────────────────────┘
                      │
                      ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     DATABASE & STORAGE INFRASTRUCTURE                  │
│                                                                        │
│   ┌─────────────────────────────┐   ┌──────────────────────────────┐   │
│   │     PostgreSQL 16 + PostGIS │   │     Vector Storage           │   │
│   │  (Spatial tables & indices) │   │  (pgvector / Qdrant/Memory)  │   │
│   └─────────────────────────────┘   └──────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Stable Interface Contracts

The following public interfaces are consumed across DOIP and must remain backwards-compatible:
1. **Simulation Engine API**:
   - `WorldState` schema (`units`, `weather`, `incidents`, `alerts`, `tick`, `seed`).
   - `SimEvent` schema (`id`, `type`, `severity`, `entityId`, `tick`, `payload`).
2. **Existing Database Interface (`app/db.py`)**:
   - `save_run(run_id, seed, scenario_id, ticks, events, log, world_json)`
   - `get_run(run_id)`
   - `list_runs()`
   - `record_audit(actor, action, detail)`
   - `save_whatif_result(...)`
   - `save_custom_scenario(...)`
   - `save_user(...)`, `get_user(...)`
3. **Existing RAG Interface**:
   - `query_rag(query, recent_events)`
   - `verify_grounding(text, known_events, known_docs)`
   - `corpus_index.docs`
4. **AI Endpoint (`/api/ai/query`)**:
   - Accepts: `{ "query": str, "run_id": Optional[str], "tick": Optional[int] }`
   - Returns: Structured answer containing claims, citations, grounding validation, and course of action recommendations.

---

## 4. Agent Ownership & Modifiable Files Matrix

To prevent cross-agent collisions, file modifications are partitioned:

| Agent | Permitted File Modifications | Read-Only References |
| :--- | :--- | :--- |
| **ARCHITECT** | `docs/phase1/*` | All files |
| **DATABASE-ENGINEER** | `backend/app/db.py`, `backend/app/models.py`, `backend/alembic/*`, `alembic.ini`, `docker-compose.yml`, `backend/requirements.txt` | `backend/app/sim_types.py` |
| **RAG-ENGINEER** | `backend/app/rag.py`, `backend/app/vector_store.py`, `backend/app/embeddings.py` | `corpus/*`, `tests/test_rag.py` |
| **AI-BACKEND-ENGINEER** | `backend/app/ai_service.py`, `backend/app/main.py` (ai routes only) | `backend/app/engine.py`, `backend/app/session.py` |
| **FRONTEND-INTEGRATION-ENGINEER** | `src/components/shell/AiDrawer.tsx`, `src/services/ai.ts`, `src/lib/api.ts` | `src/sim/types.ts` |
| **TEST-ENGINEER** | `tests/test_*.py`, `src/**/*.test.ts`, `vitest.config.ts`, `package.json` | All files |
| **SECURITY/REVIEW-ENGINEER** | `docs/phase1/SECURITY_AUDIT.md` | All files |

---

## 5. Conflict Prevention Strategy

1. **Shared Route Registration**: `backend/app/main.py` is touched only by AI-BACKEND-ENGINEER to register `/api/ai/query` via an APIRouter.
2. **Dual-Mode Database**: `db.py` will inspect `DATABASE_URL`. If PostgreSQL is configured, it leverages SQLAlchemy engine and models; if SQLite or offline, it routes to SQLite with identical function signatures.
3. **Deterministic Embeddings**: Embeddings are abstracted behind `EmbeddingProvider`. A local fast deterministic provider is bundled by default so testing never requires network calls or GPU.
