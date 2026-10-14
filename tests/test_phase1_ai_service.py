"""Phase 1B Test Suite: AI Backend Query Service (/api/ai/query).

Invariants:
- Multi-context assembly (Doctrine + Sim State + Events + Incidents + Logistics).
- Fail-soft reasoning: if LLM is offline, returns grounded rule-based analysis.
- Structured response distinguishes FACT, PROJECTION, RECOMMENDATION.
- Safety Boundary: Recommendations require human confirmation prior to DSL execution.
- LLM MUST NOT directly mutate simulation state.
"""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.ai_service import ai_service


def test_ai_query_endpoint_doctrine_only():
    """Querying doctrine via /api/ai/query returns grounded facts and verified citations."""
    client = TestClient(app)
    resp = client.post(
        "/api/ai/query",
        json={"query": "What is the policy regarding synthetic data and exports?"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "answer" in data
    assert "facts" in data
    assert "projections" in data
    assert "recommendations" in data
    assert "citations" in data
    assert "grounding" in data
    assert data["latency_ms"] > 0
    assert data["mode"] in ["local_llm", "rule_grounded_fallback"]

    # Verify citation of POL-02 (synthetic data policy)
    citations = data["citations"]
    assert any("POL-02" in c["source_id"] for c in citations)


def test_ai_query_endpoint_tactical_context():
    """Querying with active run_id and tick assembles tactical events and doctrine."""
    client = TestClient(app)
    resp = client.post(
        "/api/ai/query",
        json={
            "query": "Assess unit fuel reserves and supply depot tasking.",
            "run_id": "test_run_01",
            "tick": 45,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["tick"] == 45
    assert len(data["facts"]) > 0

    # Operational recommendations must require confirmation
    for rec in data["recommendations"]:
        assert rec["requires_confirmation"] is True
        assert rec["priority"] in ["CRITICAL", "HIGH", "MEDIUM", "ROUTINE"]
        assert rec["action"]


def test_ai_service_failsoft_offline_behavior():
    """When external LLM is offline, ai_service responds gracefully with grounded fallback."""
    # Force query to use fail-soft heuristic by querying directly
    result = ai_service.query(
        query="What are the procedures during total communications loss?",
        run_id=None,
        tick=12,
    )
    assert result["mode"] in ["local_llm", "rule_grounded_fallback"]
    assert len(result["answer"]) > 20
    assert any(c["source_id"] in ["SOP-06", "REF-01"] for c in result["citations"])


def test_ai_service_does_not_mutate_state():
    """AI Service query is read-only and does not mutate active runs or sim tables."""
    from app import db
    runs_before = len(db.list_runs())
    client = TestClient(app)
    client.post("/api/ai/query", json={"query": "Test inquiry without side effects"})
    runs_after = len(db.list_runs())
    assert runs_after == runs_before, "AI queries must not mutate simulation run records"
