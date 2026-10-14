# DOIP Developer Handbook
## Defense Operations Intelligence Platform — Engineering & Contributor Guide
### Phase 6 Production Hardening & Codebase Standards

---

## 1. Engineering Principles & Invariants

All developers contributing to the DOIP platform must strictly adhere to three non-negotiable architectural invariants:

1. **Deterministic Simulation Invariant**:
   - The simulation loop must remain mathematically pure.
   - **Never** use non-seeded pseudo-random numbers (`random.random()`, `uuid.uuid4()`) or system wall clocks (`time.time()`, `datetime.now()`) inside the simulation tick logic.
   - All state progression must be driven exclusively by the simulation tick counter and scenario seed.
   - Verification: `pytest tests/test_golden_run.py` must produce zero hash drift against `tests/golden/sc2_seed8841.hash`.

2. **Authoritative State Immutability**:
   - Predictive lookaheads, stochastic What-If runs, and Red Team explorations must never mutate live simulation objects in memory.
   - Always deep-copy or clone world state into decoupled ephemeral containers before running branch projections.

3. **Mandatory Human-in-the-Loop Gate**:
   - Any API or service that advances a mission to `execution` or triggers kinetic actions must verify the `approved_by` operator identity.
   - Unauthorized attempts must raise a `PermissionError` and return `HTTP 403 Forbidden`.

---

## 2. Codebase Organization

```text
DOIP/
├── backend/
│   ├── alembic/                 # Database schema migrations
│   │   └── versions/            # Version migration scripts
│   ├── app/
│   │   ├── main.py              # FastAPI application, route registration, lifespan
│   │   ├── db.py                # Database engine, session maker, helper methods
│   │   ├── models.py            # SQLAlchemy 2.0 ORM data models
│   │   ├── time_utils.py        # Centralized timezone-aware UTC datetime utilities
│   │   ├── resilience.py        # Circuit breakers, retry with exponential backoff
│   │   ├── cache.py             # Monotonic LRU & TTL in-memory caching engine
│   │   ├── scalability.py       # Batch stream processors and 100x scale benchmark
│   │   ├── unified_knowledge.py # Consolidated query router (Graph + Memory + RAG)
│   │   ├── routing.py           # Tactical A* pathfinding and threat cost evaluation
│   │   ├── missions.py          # Mission DAG planning and status lifecycle
│   │   ├── warroom.py           # Real-time WebSocket collaboration hub
│   │   ├── redteam.py           # Adversarial inject generator and vulnerability scanner
│   │   ├── forecasting.py       # Digital twin multi-tick forward lookahead
│   │   ├── knowledge_graph.py   # NetworkX operational knowledge graph
│   │   ├── rag_engine.py        # Dense semantic vector search and retriever
│   │   ├── llm_provider.py      # Multi-provider LLM router & offline fallback
│   │   ├── vision_pipeline.py   # Real-time CV detection, tracking, perimeter guards
│   │   └── sim/                 # Deterministic discrete-event simulation engine
│   ├── Dockerfile               # Production container definition
│   └── requirements.txt         # Pinned backend dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # Reusable tactical UI components
│   │   ├── features/            # WarRoom, AIDrawer, TacticalMap, Replay views
│   │   ├── services/            # REST and WebSocket API client adapters
│   │   └── App.tsx              # Application entry point and layout shell
│   ├── package.json             # Frontend dependencies and scripts
│   └── vite.config.ts           # Vite bundler configuration
├── tests/                       # Pytest test suites across all phases
└── docs/                        # Architecture, handbooks, and phase specifications
```

---

## 3. Development Environment Setup

### 3.1 Prerequisites
- **Python**: 3.12+ (64-bit)
- **Node.js**: 18 LTS or 20 LTS
- **PostgreSQL**: 16+ with PostGIS and pgvector (optional for local SQLite mode)

### 3.2 Backend Setup
```bash
# Clone and enter repository
cd DOIP

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt

# Run database initialization
python -c "from app import db; db.init(); print('Database initialized')"

# Launch backend in development mode
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### 3.3 Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## 4. Coding Conventions & Standards

### 4.1 Time & Date Handling
**Do not use `datetime.datetime.utcnow()`** (deprecated in Python 3.12).
Always import utilities from `app.time_utils`:
```python
from app.time_utils import utc_now, utc_iso, parse_utc_iso

# Create current UTC timestamp string
created_at = utc_iso()

# Get timezone-aware datetime object
dt = utc_now()
```

### 4.2 Pydantic V2 Serialization
Use `.model_dump()` rather than the deprecated `.dict()`:
```python
# Correct:
data = body.model_dump() if hasattr(body, "model_dump") else body.dict()
```

### 4.3 Resilience Layer Integration
Wrap third-party network, model inference, or external storage calls in circuit breakers:
```python
from app.resilience import resilience_mgr, retry_with_backoff

# Apply circuit breaker
breaker = resilience_mgr.get_breaker("remote_vision_worker", failure_threshold=3, recovery_timeout=30.0)

@breaker
def query_remote_worker(payload: dict) -> dict:
    ...

# Apply retry with jittered exponential backoff
result = retry_with_backoff(query_remote_worker, payload, max_retries=3, base_delay=0.2)
```

### 4.4 High-Performance Caching
Cache compute-heavy lookups (e.g., Dijkstra route weights, doctrine chunk embeddings):
```python
from app.cache import cache_mgr

@cache_mgr.cached(namespace="route_planning", ttl_seconds=60.0)
def compute_route_cost(start_id: str, goal_id: str, threat_level: float) -> float:
    ...
```

---

## 5. Testing Protocol & Quality Gates

Developers must run the full validation suite prior to pushing commits or opening pull requests:

```bash
# 1. Deterministic Golden Run Verification (Mandatory Gate)
python -m pytest tests/test_golden_run.py

# 2. Complete Backend Test Matrix (148+ tests)
python -m pytest tests/

# 3. Resilience and Chaos Security Suites
python -m pytest tests/test_phase6_resilience_and_scale.py tests/test_phase6_chaos_security.py

# 4. Frontend Unit & Integration Tests
cd frontend
npm test

# 5. Frontend Production Build Check
npm run build
```

---

## 6. Database Migration Workflow

When introducing new SQLAlchemy models in `backend/app/models.py`:
1. Author the model using SQLAlchemy 2.0 declarative syntax (`Mapped`, `mapped_column`).
2. Generate an Alembic migration:
   ```bash
   alembic revision -m "add_new_operational_table"
   ```
3. Ensure the migration provides both `upgrade()` and `downgrade()` methods supporting PostgreSQL types (`JSONB`, `Geometry`) and SQLite equivalents (`JSON`, `Text`).
4. Update `backend/app/db.py` to register table creation helpers and SQLite fallbacks.
