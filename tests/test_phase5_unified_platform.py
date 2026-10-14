"""Phase 5 Comprehensive Test Suite: Unified Enterprise Platform.

Tests all Phase 5 capabilities:
- Phase 5A: Unified Agent Runtime
- Phase 5B: Persistent Long-Term Memory
- Phase 5C: Autonomous Analysis Engine
- Phase 5D: Large-Scale Forecasting Matrix
- Phase 5E: Massive What-If Engine
- Phase 5F: Operational Analytics Platform
- Phase 5G: Knowledge Synthesis Layer
- Phase 5H: Observability Platform
- Phase 5I: Model Management Layer
- Phase 5J: Operational Workflow Engine (Mandatory Human Gate)
- Phase 5K: Operational Reporting Engine
- Phase 5L: API Endpoints (FastAPI TestClient)
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import db
from app.main import app
from app.agent_runtime import agent_runtime, AgentRegistry, AgentTaskQueue, AgentCoordinator
from app.memory_store import memory_store
from app.analysis_engine import analysis_engine
from app.large_scale_forecasting import large_scale_forecaster
from app.massive_whatif import massive_whatif, ScenarioGenerator
from app.knowledge_synthesizer import knowledge_synthesizer
from app.analytics_engine import operational_analytics
from app.observability import observability
from app.model_management import model_manager
from app.workflow_engine import workflow_engine
from app.reporting_engine import reporting_engine


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    db.init()


# ---------------------------------------------------------------------------
# Phase 5A: Unified Agent Runtime Tests
# ---------------------------------------------------------------------------
def test_agent_registry():
    registry = AgentRegistry()
    agent = registry.register(
        agent_id="test-agent-alpha",
        name="Alpha Unit Test Agent",
        role="test_role",
        capabilities=["recon", "analysis"],
    )
    assert agent["id"] == "test-agent-alpha"
    assert "recon" in agent["capabilities"]

    fetched = registry.get("test-agent-alpha")
    assert fetched is not None
    assert fetched["name"] == "Alpha Unit Test Agent"

    by_cap = registry.find_by_capability("recon")
    assert any(a["id"] == "test-agent-alpha" for a in by_cap)


def test_agent_task_queue_and_coordinator():
    runtime = agent_runtime
    status = runtime.get_status()
    assert status["status"] == "operational"
    assert status["active_agents_count"] >= 7

    task = runtime.submit_task("sim_calculation", {"grid_x": 10, "grid_y": 20})
    assert task["status"] == "completed"
    assert "result" in task


# ---------------------------------------------------------------------------
# Phase 5B: Long-Term Memory Tests
# ---------------------------------------------------------------------------
def test_memory_store_three_tiers():
    mem_store = memory_store

    sem = mem_store.remember("Doctrine SOP-12 mandates thermal camouflage", memory_type="semantic")
    assert sem["id"].startswith("mem-")

    epi = mem_store.remember("Convoy Bravo ambushed at Ridge 4", memory_type="episodic", importance=1.5)
    assert epi["id"].startswith("mem-")

    op = mem_store.remember("Telemetry ping received from Drone-04", memory_type="operational")
    assert op["id"].startswith("mem-")

    retrieved = mem_store.retrieve("thermal")
    assert len(retrieved) >= 1

    summary = mem_store.summarize()
    assert "Consolidated Intelligence Summary" in summary

    consolidation = mem_store.consolidate()
    assert consolidation["status"] == "consolidated"


# ---------------------------------------------------------------------------
# Phase 5C: Autonomous Analysis Engine Tests
# ---------------------------------------------------------------------------
def test_analysis_engine():
    results = analysis_engine.run_full_analysis()
    assert results["status"] == "complete"
    assert results["total_findings"] >= 5
    assert "anomalies" in results["categories"]
    assert "bottlenecks" in results["categories"]
    assert "trends" in results["categories"]
    assert "predicted_failures" in results["categories"]
    assert "readiness" in results["categories"]


# ---------------------------------------------------------------------------
# Phase 5D: Large-Scale Forecasting Matrix Tests
# ---------------------------------------------------------------------------
def test_large_scale_forecasting():
    matrix = large_scale_forecaster.generate_forecast_matrix(
        theaters=["THEATER-A", "THEATER-B"], horizon_hours=6.0
    )
    assert matrix["theaters"] == ["THEATER-A", "THEATER-B"]
    assert matrix["horizon_hours"] == 6.0
    assert "THEATER-A" in matrix["risk_tensor"]
    assert "THEATER-B" in matrix["risk_tensor"]
    assert "composite_risk_score" in matrix["risk_tensor"]["THEATER-A"]


# ---------------------------------------------------------------------------
# Phase 5E: Massive What-If Engine Tests
# ---------------------------------------------------------------------------
def test_massive_whatif():
    batch = massive_whatif.run_batch(n_scenarios=30, seed_base=101)
    assert batch["total_scenarios"] == 30
    assert "comparison" in batch
    assert "mean_score" in batch["comparison"]
    assert len(batch["ranked_top_10"]) <= 10
    # Strict Invariant: outcomes must be sorted by score descending
    scores = [o["score"] for o in batch["ranked_top_10"]]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Phase 5F: Operational Analytics Platform Tests
# ---------------------------------------------------------------------------
def test_operational_analytics():
    dash = operational_analytics.get_dashboard_summary()
    assert "kpis" in dash
    assert "missions" in dash
    assert "resources" in dash
    assert "readiness" in dash
    assert dash["kpis"]["mission_success_rate"] > 0.0
    assert dash["readiness"]["composite_fleet_readiness"] > 0.0


# ---------------------------------------------------------------------------
# Phase 5G: Knowledge Synthesis Layer Tests
# ---------------------------------------------------------------------------
def test_knowledge_synthesizer():
    synth = knowledge_synthesizer.synthesize_operational_picture(
        query="corridor security and supply escort"
    )
    assert synth["synthesis_id"].startswith("synth-")
    assert synth["confidence_score"] > 0.8
    assert len(synth["doctrine_citations"]) >= 1
    assert len(synth["recommendations"]) >= 1


# ---------------------------------------------------------------------------
# Phase 5H: Observability Platform Tests
# ---------------------------------------------------------------------------
def test_observability():
    obs = observability
    obs.increment_counter("unit_test_counter", 5)
    obs.record_latency("test_operation", 18.5)
    obs.record_latency("test_operation", 24.2)
    obs.set_gauge("test_gauge", 99.9)

    summary = obs.get_metrics_summary()
    assert summary["counters"]["unit_test_counter"] >= 5
    assert summary["gauges"]["test_gauge"] == 99.9
    assert "test_operation" in summary["latency_percentiles"]

    health = obs.get_system_health()
    assert health["status"] == "HEALTHY"

    prom = obs.get_prometheus_export()
    assert "doip_unit_test_counter_total" in prom


# ---------------------------------------------------------------------------
# Phase 5I: Model Management Layer Tests
# ---------------------------------------------------------------------------
def test_model_manager_and_router():
    models = model_manager.registry.list_all()
    assert len(models) >= 4

    # Routing tests
    vision_route = model_manager.router.route_task("vision_adjudication")
    assert vision_route["selected_model"]["model_type"] == "vision"

    rag_route = model_manager.router.route_task("rag_retrieve")
    assert rag_route["selected_model"]["model_type"] == "embedding"

    health = model_manager.check_health("model-ollama-llama3")
    assert health["status"] in ("ONLINE", "OFFLINE")


# ---------------------------------------------------------------------------
# Phase 5J: Operational Workflow Engine Tests
# ---------------------------------------------------------------------------
def test_workflow_engine_human_gate():
    wf = workflow_engine.create_workflow(
        workflow_type="strike_mission",
        title="Operation Desert Falcon",
        requires_human_confirmation=True,
    )
    assert wf["status"] == "staged"
    assert wf["current_step"] == "human_gate"

    # Invariant check: Cannot advance to execution without operator approval
    with pytest.raises(PermissionError):
        workflow_engine.advance_step(wf["id"], "execution")

    # Authorize with operator ID
    approved = workflow_engine.approve_workflow(wf["id"], operator_id="GEN-THOMPSON")
    assert approved["status"] == "approved"
    assert approved["approved_by"] == "GEN-THOMPSON"

    # Now advancing is permitted
    advanced = workflow_engine.advance_step(wf["id"], "completed")
    assert advanced["status"] == "completed"


# ---------------------------------------------------------------------------
# Phase 5K: Operational Reporting Engine Tests
# ---------------------------------------------------------------------------
def test_reporting_engine():
    sitrep = reporting_engine.generate_daily_sitrep("THEATER-CENTRAL")
    assert sitrep["report_type"] == "sitrep"
    assert "# COMMANDER'S DAILY SITUATION REPORT" in sitrep["content_md"]

    aar = reporting_engine.generate_mission_report("MSN-IRON-FORGE")
    assert aar["report_type"] == "mission_aar"
    assert "MSN-IRON-FORGE" in aar["content_md"]

    listed = reporting_engine.list_reports(limit=10)
    assert len(listed) >= 2


# ---------------------------------------------------------------------------
# Phase 5L: API Endpoints (FastAPI TestClient)
# ---------------------------------------------------------------------------
def test_api_phase5_endpoints():
    client = TestClient(app)

    # 1. Agents list
    r_agents = client.get("/api/agents")
    assert r_agents.status_code == 200
    assert isinstance(r_agents.json(), list)

    # 2. Agent Runtime status
    r_rt = client.get("/api/agents/runtime/status")
    assert r_rt.status_code == 200
    assert r_rt.json()["status"] == "operational"

    # 3. Agent task submit
    r_task = client.post("/api/agents/tasks", json={"task_type": "patrol_check", "payload": {}})
    assert r_task.status_code == 200

    # 4. Memory store & retrieve
    r_mem = client.post("/api/memory/remember", json={"content": "Logistics depot 3 inventory verified", "memory_type": "operational"})
    assert r_mem.status_code == 200
    r_ret = client.get("/api/memory/retrieve?q=depot")
    assert r_ret.status_code == 200

    # 5. Analysis run
    r_an = client.get("/api/analysis/run")
    assert r_an.status_code == 200
    assert "categories" in r_an.json()

    # 6. Forecast matrix
    r_fm = client.post("/api/forecasting/matrix", json={"theaters": ["THEATER-1"], "horizon_hours": 3.0})
    assert r_fm.status_code == 200

    # 7. Massive What-If
    r_wi = client.post("/api/whatif/massive", json={"n_scenarios": 20})
    assert r_wi.status_code == 200

    # 8. Analytics dashboard
    r_dash = client.get("/api/analytics/dashboard")
    assert r_dash.status_code == 200

    # 9. Knowledge synthesis
    r_syn = client.post("/api/knowledge/synthesize", json={"query": "mountain convoy protection"})
    assert r_syn.status_code == 200

    # 10. Observability health & prometheus
    r_health = client.get("/api/observability/health")
    assert r_health.status_code == 200
    r_prom = client.get("/api/observability/prometheus")
    assert r_prom.status_code == 200
    assert "doip" in r_prom.text

    # 11. Model list & route
    r_models = client.get("/api/models")
    assert r_models.status_code == 200
    r_route = client.post("/api/models/route", json={"task_type": "vision_adjudication"})
    assert r_route.status_code == 200

    # 12. Workflow lifecycle
    r_wf = client.post("/api/workflows", json={"workflow_type": "recon", "title": "Route Recon Alpha"})
    assert r_wf.status_code == 200
    wfid = r_wf.json()["id"]

    r_app = client.post(f"/api/workflows/{wfid}/approve", json={"operator_id": "COL-DAVIS"})
    assert r_app.status_code == 200
    assert r_app.json()["approved_by"] == "COL-DAVIS"

    # 13. Reports generate & list
    r_rep = client.post("/api/reports/generate", json={"report_type": "sitrep", "theater": "NORTH"})
    assert r_rep.status_code == 200
    r_reps = client.get("/api/reports")
    assert r_reps.status_code == 200
