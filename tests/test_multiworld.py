"""Phase 4B Test Suite: Multi-Theater Digital Twin & World Manager.

Invariants:
- Multi-theater management across geographical sectors.
- Isolated concurrent simulation worlds with independent units, weather, and logistics.
- Cross-theater intelligence and readiness aggregation.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.multiworld import (
    TheaterManager,
    WorldManager,
    theater_manager,
    world_manager,
)
from app import db


def test_theater_manager_lifecycle_and_lookup():
    """Verify theater registration, retrieval, and defaults."""
    mgr = TheaterManager()
    theaters = mgr.list_theaters()
    assert len(theaters) >= 3

    # Check northern theater
    north = mgr.get_theater("THEATER-NORTH")
    assert north is not None
    assert north["code"] == "NORTH"
    assert len(north["bounds"]) == 4

    # Register custom theater
    custom_theater = {
        "id": "THEATER-CENTRAL-VALLEY",
        "name": "Central Valley Tactical Zone",
        "code": "CENTRAL",
        "bounds": [[12.0, 77.0], [12.0, 77.5], [11.5, 77.5], [11.5, 77.0]],
        "active_world_id": "WLD-CENTRAL-01",
        "status": "active",
    }
    registered = mgr.register_theater(custom_theater)
    assert registered["id"] == "THEATER-CENTRAL-VALLEY"

    queried = mgr.get_theater("THEATER-CENTRAL-VALLEY")
    assert queried is not None
    assert queried["name"] == "Central Valley Tactical Zone"


def test_world_manager_isolation_and_state_snapshots():
    """Verify independent simulation worlds maintain isolated state."""
    w_mgr = WorldManager()
    worlds = w_mgr.list_worlds()
    assert len(worlds) >= 3

    north_world = w_mgr.get_world("WLD-NORTH-01")
    east_world = w_mgr.get_world("WLD-EAST-01")
    assert north_world is not None
    assert east_world is not None

    # Check state isolation
    snap_n = north_world.get("state_snapshot", {})
    snap_e = east_world.get("state_snapshot", {})

    assert snap_n.get("seed") != snap_e.get("seed")
    assert "units" in snap_n
    assert "depots" in snap_n

    # Filtering worlds by theater_id
    filtered = w_mgr.list_worlds(theater_id="THEATER-NORTH")
    assert len(filtered) >= 1
    assert all(w["theater_id"] == "THEATER-NORTH" for w in filtered)


def test_cross_theater_analysis():
    """Verify cross-theater readiness, threat index, and fuel metrics."""
    w_mgr = WorldManager()
    analysis = w_mgr.cross_theater_analysis()

    assert analysis["theaters_active"] >= 3
    assert analysis["total_units_deployed"] > 0
    assert analysis["total_depot_fuel_liters"] > 0
    assert 0.0 <= analysis["global_readiness_score"] <= 100.0
    assert 0.0 <= analysis["threat_density_index"] <= 100.0
    assert len(analysis["theaters"]) >= 3

    # Check breakdown schema
    first_theater = analysis["theaters"][0]
    assert "theater_id" in first_theater
    assert "world_id" in first_theater
    assert "readiness_score" in first_theater


def test_multiworld_rest_api_endpoints():
    """Verify FastAPI endpoints for multi-theater and world management."""
    client = TestClient(app)

    # 1. List theaters
    res_t = client.get("/api/theaters")
    assert res_t.status_code == 200
    theaters = res_t.json()
    assert isinstance(theaters, list)
    assert len(theaters) >= 3

    # 2. Get specific theater
    res_single = client.get("/api/theaters/THEATER-NORTH")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == "THEATER-NORTH"

    # 3. List worlds
    res_w = client.get("/api/worlds")
    assert res_w.status_code == 200
    worlds = res_w.json()
    assert isinstance(worlds, list)
    assert len(worlds) >= 3

    # 4. Cross-theater analysis
    res_cross = client.get("/api/theaters/cross-analysis")
    assert res_cross.status_code == 200
    cross = res_cross.json()
    assert "theaters_active" in cross
    assert "global_readiness_score" in cross
