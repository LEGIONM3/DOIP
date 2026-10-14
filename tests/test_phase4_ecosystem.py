"""Phase 4E & 4F Test Suite: Multi-Layer Graph AI & Distributed Forecasting.

Invariants:
- Multi-layer graph reasoning across 5 distinct operational layers:
  Command, Physical Assets, Cyber/EW, Logistics, Terrain.
- Cascade failure propagation modeling.
- Cross-theater emerging risk detection.
- Distributed synchronized digital twin lookahead forecasting across all theaters.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.graph_intelligence import GraphIntelligenceEngine, graph_ai
from app.distributed_forecaster import DistributedDigitalTwinForecaster, distributed_forecaster


def test_graph_intelligence_reasoning_and_cascades():
    """Verify multi-layer graph reasoning and cascade failure propagation."""
    engine = GraphIntelligenceEngine()
    
    # 1. Reasoning query
    res = engine.graph_reason(query="Evaluate supply vulnerability if northern depot fails")
    assert "insight" in res
    assert "nodes" in res
    assert "links" in res
    assert res["nodes_identified"] > 0

    # 2. Cascade failure prediction
    cascade = engine.predict_cascade_failure("AST-DEPOT-NORTH")
    assert cascade["root_failure_id"] == "AST-DEPOT-NORTH"
    assert cascade["cascade_severity"] in ["LOW", "MODERATE", "CRITICAL"]
    assert cascade["total_compromised_entities"] >= 1
    assert len(cascade["impact_chain"]) >= 1

    # 3. Detect emergent risks
    risks = engine.detect_emergent_risks()
    assert isinstance(risks, list)
    assert len(risks) >= 1
    assert "risk_type" in risks[0]
    assert "severity" in risks[0]


def test_distributed_forecaster_all_theaters():
    """Verify distributed forecaster synthesizes synchronized lookahead for all theaters."""
    forecaster = DistributedDigitalTwinForecaster()
    fc = forecaster.forecast_all_theaters(horizon_hours=3.0, confidence=0.95)

    assert "theaters_evaluated" in fc
    assert fc["theaters_evaluated"] >= 3
    assert "theater_forecasts" in fc
    assert "global_metrics" in fc
    assert "strategic_summary" in fc

    metrics = fc["global_metrics"]
    assert "campaign_delay_probability" in metrics
    assert "total_pnr_breaches" in metrics


def test_phase4_ecosystem_rest_api_endpoints():
    """Verify FastAPI endpoints for graph AI and distributed forecasting."""
    client = TestClient(app)

    # 1. Graph Reason
    res_reason = client.post("/api/graph-ai/reason", json={"query": "Check communications integrity"})
    assert res_reason.status_code == 200
    assert "insight" in res_reason.json()

    # 2. Cascade Failure
    res_casc = client.get("/api/graph-ai/cascade-failure/AST-DEPOT-NORTH")
    assert res_casc.status_code == 200
    assert "impact_chain" in res_casc.json()

    # 3. Emergent Risks
    res_risks = client.get("/api/graph-ai/emergent-risks")
    assert res_risks.status_code == 200
    assert isinstance(res_risks.json(), list)

    # 4. Distributed Forecast
    res_fc = client.post("/api/forecast/distributed", json={"horizon_hours": 2.0, "confidence": 0.95})
    assert res_fc.status_code == 200
    assert "theaters_evaluated" in res_fc.json()
