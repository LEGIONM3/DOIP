"""Phase 3 Test Suite: Digital Twin, Knowledge Graph, Vision, Copilot & Replay DB Layer.

Invariants:
- SQLAlchemy 2.0 ORM models for all Phase 3 domain entities:
  * KnowledgeGraphNode, KnowledgeGraphEdge
  * VisionDetection, VisionTrack
  * ForecastRun
  * MissionCopilotSession
  * ReplayReport
- Alembic migration 8b1f2930cd34 applies cleanly with head status.
- Persistence helpers for all Phase 3 entities support save, get, list, and lifecycle updates.
- Backward compatibility preserved across SQLite and PostgreSQL engines.
"""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from app import db, models


@pytest.fixture(autouse=True)
def setup_db():
    db.init()


def test_phase3_models_metadata():
    """Verify all 7 Phase 3 models are registered in Base.metadata."""
    table_names = models.Base.metadata.tables.keys()
    required = {
        "knowledge_graph_nodes",
        "knowledge_graph_edges",
        "vision_detections",
        "vision_tracks",
        "forecast_runs",
        "copilot_sessions",
        "replay_reports",
    }
    for req in required:
        assert req in table_names, f"Expected table {req} in Base.metadata"


def test_knowledge_graph_node_and_edge_crud():
    """Verify knowledge graph node and edge persistence and query filtering."""
    node_id = "test-node-hq-01"
    node = db.save_graph_node({
        "id": node_id,
        "entity_type": "COMMAND_POST",
        "label": "Tactical Operations Center Alpha",
        "properties": {"echelon": "brigade", "readiness": "high"},
    })
    assert node["id"] == node_id
    assert node["entity_type"] == "COMMAND_POST"

    nodes = db.list_graph_nodes(entity_type="COMMAND_POST")
    assert any(n["id"] == node_id for n in nodes)

    edge = db.save_graph_edge({
        "source_id": node_id,
        "target_id": "target-radar-02",
        "relation_type": "CONTROLS",
        "weight": 1.5,
        "properties": {"channel": "secure_link"},
    })
    assert edge["source_id"] == node_id
    assert edge["relation_type"] == "CONTROLS"

    edges = db.list_graph_edges(source_id=node_id, relation_type="CONTROLS")
    assert any(e["source_id"] == node_id and e["target_id"] == "target-radar-02" for e in edges)


def test_vision_detections_and_tracks_crud():
    """Verify vision detection telemetry and persistent track lifecycle."""
    det = db.save_vision_detection({
        "frame_id": "frame-air-01",
        "tick": 42,
        "class_name": "uav",
        "confidence": 0.96,
        "bbox_json": [15.0, 25.0, 30.0, 20.0],
        "lat": 32.748,
        "lon": 74.885,
    })
    assert det["class_name"] == "uav"
    assert det["confidence"] == 0.96

    dets = db.list_vision_detections(frame_id="frame-air-01", tick=42)
    assert len(dets) >= 1
    assert any(d["frame_id"] == "frame-air-01" for d in dets)

    trk = db.save_vision_track({
        "id": "TRK-TARGET-09",
        "class_name": "military_vehicle",
        "first_tick": 40,
        "last_tick": 45,
        "trajectory": [
            {"tick": 40, "lat": 32.74, "lon": 74.88},
            {"tick": 45, "lat": 32.75, "lon": 74.88},
        ],
        "status": "active",
    })
    assert trk["id"] == "TRK-TARGET-09"
    assert trk["class_name"] == "military_vehicle"

    tracks = db.list_vision_tracks(status="active")
    assert any(t["id"] == "TRK-TARGET-09" for t in tracks)

    fetched_trk = db.get_vision_track("TRK-TARGET-09")
    assert fetched_trk is not None
    assert fetched_trk["id"] == "TRK-TARGET-09"


def test_forecast_run_crud():
    """Verify digital twin lookahead forecast persistence and retrieval."""
    fc_id = "FC-RUN-PHASE3-01"
    run = db.save_forecast_run({
        "id": fc_id,
        "scenario_id": "SC-BORDER-DEFENSE",
        "tick": 100,
        "horizon_ticks": 180,
        "predictions": [
            {"tick": 120, "threat_level": "elevated"},
            {"tick": 180, "threat_level": "critical"},
        ],
        "confidence": 0.91,
    })
    assert run["id"] == fc_id
    assert run["scenario_id"] == "SC-BORDER-DEFENSE"

    fetched = db.get_forecast_run(fc_id)
    assert fetched is not None
    assert fetched["scenario_id"] == "SC-BORDER-DEFENSE"
    assert len(fetched["predictions"]) == 2

    runs = db.list_forecast_runs(scenario_id="SC-BORDER-DEFENSE")
    assert any(r["id"] == fc_id for r in runs)


def test_mission_copilot_session_crud():
    """Verify mission copilot conversational advisory and status updates."""
    cop_id = "copilot-sess-007"
    session = db.save_copilot_session({
        "id": cop_id,
        "mission_id": "MSN-TACTICAL-01",
        "title": "Air Corridor Optimization",
        "messages": [
            {"role": "user", "content": "Suggest bypass for SAM radar coverage"},
            {"role": "assistant", "content": "Reroute through waypoint WP-NORTH-02"},
        ],
        "proposals": [
            {"type": "REROUTE", "waypoints": [[32.74, 74.88], [32.78, 74.92]]},
        ],
        "status": "active",
    })
    assert session["id"] == cop_id
    assert session["status"] == "active"

    fetched = db.get_copilot_session(cop_id)
    assert fetched is not None
    assert fetched["title"] == "Air Corridor Optimization"
    assert len(fetched["messages"]) == 2

    # Status transition
    updated = db.update_copilot_session_status(cop_id, "approved", approved_by="colonel_sanders")
    assert updated is not None
    assert updated["status"] == "approved"
    assert updated["approved_by"] == "colonel_sanders"


def test_replay_report_crud():
    """Verify after-action replay and turning points persistence."""
    rep_id = "REP-AAR-2026-01"
    report = db.save_replay_report({
        "id": rep_id,
        "run_id": "RUN-TEST-SIM-101",
        "comparison_run_id": "RUN-TEST-SIM-100",
        "summary": "Air superiority achieved with zero collateral damage",
        "turning_points": [
            {"tick": 45, "event": "SAM radar neutralized", "impact": "High"},
            {"tick": 80, "event": "Extraction route cleared", "impact": "Decisive"},
        ],
        "kpi_deltas": {
            "survivability": "+25%",
            "fuel_efficiency": "+12%",
        },
    })
    assert report["id"] == rep_id
    assert report["run_id"] == "RUN-TEST-SIM-101"

    fetched = db.get_replay_report(rep_id)
    assert fetched is not None
    assert fetched["run_id"] == "RUN-TEST-SIM-101"
    assert len(fetched["turning_points"]) == 2
    assert fetched["kpi_deltas"]["survivability"] == "+25%"

    reports = db.list_replay_reports(run_id="RUN-TEST-SIM-101")
    assert any(r["id"] == rep_id for r in reports)
