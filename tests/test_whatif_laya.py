"""Integration tests for What-If scenario permutations, massive branch execution, and Phase 8.5 endpoints."""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.hybrid_outcome_engine import HybridOutcomeEngine


@pytest.fixture
def client():
    return TestClient(app)


def test_whatif_hybrid_alternatives():
    """Verify HybridOutcomeEngine evaluates multi-permutation what-if alternatives."""
    engine = HybridOutcomeEngine()
    whatif_res = engine.evaluate_whatif_alternatives(ticks=5)

    assert whatif_res["variations_evaluated"] == 4
    for r in whatif_res["results"]:
        assert "variation_name" in r
        assert "final_operational_state" in r["summary"]
        assert "average_risk" in r["summary"]


def test_massive_hybrid_whatif_branches():
    """Verify massive hybrid what-if engine calculates outcome probability distributions and risk percentiles."""
    engine = HybridOutcomeEngine()
    massive_res = engine.run_massive_hybrid_whatif(branches=100, ticks=10)

    assert massive_res["branches_evaluated"] == 100
    assert "success_probability" in massive_res
    assert "delay_probability" in massive_res
    assert "failure_probability" in massive_res
    assert "abort_probability" in massive_res

    # Verify probabilities sum to ~1.0
    total_prob = (
        massive_res["success_probability"]
        + massive_res["delay_probability"]
        + massive_res["failure_probability"]
        + massive_res["abort_probability"]
    )
    assert abs(total_prob - 1.0) < 0.05

    # Verify risk percentiles
    risk_env = massive_res["risk_distribution"]
    assert 0.0 <= risk_env["p10"] <= risk_env["p50"] <= risk_env["p90"] <= risk_env["worst_case"] <= 1.0


def test_api_hybrid_simulation_endpoints(client):
    """Verify Phase 8 REST endpoints for hybrid step and trajectory."""
    # Step endpoint
    res_step = client.post("/api/simulation/hybrid/step", json={"dt_sec": 1.0, "mode": "HYBRID_AI_SIM"})
    assert res_step.status_code == 200
    data_step = res_step.json()
    assert "consensus_outcome" in data_step
    assert "physics_state" in data_step

    # Trajectory run endpoint
    res_run = client.post("/api/simulation/hybrid/run", json={"ticks": 5, "dt_sec": 1.0})
    assert res_run.status_code == 200
    data_run = res_run.json()
    assert data_run["ticks"] == 5
    assert "trajectory" in data_run


def test_api_massive_whatif_endpoint(client):
    """Verify REST endpoint for massive What-If Monte Carlo simulation."""
    res = client.post("/api/simulation/hybrid/whatif/massive", json={"branches": 100, "ticks": 10})
    assert res.status_code == 200
    data = res.json()
    assert data["branches_evaluated"] == 100
    assert "success_probability" in data
    assert "risk_distribution" in data


def test_api_laya_endpoints_and_model_switching(client):
    """Verify Phase 8 REST endpoints for Laya status, decide, models, metrics, and switching."""
    # Status
    res_status = client.get("/api/laya/status")
    assert res_status.status_code == 200
    assert res_status.json()["model_name"] in ["laya-doip-v1", "laya_doip_v1"]

    # Decide
    res_decide = client.post("/api/laya/decide", json={"min_confidence": 0.5})
    assert res_decide.status_code == 200
    data_decide = res_decide.json()
    assert "operational_state" in data_decide
    assert "gate_state" in data_decide

    # Models
    res_models = client.get("/api/laya/models")
    assert res_models.status_code == 200
    assert len(res_models.json()) >= 2

    # Switch model to laya-doip-v2
    res_switch = client.post("/api/laya/models/switch", json={"model_id": "laya-doip-v2"})
    assert res_switch.status_code == 200
    assert res_switch.json()["active_model"] == "laya-doip-v2"

    # Switch back to laya-doip-v1
    res_switch_back = client.post("/api/laya/models/switch", json={"model_id": "laya-doip-v1"})
    assert res_switch_back.status_code == 200
    assert res_switch_back.json()["active_model"] == "laya-doip-v1"

    # Train status
    res_train = client.get("/api/model-lab/train-status")
    assert res_train.status_code == 200
    assert res_train.json()["status"] == "READY"
