"""Test Suite for DOIP Phase 7 — Operations Center, Quality, Research & REST Endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.unified_knowledge import unified_knowledge
from app.operations_center import operations_center
from app.quality_platform import quality_platform
from app.data_governance import data_governance_engine
from app.research_sandbox import research_sandbox
from app.documentation_engine import documentation_engine

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer analyst_token"}
COMMANDER_HEADERS = {"Authorization": "Bearer admin_token"}


def test_unified_knowledge_all_methods():
    """Verify all 5 core methods of UnifiedKnowledgePlatform."""
    # 1. Retrieve
    ret = unified_knowledge.retrieve(query="Convoy ambush countermeasures", limit=3)
    assert "memories" in ret
    assert "doctrine_citations" in ret
    assert len(ret["doctrine_citations"]) >= 1

    # 2. Reason
    rsn = unified_knowledge.reason(prompt="Evaluate route security through defile")
    assert "facts" in rsn
    assert "projections" in rsn
    assert "recommendations" in rsn
    assert rsn["grounding"]["human_gate_required"] is True

    # 3. Forecast
    fc = unified_knowledge.forecast(entity_id="UNIT-CONVOY-01", horizon_ticks=180)
    assert fc["horizon_ticks"] == 180
    assert "arrival_percentiles" in fc
    assert "risk_tensor" in fc

    # 4. Trace
    tr = unified_knowledge.trace(incident_id_or_entity_id="INC-AMBUSH-01")
    assert tr["target_id"] == "INC-AMBUSH-01"
    assert "root_cause_analysis" in tr
    assert "dependency_chain" in tr

    # 5. Analyze
    an = unified_knowledge.analyze(theater_id="THEATER-NORTH")
    assert an["theater_id"] == "THEATER-NORTH"
    assert "threat_posture" in an
    assert an["fleet_availability_pct"] > 90.0


def test_operations_center_health_and_reports():
    """Verify Operations Center health inspections and automated report generation."""
    sys_h = operations_center.system_health_review()
    assert sys_h["status"] in ("NOMINAL", "DEGRADED")
    assert sys_h["health_score"] >= 80.0

    ag_h = operations_center.agent_health_review()
    assert ag_h["total_agents"] >= 0
    assert "readiness_percentage" in ag_h

    d_rep = operations_center.generate_daily_health_report()
    assert d_rep["report_type"] == "DAILY_HEALTH_REPORT"
    assert "report_id" in d_rep

    w_rep = operations_center.generate_weekly_risk_report()
    assert w_rep["report_type"] == "WEEKLY_RISK_REPORT"
    assert "theater_risks" in w_rep

    m_rep = operations_center.generate_monthly_readiness_report()
    assert m_rep["report_type"] == "MONTHLY_READINESS_REPORT"
    assert m_rep["composite_readiness_score"] >= 90.0


def test_quality_platform_scorecard():
    """Verify Quality Assurance Platform scorecard generation."""
    card = quality_platform.generate_quality_scorecard()
    assert card["scorecard_type"] == "DOIP_QUALITY_SCORECARD"
    assert card["composite_dqi"] >= 90.0
    assert card["letter_grade"] in ("A+", "A")
    assert "test_coverage" in card["pillars"]
    assert "technical_debt" in card["pillars"]


def test_data_governance_framework():
    """Verify data lineage, schemas, retention, and access policies."""
    # Lineage
    lin = data_governance_engine.record_lineage(
        dataset_id="DS-TELEMETRY-01",
        source="ADS-B Receiver",
        transformation="Kalman Filter Velocity",
        actor="vision_pipeline",
    )
    assert lin["dataset_id"] == "DS-TELEMETRY-01"
    records = data_governance_engine.get_lineage("DS-TELEMETRY-01")
    assert len(records) >= 1

    # Schema
    sch = data_governance_engine.register_schema(
        schema_id="SimEvent",
        version="v1.0",
        schema_def={"type": "object", "properties": {"tick": {"type": "integer"}}},
    )
    assert sch["version"] == "v1.0"

    # Retention
    ret = data_governance_engine.enforce_retention_policy("telemetry_stream", age_days=15)
    assert ret["decision"] == "RETAIN"

    # Access policy
    assert data_governance_engine.enforce_access_policy("commander", "TOP_SECRET") is True
    assert data_governance_engine.enforce_access_policy("analyst", "TOP_SECRET") is False


def test_research_sandbox_isolation():
    """Verify research sandbox executes experiments with strict production isolation."""
    # AI experiment
    ai_exp = research_sandbox.run_experimental_ai(
        prompt="Synthesize non-traditional counter-EW jamming waveform",
        experimental_model="neuromorphic_v2",
    )
    assert ai_exp["status"] == "COMPLETED"
    assert ai_exp["isolated"] is True

    # Novel forecaster
    fc_exp = research_sandbox.run_novel_forecaster(horizon_ticks=400)
    assert fc_exp["domain"] == "NOVEL_FORECASTING"
    assert fc_exp["isolated"] is True

    # Novel planner
    pln_exp = research_sandbox.run_novel_planner(start=(34.0, 43.0), goal=(35.0, 44.0))
    assert pln_exp["domain"] == "NOVEL_PLANNER"
    assert pln_exp["isolated"] is True

    # Prototype simulation
    sim_exp = research_sandbox.run_prototype_sim(scenario_id="SC-PROTO-01", ticks=40)
    assert sim_exp["production_impact"] == "ZERO_MUTATION_CONFIRMED"

    # Experiment listing
    experiments = research_sandbox.list_experiments()
    assert len(experiments) >= 4


def test_documentation_engine_sync():
    """Verify autonomous documentation engine introspects source metadata."""
    res = documentation_engine.sync_all_documentation()
    assert res["status"] == "SYNCHRONIZED"
    assert "architecture" in res["sections_generated"]
    assert "api" in res["sections_generated"]
    assert "operator" in res["sections_generated"]


def test_phase7_rest_endpoints():
    """Verify FastAPI endpoints registered for Phase 7 capabilities."""
    # 1. Platform Services
    r_svc = client.get("/api/platform/services", headers=AUTH_HEADERS)
    assert r_svc.status_code == 200
    assert len(r_svc.json()["services"]) >= 15

    # 2. Platform Health
    r_h = client.get("/api/platform/health", headers=AUTH_HEADERS)
    assert r_h.status_code == 200
    assert "overall_status" in r_h.json()

    # 3. Operations Center Health & Daily Report
    r_op_h = client.get("/api/operations/center/health", headers=AUTH_HEADERS)
    assert r_op_h.status_code == 200
    r_daily = client.get("/api/operations/center/reports/daily", headers=AUTH_HEADERS)
    assert r_daily.status_code == 200
    assert r_daily.json()["report_type"] == "DAILY_HEALTH_REPORT"

    # 4. Governance Verify (Authorized Commander passes)
    r_gov = client.post(
        "/api/governance/verify",
        json={"action": "mission_execution", "actor": "commander_nash", "role": "commander"},
        headers=COMMANDER_HEADERS,
    )
    assert r_gov.status_code == 200
    assert r_gov.json()["governance_status"] == "APPROVED"

    # 5. Governance Verify (Unauthorized action rejected with 403)
    r_gov_fail = client.post(
        "/api/governance/verify",
        json={"action": "mission_execution", "actor": ""},
        headers=AUTH_HEADERS,
    )
    assert r_gov_fail.status_code == 403

    # 6. Continuous Validation
    r_val = client.post("/api/validation/continuous", headers=AUTH_HEADERS)
    assert r_val.status_code == 200
    assert r_val.json()["status"] == "PASSED"

    # 7. Quality Scorecard
    r_q = client.get("/api/quality/scorecard", headers=AUTH_HEADERS)
    assert r_q.status_code == 200
    assert r_q.json()["letter_grade"] in ("A+", "A")

    # 8. Research Sandbox Experiment
    r_sb = client.post(
        "/api/research/sandbox/experiment",
        json={"experiment_type": "ai", "prompt": "Evaluate counter-drone defense"},
        headers=AUTH_HEADERS,
    )
    assert r_sb.status_code == 200
    assert r_sb.json()["isolated"] is True
