"""Phase 2C Test Suite: War Room Real-Time Collaboration.

Invariants:
- Multi-operator presence tracking, roles, and status.
- Tactical task creation and incident assignment handoff.
- Real-time operations chat and map annotations.
- WebSocket stream handshake and message dispatch.
"""

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.warroom import WarRoomHub, warroom_hub
from app import db


def test_warroom_rest_endpoints():
    """REST endpoints for presence and tasks function correctly."""
    client = TestClient(app)

    # 1. Presence check
    resp_pres = client.get("/api/warroom/presence")
    assert resp_pres.status_code == 200
    assert "presence" in resp_pres.json()

    # 2. Task creation
    resp_task = client.post("/api/warroom/tasks", json={
        "title": "Clear North Corridor",
        "description": "Patrol route for hostile activity",
        "priority": "HIGH",
    })
    assert resp_task.status_code == 200
    task_id = resp_task.json()["id"]
    assert task_id is not None

    # 3. Task assignment
    resp_assign = client.post(f"/api/warroom/tasks/{task_id}/assign", json={
        "assigned_to": "operator_alpha",
        "reason": "Direct sector responsibility",
    })
    assert resp_assign.status_code == 200
    assert resp_assign.json()["task"]["assigned_to"] == "operator_alpha"

    # 4. List tasks
    resp_list = client.get("/api/warroom/tasks")
    assert resp_list.status_code == 200
    assert any(t["id"] == task_id for t in resp_list.json()["tasks"])


def test_warroom_websocket_protocol():
    """WebSocket connection handshakes, hydrates state, and parses messages."""
    client = TestClient(app)

    with client.websocket_connect("/ws/warroom?token=demo") as websocket:
        # Receive initial snapshots
        data1 = websocket.receive_json()
        assert data1["type"] in ("warroom_sync", "snapshot")

        # Send chat message
        websocket.send_json({
            "type": "chat_message",
            "payload": {
                "username": "tester",
                "name": "Test Operator",
                "role": "operator",
                "text": "Status nominal in sector 4.",
            },
        })

        # Send cursor move
        websocket.send_json({
            "type": "cursor_move",
            "payload": {
                "username": "tester",
                "lat": 34.05,
                "lon": 71.55,
            },
        })

        # Send map annotation
        websocket.send_json({
            "type": "map_annotation",
            "payload": {
                "id": "ANN-TEST-01",
                "kind": "marker",
                "coordinates": [[34.05, 71.55]],
                "title": "Observation Post Echo",
                "color": "#10B981",
            },
        })
