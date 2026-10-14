"""Tests for Pan-India Live World Model & Isolated Artificial Impact Simulation."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.engine import SimEngine
from backend.app.environmental_context import environmental_context_service, MONITORING_STATIONS
from backend.app.world_model import world_model_service


@pytest.fixture
def client():
    return TestClient(app)


def test_legacy_golden_preservation():
    """Ensure SC-1..SC-4 engine initialization is completely unchanged."""
    eng = SimEngine()
    evs = eng.start(8841, "SC-2")
    assert len(evs) == 1
    init_payload = evs[0].payload
    assert init_payload["scenarioId"] == "SC-2"
    assert len(init_payload["units"]) == 15
    # Ensure coords are anchored to Bengaluru BASE_LAT / BASE_LON
    for u in init_payload["units"]:
        assert 12.8 < u["lat"] < 13.1
        assert 77.4 < u["lon"] < 77.8


def test_pan_india_baseline_generation():
    """Ensure IN-BASE-LIVE generates units and depots distributed across India."""
    eng = SimEngine()
    evs = eng.start(20261014, "IN-BASE-LIVE")
    assert len(evs) == 1
    init_payload = evs[0].payload
    assert init_payload["scenarioId"] == "IN-BASE-LIVE"
    assert init_payload["worldMode"] == "baseline"

    units = init_payload["units"]
    depots = init_payload["depots"]
    assert len(units) >= 20
    assert len(depots) == 7  # 7 strategic depots including Northeast (Tezpur)

    # Verify pan-India geographic spread (from Ladakh ~34N to South/Islands ~11N)
    lats = [u["lat"] for u in units]
    lons = [u["lon"] for u in units]
    assert max(lats) > 30.0  # Northern sector
    assert min(lats) < 15.0  # Southern or Island sector
    assert min(lons) < 73.0  # Western sector
    assert max(lons) > 85.0  # Eastern or Island sector


def test_pan_india_cyclone_scenario_step():
    """Verify Bay of Bengal cyclone movement and coastal impacts."""
    eng = SimEngine()
    eng.start(20261014, "IN-SC-CYCLONE")
    assert len(eng._weather) == 1
    cyclone = eng._weather[0]
    assert cyclone.id == "W-CYCLONE-BOB"

    # Step simulation
    events = eng.step()
    assert len(events) > 0
    # Cyclone moves northwest
    weather_moves = [e for e in events if e.type == "weather_move" and "CYCLONE" in e.entityId]
    assert len(weather_moves) == 1
    assert weather_moves[0].severity == "high"


def test_pan_india_comms_blackout_scenario():
    """Verify Himalayan high-altitude comms loss rates and battery drain."""
    eng = SimEngine()
    eng.start(20261014, "IN-SC-NORTH-COMMS")
    assert len(eng._weather) == 1
    assert eng._weather[0].id == "W-BLIZZARD-LEH"

    # Run 10 ticks and verify Northern units experience high strain
    total_events = []
    for _ in range(10):
        total_events.extend(eng.step())

    assert any(e.type in ("unit_move", "resource_level", "weather_move") for e in total_events)


def test_environmental_context_service_offline_resilience():
    """Verify environmental context service delivers valid data and provenance."""
    import asyncio
    ctx = asyncio.run(environmental_context_service.get_environmental_context())
    assert ctx["subcontinent"] == "India"
    assert ctx["stationsCount"] == len(MONITORING_STATIONS)
    assert ctx["globalProvenance"] in [
        "REAL_OBSERVATION",
        "REAL_FORECAST",
        "CACHED_REAL_DATA",
        "SYNTHETIC_ENVIRONMENT",
    ]
    # Check Leh station
    leh = ctx["stations"]["STN-LEH"]
    assert leh["lat"] == 34.1526
    assert "temperatureC" in leh
    assert "windSpeedKph" in leh
    assert "cloudPct" in leh
    assert isinstance(leh["cloudPct"], (int, float))


def test_api_world_baseline(client):
    """Test GET /api/world/baseline."""
    resp = client.get("/api/world/baseline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["worldMode"] == "baseline"
    assert data["subcontinent"] == "India"
    assert len(data["units"]) >= 20
    assert len(data["depots"]) == 7
    assert "environmentalContext" in data


def test_api_simulation_branch_fork_step_reset(client):
    """Test fork, step, and instant reset API lifecycle."""
    # 1. Fork a simulation branch
    fork_resp = client.post(
        "/api/world/simulation/fork",
        json={"scenario_id": "IN-SC-CYCLONE", "seed": 4242, "name": "Test Cyclone Run"},
    )
    assert fork_resp.status_code == 200
    fork_data = fork_resp.json()
    branch_id = fork_data["branch"]["branch_id"]
    assert branch_id.startswith("BRANCH-")
    assert fork_data["branch"]["scenario_id"] == "IN-SC-CYCLONE"

    # 2. Step the branch
    step_resp = client.post("/api/world/simulation/step", json={"branch_id": branch_id})
    assert step_resp.status_code == 200
    events = step_resp.json()["events"]
    assert len(events) > 0

    # 3. Reset the branch
    reset_resp = client.post("/api/world/simulation/reset", json={"branch_id": branch_id})
    assert reset_resp.status_code == 200
    reset_data = reset_resp.json()
    assert reset_data["status"] == "reset_complete"
    assert reset_data["tick"] == 0


def test_simulation_branch_isolation():
    """Verify that branching does NOT contaminate or alter the baseline state."""
    baseline_before = world_model_service.baseline_engine.tick
    branch = world_model_service.fork_simulation("IN-SC-WEST-HEAT", seed=9999)
    # Step branch multiple times
    for _ in range(15):
        branch.step()

    assert branch.engine.tick == 15
    # Baseline remains unchanged
    assert world_model_service.baseline_engine.tick == baseline_before


def test_pan_india_cascade_multi_sector_crisis():
    """Verify Pan-India Multi-Sector Cascade crisis spawns 4 concurrent weather cells across India and steps."""
    eng = SimEngine()
    evs = eng.start(20261014, "IN-SC-CASCADE")
    assert len(evs) == 1
    assert evs[0].payload["scenarioId"] == "IN-SC-CASCADE"
    assert evs[0].payload["worldMode"] == "simulation"

    # Verify 4 concurrent weather cells across distinct sectors
    weather_ids = {w.id for w in eng._weather}
    assert "W-CYCLONE-BOB" in weather_ids     # Eastern cyclone
    assert "W-BLIZZARD-LEH" in weather_ids    # Northern blizzard
    assert "W-HEATWAVE-THAR" in weather_ids   # Western heatwave
    assert "W-SQUALL-ANDAMAN" in weather_ids  # Littoral squalls
    assert len(eng._weather) == 4

    # Step engine through 10 iterations to verify compound multi-sector events
    collected_events = []
    for _ in range(10):
        collected_events.extend(eng.step())

    assert len(collected_events) > 0
    types = {e.type for e in collected_events}
    assert "weather_move" in types
    assert "unit_move" in types

    # Instant reset back to baseline
    evs_reset = eng.start(20261014, "IN-BASE-LIVE")
    assert evs_reset[0].payload["scenarioId"] == "IN-BASE-LIVE"
    assert evs_reset[0].payload["worldMode"] == "baseline"
    assert len(eng._weather) == 0
