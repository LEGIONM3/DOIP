"""Phase 3 Run Control, Live Map, and WebSocket Dataflow Verification.

Validates:
1. API endpoints for start, pause, resume, speed, and stop.
2. Live WebSocket protocol (/ws/sim/{run_id}) event streaming and command processing.
3. Engine state synchronization with published events.
"""

import asyncio
import pytest
from starlette.testclient import TestClient
from app.main import app, _sessions, _sessions_lock
from app import auth


@pytest.fixture
def auth_headers():
    token = auth.issue("commander", "admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_token():
    return auth.issue("commander", "admin")


def test_api_run_control_lifecycle(auth_headers):
    """Test start -> pause -> resume -> speed -> stop via REST API."""
    client = TestClient(app)
    run_id = "test-api-lifecycle-01"

    # Start
    res = client.post("/api/sim/start", json={"seed": 20260101, "scenario_id": "SC-1", "speed": 2.0, "run_id": run_id}, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["status"] == "RUNNING"
    assert data["speed"] == 2.0

    # Status check
    res = client.get(f"/api/sim/status?run_id={run_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "RUNNING"

    # Pause
    res = client.post("/api/sim/pause", json={"run_id": run_id}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "PAUSED"

    # Speed update
    res = client.post("/api/sim/speed", json={"run_id": run_id, "speed": 16.0}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["speed"] == 16.0

    # Resume
    res = client.post("/api/sim/resume", json={"run_id": run_id}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "RUNNING"

    # Stop
    res = client.post("/api/sim/stop", json={"run_id": run_id}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "STOPPED"


def test_ws_sim_live_streaming(auth_token):
    """Test live WebSocket streaming, command intake, and broadcast."""
    client = TestClient(app)
    run_id = "test-ws-stream-01"

    with client.websocket_connect(f"/ws/sim/{run_id}?token={auth_token}&seed=20260101&scenarioId=SC-1&speed=20.0") as ws:
        # First message should be log_replay
        init_frame = ws.receive_json()
        assert init_frame["type"] == "log_replay"
        assert "events" in init_frame
        assert "snapshot" in init_frame

        # Send speed change command
        ws.send_json({"cmd": "speed", "value": 10.0})

        # Wait for live events batch
        msg = ws.receive_json()
        assert msg["type"] == "events"
        assert len(msg["events"]) > 0

        # Send pause
        ws.send_json({"cmd": "pause"})
        # Should receive pause confirmation event or live batch containing it
        pause_seen = False
        for _ in range(5):
            m = ws.receive_json()
            if m["type"] == "events":
                for e in m["events"]:
                    if e.get("type") == "system" and e.get("payload", {}).get("status") == "PAUSED":
                        pause_seen = True
                        break
            if pause_seen:
                break
        assert pause_seen

        # Send stop
        ws.send_json({"cmd": "stop"})
