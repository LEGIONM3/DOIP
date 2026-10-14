"""Phase 6 Comprehensive Test Suite: Security Hardening & Chaos Testing.

Tests:
- Mandatory Human-in-the-Loop authorization boundary (anti-bypass guard)
- Authoritative live simulation state immutability during What-If / Forecast runs
- Unified Knowledge Platform cross-source query integration
- Phase 6 Hardening REST endpoints (resilience status, cache stats, scalability benchmarks)
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import db
from app.main import app
from app.workflow_engine import workflow_engine
from app.unified_knowledge import unified_knowledge
from app.massive_whatif import massive_whatif


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.init()


# ---------------------------------------------------------------------------
# 1. Human-in-the-Loop Security Invariant Tests
# ---------------------------------------------------------------------------
def test_ai_cannot_bypass_human_approval_gate():
    """Verify that an automated agent cannot advance a workflow to execution without operator sign-off."""
    wf = workflow_engine.create_workflow(
        workflow_type="kinetic_strike",
        title="Operation Desert Hawk Authorization",
        requires_human_confirmation=True,
    )
    assert wf["status"] == "staged"
    assert wf["approved_by"] is None

    # Hard enforcement: advance_step raises PermissionError
    with pytest.raises(PermissionError):
        workflow_engine.advance_step(wf["id"], "execution")

    # REST endpoint must return HTTP 403 Forbidden
    client = TestClient(app)
    resp = client.post(
        f"/api/workflows/{wf['id']}/advance",
        json={"next_step": "execution"},
    )
    assert resp.status_code == 403
    assert "Human authorization required" in resp.json()["detail"]

    # Once authenticated operator approves, transition is permitted
    app_res = client.post(
        f"/api/workflows/{wf['id']}/approve",
        json={"operator_id": "OPERATOR-SEC-09"},
    )
    assert app_res.status_code == 200
    assert app_res.json()["approved_by"] == "OPERATOR-SEC-09"

    # Now advancing is permitted
    adv_res = client.post(
        f"/api/workflows/{wf['id']}/advance",
        json={"next_step": "completed"},
    )
    assert adv_res.status_code == 200


# ---------------------------------------------------------------------------
# 2. Live Authoritative State Immutability Tests
# ---------------------------------------------------------------------------
def test_whatif_preserves_live_state_immutability():
    """Verify that running 100 scenario variations in decoupled memory leaves authoritative state unchanged."""
    authoritative_scenario = {
        "id": "SC-AUTH-01",
        "name": "Primary Authoritative Baseline",
        "units": [{"id": "U-1", "speed": 50, "fuel": 100.0}],
    }
    baseline_copy = copy.deepcopy(authoritative_scenario)

    result = massive_whatif.run_batch(base_scenario=authoritative_scenario, n_scenarios=50)
    assert result["total_scenarios"] == 50

    # Ensure authoritative object was NOT mutated
    assert authoritative_scenario == baseline_copy
    assert authoritative_scenario["units"][0]["fuel"] == 100.0


# ---------------------------------------------------------------------------
# 3. Unified Knowledge Platform Tests
# ---------------------------------------------------------------------------
def test_unified_knowledge_platform_query():
    res = unified_knowledge.query(
        query_str="mountain pass convoy defense",
        theater_id="THEATER-NORTH",
    )
    assert res["synthesis_id"].startswith("ukp-")
    assert res["confidence_score"] >= 0.9
    assert len(res["doctrine_citations"]) >= 1
    assert len(res["recommendations"]) >= 1

    # Link memory to entity
    linked = unified_knowledge.remember_and_link(
        entity_id="DEPOT-ALPHA",
        memory_content="Depot Alpha fuel reserves verified at 342,000L.",
    )
    assert linked["status"] == "linked"
    assert linked["linked_entity"] == "DEPOT-ALPHA"


# ---------------------------------------------------------------------------
# 4. Phase 6 Production Hardening API Endpoints
# ---------------------------------------------------------------------------
def test_phase6_api_endpoints():
    client = TestClient(app)

    # 1. Resilience status & reset
    r_res = client.get("/api/resilience/status")
    assert r_res.status_code == 200
    assert "llm_inference" in r_res.json()

    r_reset = client.post("/api/resilience/reset")
    assert r_reset.status_code == 200
    assert r_reset.json()["status"] == "RESET_SUCCESSFUL"

    # 2. Cache stats & clear
    r_cache = client.get("/api/cache/stats")
    assert r_cache.status_code == 200
    assert "hit_ratio" in r_cache.json()

    r_clear = client.post("/api/cache/clear?namespace=test_clear")
    assert r_clear.status_code == 200

    # 3. Scalability benchmark
    r_bench = client.post("/api/scalability/benchmark?num_items=2000")
    assert r_bench.status_code == 200
    assert r_bench.json()["status"] == "PASS"

    # 4. Unified Knowledge Query endpoint
    r_ukp = client.post(
        "/api/knowledge/unified/query",
        json={"query": "coastal defense SOPs", "theater_id": "THEATER-SOUTH"},
    )
    assert r_ukp.status_code == 200
    assert r_ukp.json()["confidence_score"] > 0.8
