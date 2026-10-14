"""Phase 4I & 4J Test Suite: Event Streaming Platform & Operational Data Lake.

Invariants:
- High-throughput event streaming with sequential offset tracking and partition support.
- Stream replay across arbitrary offset ranges.
- Real-time materialized state projections from event streams.
- Operational Data Lake object storage (S3/MinIO abstraction) and historical analytics.
"""

from pathlib import Path
import pytest
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.event_stream import EventBus, event_bus
from app.datalake import OperationalDataLake, data_lake
from app import db


import uuid


def test_event_bus_publish_and_monotonic_offsets():
    """Verify published events receive monotonically increasing sequential offsets."""
    bus = EventBus(buffer_size=50)
    stream_name = f"test.telemetry.{uuid.uuid4().hex[:6]}"

    ev1 = bus.publish(stream_name, "position_update", {"unit_id": "UAV-99", "alt": 1200})
    ev2 = bus.publish(stream_name, "position_update", {"unit_id": "UAV-99", "alt": 1250})
    ev3 = bus.publish(stream_name, "fuel_alert", {"unit_id": "UAV-99", "pct": 18.0})

    assert ev1["offset"] == 1
    assert ev2["offset"] == 2
    assert ev3["offset"] == 3
    assert ev3["event_type"] == "fuel_alert"

    # Verify persistence in database
    db_events = db.list_stream_events(stream_name=stream_name, from_offset=1, limit=10)
    assert len(db_events) == 3
    assert db_events[0]["offset"] == 1
    assert db_events[1]["offset"] == 2
    assert db_events[2]["offset"] == 3


def test_event_bus_replay_and_projection():
    """Verify offset range replay and real-time state projection computation."""
    bus = EventBus(buffer_size=100)
    stream_name = f"test.replay.{uuid.uuid4().hex[:6]}"

    for i in range(1, 11):
        bus.publish(stream_name, "tick_event", {"tick": i * 10})

    # 1. Replay offset slice [3, 7]
    replayed = bus.event_replay(stream_name, from_offset=3, to_offset=7)
    assert len(replayed) == 5
    assert [e["offset"] for e in replayed] == [3, 4, 5, 6, 7]

    # 2. Materialized projection
    projection = bus.event_projection(stream_name)
    assert projection["stream_name"] == stream_name
    assert projection["latest_offset"] == 10
    assert projection["event_types_breakdown"].get("tick_event", 0) == 10
    assert projection["last_event"]["payload"]["tick"] == 100


def test_operational_data_lake_storage_and_analytics():
    """Verify data lake storage abstraction, listing, and historical analytics."""
    lake = OperationalDataLake()
    bucket = f"raw-telemetry-{uuid.uuid4().hex[:6]}"
    key = "mission_log_2026_01.json"
    sample_data = {"mission_id": "MSN-TEST-LAKE", "waypoints_count": 8, "status": "completed"}

    # 1. Put object
    stored = lake.put_object(
        bucket=bucket,
        key=key,
        data=sample_data,
        metadata={"classification": "SECRET-NOFORN"},
    )
    assert stored["bucket"] == bucket
    assert stored["key"] == key
    assert stored["size_bytes"] > 0

    # 2. Get object
    retrieved = lake.get_object(bucket, key)
    assert retrieved is not None
    assert retrieved["data"]["mission_id"] == "MSN-TEST-LAKE"

    # 3. List objects
    objects = lake.list_objects(bucket=bucket)
    assert len(objects) >= 1
    assert any(o["key"] == key for o in objects)

    # 4. Historical analysis
    analysis = lake.historical_analysis(bucket=bucket)
    assert analysis["total_objects"] >= 1
    assert analysis["total_size_bytes"] > 0
    assert "buckets_distribution" in analysis


def test_streaming_and_datalake_rest_api_endpoints():
    """Verify FastAPI endpoints for event streaming and data lake."""
    client = TestClient(app)

    # 1. Publish Event
    pub_req = {
        "stream_name": "api.test.stream",
        "event_type": "THREAT_SPIKE",
        "payload": {"radar_azimuth": 274.5, "intensity_db": 42.0},
        "partition": 0,
    }
    res_pub = client.post("/api/events/publish", json=pub_req)
    assert res_pub.status_code == 200
    pub_res = res_pub.json()
    assert pub_res["event_type"] == "THREAT_SPIKE"
    assert pub_res["offset"] >= 1

    # 2. Replay Events
    res_rep = client.get("/api/events/replay?stream_name=api.test.stream&from_offset=0")
    assert res_rep.status_code == 200
    assert len(res_rep.json()) >= 1

    # 3. Event Projection
    res_proj = client.get("/api/events/projection/api.test.stream")
    assert res_proj.status_code == 200
    assert "event_types_breakdown" in res_proj.json()

    # 4. Data Lake Put Object
    obj_req = {
        "bucket": "operational-briefs",
        "key": "brief_REST_01.json",
        "data": {"title": "REST Test Brief", "readiness": 91.5},
        "content_type": "application/json",
        "metadata": {"origin": "automated-test"},
    }
    res_put = client.post("/api/datalake/objects", json=obj_req)
    assert res_put.status_code == 200
    assert res_put.json()["key"] == "brief_REST_01.json"

    # 5. Data Lake List Objects
    res_list = client.get("/api/datalake/objects?bucket=operational-briefs")
    assert res_list.status_code == 200
    assert any(o["key"] == "brief_REST_01.json" for o in res_list.json())

    # 6. Data Lake Analysis
    res_an = client.get("/api/datalake/analysis?bucket=operational-briefs")
    assert res_an.status_code == 200
    assert "total_objects" in res_an.json()
