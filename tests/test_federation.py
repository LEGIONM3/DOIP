"""Phase 4A Test Suite: Federated Command Architecture.

Invariants:
- Multi-tier command hierarchy: Regional -> Operational/Theater -> Tactical.
- Synchronized intelligence: Bidirectional intelligence propagation across nodes.
- Liveness heartbeats and persistence.
- Strict AI safety boundary: Strategic directives cascade in 'staged' status with
  requires_human_confirmation=True.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.federation import (
    FederationNode,
    RegionalNode,
    TheaterNode,
    FederationManager,
    federation_manager,
)
from app import db


def test_federation_node_hierarchy_and_roles():
    """Verify nodes instantiate with correct tiers, regions, and relationships."""
    reg_node = RegionalNode(
        node_id="NODE-TEST-REGIONAL",
        name="Strategic Test Command",
        region="PACIFIC-WEST",
    )
    assert reg_node.tier == "regional"
    assert reg_node.region == "PACIFIC-WEST"
    assert reg_node.status == "online"

    th_node = TheaterNode(
        node_id="NODE-TEST-THEATER",
        name="Littoral Theater Sector",
        theater_code="THEATER-SOUTH",
        region="SOUTH-LITTORAL",
    )
    assert th_node.tier == "operational"
    assert th_node.theater_code == "THEATER-SOUTH"

    tac_node = FederationNode(
        node_id="NODE-TEST-TACTICAL",
        name="Tactical Drone Group 4",
        tier="tactical",
        parent_id=th_node.node_id,
    )
    assert tac_node.tier == "tactical"
    assert tac_node.parent_id == th_node.node_id

    # Test subordinate registration
    reg_node.register_subordinate(th_node.node_id)
    assert th_node.node_id in reg_node.operational_nodes

    th_node.register_tactical_unit(tac_node.node_id)
    assert tac_node.node_id in th_node.tactical_nodes


def test_federation_manager_topology_and_heartbeats():
    """Verify default topology seeding and heartbeat persistence."""
    mgr = FederationManager()
    nodes = mgr.list_nodes()
    assert len(nodes) >= 4

    hq = mgr.get_node("NODE-REGIONAL-HQ")
    assert hq is not None
    assert hq.tier == "regional"

    # Test heartbeat updates DB
    hb_result = hq.heartbeat()
    assert hb_result["id"] == "NODE-REGIONAL-HQ"
    assert hb_result["status"] == "online"

    db_node = db.get_federation_node("NODE-REGIONAL-HQ")
    assert db_node is not None
    assert db_node["name"] == "Joint Regional Defense Command"


def test_directive_broadcast_and_human_approval_invariant():
    """Verify top-down command broadcast enforces staged status and human gate."""
    mgr = FederationManager()
    broadcast_results = mgr.broadcast_directive(
        origin_id="NODE-REGIONAL-HQ",
        directive_title="Execute Readiness Level Alpha",
        content="All theater assets initiate defensive dispersion.",
        target_tier="operational",
    )
    assert len(broadcast_results) >= 2
    for item in broadcast_results:
        directive = item["directive"]
        assert directive["origin_node_id"] == "NODE-REGIONAL-HQ"
        assert directive["target_tier"] == "operational"
        # STRICT SAFETY INVARIANT: Directives must be staged and require human confirmation
        assert directive["requires_human_confirmation"] is True
        assert directive["status"] == "staged"


def test_intelligence_synchronization():
    """Verify cross-node intelligence sharing propagates to peer nodes."""
    mgr = FederationManager()
    intel_payload = {
        "threat_type": "RADAR_EMISSION_ANOMALY",
        "sector": "SECTOR-NORTH-7",
        "confidence": 0.96,
    }
    sync_count = mgr.synchronize_intelligence(
        source_node_id="NODE-TACTICAL-RECON-1",
        intel_type="EW_ALERT",
        payload=intel_payload,
    )
    assert sync_count >= 3

    # Check recipient node received intelligence
    th_north = mgr.get_node("NODE-THEATER-NORTH")
    assert th_north is not None
    assert len(th_north.replicated_intelligence) > 0
    latest_intel = th_north.replicated_intelligence[-1]
    assert latest_intel["kind"] == "EW_ALERT"
    assert latest_intel["payload"]["sector"] == "SECTOR-NORTH-7"


def test_federation_rest_api_endpoints():
    """Verify FastAPI endpoints for federated mesh operations."""
    client = TestClient(app)

    # 1. List nodes
    res = client.get("/api/federation/nodes")
    assert res.status_code == 200
    nodes = res.json()
    assert isinstance(nodes, list)
    assert len(nodes) >= 4

    # 2. Heartbeat / Register
    hb_req = {
        "id": "NODE-THEATER-NORTH",
        "name": "Northern Mountain Theater Command",
        "tier": "operational",
        "region": "NORTH-SECTOR",
        "endpoint": "https://fed-north.doip.mil:8443",
        "metadata": {"custom_tag": "test_hb"},
    }
    res_hb = client.post("/api/federation/nodes", json=hb_req)
    assert res_hb.status_code == 200
    assert res_hb.json()["status"] == "online"

    # 3. Broadcast directive
    dir_req = {
        "origin_id": "NODE-REGIONAL-HQ",
        "title": "REST API Test Directive",
        "content": "Confirming communication corridor",
        "target_tier": "operational",
    }
    res_dir = client.post("/api/federation/directives", json=dir_req)
    assert res_dir.status_code == 200
    broadcast_data = res_dir.json()
    assert isinstance(broadcast_data, list)
    assert len(broadcast_data) >= 2
    for target in broadcast_data:
        assert target["directive"]["requires_human_confirmation"] is True

    # 4. Sync intelligence
    sync_req = {
        "source_node_id": "NODE-REGIONAL-HQ",
        "kind": "STRATEGIC_DEFENSE_UPDATE",
        "payload": {"defense_condition": "DEFCON-3"},
    }
    res_sync = client.post("/api/federation/intelligence", json=sync_req)
    assert res_sync.status_code == 200
    assert res_sync.json()["synced_nodes_count"] >= 3
