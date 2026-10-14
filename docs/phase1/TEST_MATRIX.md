# DOIP Phase 1 — Comprehensive Test Matrix

**Author:** TEST-ENGINEER Agent (ECC Orchestration Team)  
**Harness:** Pytest (Backend) + Vitest (Frontend)  
**Status:** Approved for Implementation  

---

## 1. Test Suite Architecture

| Test Domain | Target Suite | Runner | Coverage Criteria |
| :--- | :--- | :--- | :--- |
| **Doctrine Chunking** | `tests/test_phase1_chunking.py` | Pytest | Determinism, zero random IDs, frontmatter parsing, section breakdown |
| **Vector Retrieval** | `tests/test_phase1_rag.py` | Pytest | Cosine similarity, hybrid RRF, top-k ranking, metadata retention |
| **Citation Safety** | `tests/test_phase1_citation.py` | Pytest | Fabrication rejection, valid source verification, claim verification |
| **AI Query Endpoint** | `tests/test_phase1_ai_service.py`| Pytest | `/api/ai/query`, context assembly, fail-soft fallback, malformed input |
| **Database & Migrations**| `tests/test_phase1_database.py` | Pytest | SQLAlchemy models, Alembic upgrades, PostGIS types, SQLite fallback |
| **Core Invariants** | `tests/test_determinism.py`, `tests/test_golden_run.py` | Pytest | SC-2 seed 8841 golden hash freeze, PRNG immutability |
| **Frontend AI Service** | `src/services/ai.test.ts` | Vitest | Typed client, payload serialization, error resilience |
| **Frontend AI Drawer** | `src/components/shell/AiDrawer.test.tsx` | Vitest | Tab navigation, citation chip rendering, FACT/PROJECTION tags, fallback UI |

---

## 2. Gate Criteria & Acceptance Benchmarks

1. **Golden Run**:
   - `python -m pytest tests/test_golden_run.py` must pass with zero hash delta.
2. **Corpus Coverage**:
   - All 15 doctrine documents (POL-01..03, REF-01..04, SOP-01..08) must chunk deterministically into >= 50 semantic sections.
   - Retrieval queries on key doctrine terms (e.g., "convoy escort", "rules of engagement", "comms silence") must retrieve the authoritative document in top-3 results with score >= 0.70.
3. **Citation Safety**:
   - Fabricated IDs (e.g. `[SOP-99]`, `[INC-9999]`) must be flagged as unverified and excluded from verified citations.
4. **Database Resilience**:
   - When PostgreSQL is running, tables use proper constraints and PostGIS geometry.
   - When offline or SQLite is active, all application CRUD queries execute successfully without error.
5. **Frontend Health**:
   - `npx vitest run` must execute with 100% passing tests.
   - AI Drawer seamlessly renders LLM answers and degrades gracefully if backend returns fallback.
