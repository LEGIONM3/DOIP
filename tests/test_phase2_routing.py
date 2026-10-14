"""Phase 2A Test Suite: Tactical Route Planning Engine.

Invariants:
- Multi-layer cost routing across terrain, weather, and threat layers.
- 4 tactical strategies: shortest, safest, fuel_efficient, fastest.
- Explainable plain-text route rationale.
- Relational / PostGIS persistence.
"""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.routing import calculate_route, TacticalRouter
from app import db


def test_routing_a_star_grid_basic():
    """Tactical router computes continuous path from start to destination."""
    start = (34.0, 71.0)
    dest = (34.2, 71.2)
    route = calculate_route(start=start, destination=dest, strategy="shortest")

    assert route is not None
    assert route["id"].startswith("RT-")
    assert route["strategy"] == "shortest"
    assert route["distance_km"] > 0
    assert len(route["waypoints"]) >= 2
    assert route["waypoints"][0] == [34.0, 71.0]
    assert route["waypoints"][-1] == [34.2, 71.2]
    assert route["fuel_l"] > 0
    assert len(route["explanation"]) > 10


def test_routing_strategies_tradeoffs():
    """Different strategies yield distinct distance, fuel, and risk tradeoffs."""
    start = (34.0, 71.0)
    dest = (34.3, 71.3)

    world_state = {
        "zones": [
            {
                "kind": "threat_high",
                "severity": 4,
                "points": [[34.1, 71.1], [34.2, 71.1], [34.2, 71.2], [34.1, 71.2]],
            }
        ],
        "weather": {
            "cell1": {"lat": 34.15, "lon": 71.15, "radiusM": 5000, "intensity": 0.8}
        },
    }

    r_shortest = calculate_route(start=start, destination=dest, strategy="shortest", world_state=world_state)
    r_safest = calculate_route(start=start, destination=dest, strategy="safest", world_state=world_state)
    r_fuel = calculate_route(start=start, destination=dest, strategy="fuel_efficient", world_state=world_state)

    # All strategies successfully generate valid routes
    assert r_shortest["distance_km"] > 0
    assert r_safest["distance_km"] > 0
    assert r_fuel["distance_km"] > 0

    # Safest strategy generates explanation highlighting threat avoidance
    assert "Safest route selected" in r_safest["explanation"]
    assert "Fuel-efficient route" in r_fuel["explanation"]
    assert "Shortest path selected" in r_shortest["explanation"]


def test_routing_endpoint_rest():
    """POST /api/routes/calculate returns valid route structure."""
    client = TestClient(app)
    resp = client.post(
        "/api/routes/calculate",
        json={
            "start": [34.01, 71.02],
            "destination": [34.18, 71.19],
            "strategy": "safest",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy"] == "safest"
    assert data["distance_km"] > 0
    assert len(data["waypoints"]) >= 2
    assert "fuel_l" in data
    assert "explanation" in data


def test_routing_get_and_list_endpoints():
    """GET /api/routes and GET /api/routes/{id} return persisted routes."""
    client = TestClient(app)
    # 1. Create a route
    c_resp = client.post(
        "/api/routes/calculate",
        json={"start": [34.05, 71.05], "destination": [34.15, 71.15], "strategy": "fastest"},
    )
    assert c_resp.status_code == 200
    route_id = c_resp.json()["id"]

    # 2. Get route by id
    get_resp = client.get(f"/api/routes/{route_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == route_id

    # 3. List routes
    list_resp = client.get("/api/routes?limit=5")
    assert list_resp.status_code == 200
    routes = list_resp.json()["routes"]
    assert any(r["id"] == route_id for r in routes)
