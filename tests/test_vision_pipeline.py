"""Tests for Phase 3B Real Vision Analytics Pipeline and Tracking Engine."""

from __future__ import annotations

import pytest
from app import db, vision
from app.main import app
from app.vision_pipeline import (
    TARGET_CLASSES,
    RealVisionPipeline,
    VisionProvider,
    vision_pipeline,
)
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def init_test_db():
    db.init()


def test_vision_provider_interface():
    """Verify VisionProvider abstract base class and RealVisionPipeline subclass."""
    assert issubclass(RealVisionPipeline, VisionProvider)
    assert isinstance(vision_pipeline, RealVisionPipeline)


def test_detection_classes_and_persistence():
    """Verify detect(None) returns all 5 military classes and persists to DB."""
    pipeline = RealVisionPipeline()
    dets = pipeline.detect(None)

    assert len(dets) >= 5
    labels = {d["class_label"] for d in dets}
    for expected_cls in TARGET_CLASSES:
        assert expected_cls in labels, f"Missing target class {expected_cls} in {labels}"

    for d in dets:
        assert "id" in d
        assert "confidence" in d
        assert 0.0 <= d["confidence"] <= 1.0
        assert "box" in d
        assert "lat" in d and "lon" in d

    # Verify database persistence
    saved = db.get_vision_detections(limit=10)
    assert len(saved) >= len(dets)


def test_persistent_multi_frame_tracking():
    """Verify consistent track_id, velocity, and heading calculation across multiple ticks."""
    pipeline = RealVisionPipeline()

    frame1_dets = [
        {
            "id": "DET-F1-01",
            "type": "detection",
            "class_label": "military_vehicle",
            "confidence": 0.95,
            "lat": 32.7400,
            "lon": 74.8800,
            "box": {"x": 30.0, "y": 40.0, "w": 20.0, "h": 20.0},
            "tick": 1,
        },
        {
            "id": "DET-F1-02",
            "type": "detection",
            "class_label": "uav",
            "confidence": 0.92,
            "lat": 32.7500,
            "lon": 74.8900,
            "box": {"x": 10.0, "y": 15.0, "w": 10.0, "h": 10.0},
            "tick": 1,
        },
    ]

    # Frame 1: initial tracks
    tracks_f1 = pipeline.track(frame1_dets, frame_id="frame_01", tick=1)
    assert len(tracks_f1) == 2
    trk1_id = tracks_f1[0]["track_id"]
    trk2_id = tracks_f1[1]["track_id"]
    assert trk1_id != trk2_id

    # Frame 2: units move northward
    frame2_dets = [
        {
            "id": "DET-F2-01",
            "type": "detection",
            "class_label": "military_vehicle",
            "confidence": 0.96,
            "lat": 32.7405,  # moved north by ~55m
            "lon": 74.8800,
            "box": {"x": 30.0, "y": 38.0, "w": 20.0, "h": 20.0},
            "tick": 5,
        },
        {
            "id": "DET-F2-02",
            "type": "detection",
            "class_label": "uav",
            "confidence": 0.94,
            "lat": 32.7510,  # moved north by ~111m
            "lon": 74.8900,
            "box": {"x": 10.0, "y": 12.0, "w": 10.0, "h": 10.0},
            "tick": 5,
        },
    ]

    tracks_f2 = pipeline.track(frame2_dets, frame_id="frame_02", tick=5)
    assert len(tracks_f2) == 2
    # Verify consistent track_id assignment
    assert tracks_f2[0]["track_id"] == trk1_id
    assert tracks_f2[1]["track_id"] == trk2_id

    # Verify velocity and heading vector calculation
    assert tracks_f2[0]["velocity_mps"] > 0.0
    assert 350.0 <= tracks_f2[0]["heading_deg"] <= 360.0 or 0.0 <= tracks_f2[0]["heading_deg"] <= 10.0
    assert tracks_f2[1]["velocity_mps"] > 0.0

    # Verify persistence to DB
    persisted = db.get_vision_track(trk1_id)
    assert persisted is not None
    assert persisted["track_id"] == trk1_id
    assert persisted["velocity_mps"] > 0.0


def test_perimeter_intrusion_detection():
    """Verify perimeter intrusion triggers for targets inside restricted zones."""
    pipeline = RealVisionPipeline()

    restricted_zones = [
        {
            "zone_id": "ZONE-TEST-FORBIDDEN",
            "name": "Restricted Command Perimeter",
            "zone_type": "no_go",
            "coordinates": [
                {"lat": 32.7400, "lon": 74.8800},
                {"lat": 32.7450, "lon": 74.8800},
                {"lat": 32.7450, "lon": 74.8850},
                {"lat": 32.7400, "lon": 74.8850},
            ],
        }
    ]

    dets = [
        {
            "id": "DET-INTRUDER",
            "class_label": "military_vehicle",
            "lat": 32.7425,  # inside
            "lon": 74.8825,
            "tick": 12,
        },
        {
            "id": "DET-OUTSIDE",
            "class_label": "personnel",
            "lat": 32.7550,  # outside
            "lon": 74.8950,
            "tick": 12,
        },
    ]

    intrusions = pipeline.check_perimeter_intrusions(dets, restricted_zones)
    assert len(intrusions) == 1
    assert intrusions[0]["detection_id"] == "DET-INTRUDER"
    assert intrusions[0]["zone_id"] == "ZONE-TEST-FORBIDDEN"
    assert intrusions[0]["severity"] == "critical"


def test_activity_classification():
    """Verify activity classification: nominal, in_transit, stalled, intruding, suspicious."""
    pipeline = RealVisionPipeline()

    tracks = [
        {
            "track_id": "TRK-INTRUDING",
            "class_label": "personnel",
            "activity_state": "intruding",
            "velocity_mps": 0.5,
            "heading_deg": 45.0,
            "history": [],
        },
        {
            "track_id": "TRK-MOVING",
            "class_label": "convoy_truck",
            "activity_state": "nominal",
            "velocity_mps": 14.2,
            "heading_deg": 90.0,
            "history": [{"heading_deg": 90.0}],
        },
        {
            "track_id": "TRK-STALLED",
            "class_label": "military_vehicle",
            "activity_state": "in_transit",
            "velocity_mps": 0.05,
            "heading_deg": 180.0,
            "history": [{"heading_deg": 180.0}, {"heading_deg": 180.0}],
        },
        {
            "track_id": "TRK-SUSPICIOUS",
            "class_label": "uav",
            "activity_state": "nominal",
            "velocity_mps": 8.0,
            "heading_deg": 270.0,
            "history": [{"heading_deg": 30.0}, {"heading_deg": 270.0}],  # 120 deg jump
        },
        {
            "track_id": "TRK-NOMINAL",
            "class_label": "personnel",
            "activity_state": "nominal",
            "velocity_mps": 0.0,
            "heading_deg": 0.0,
            "history": [],
        },
    ]

    analyzed = pipeline.analyze_activity(tracks)
    states = {t["track_id"]: t["activity_state"] for t in analyzed}

    assert states["TRK-INTRUDING"] == "intruding"
    assert states["TRK-MOVING"] == "in_transit"
    assert states["TRK-STALLED"] == "stalled"
    assert states["TRK-SUSPICIOUS"] == "suspicious"
    assert states["TRK-NOMINAL"] == "nominal"


def test_adjudication_pipeline_integration():
    """Verify /vision/adjudicate uses real analytics through vision_pipeline."""
    detection_events = [
        {
            "id": "DET-ADJ-01",
            "type": "detection",
            "entityId": "CAM-01-NORTH",
            "tick": 15,
            "payload": {
                "label": "military_vehicle",
                "confidence": 0.95,
                "lat": 32.7410,
                "lon": 74.8820,
                "model": "yolov8n-doip-v1.4",
            },
        },
        {
            "id": "DET-ADJ-02",
            "type": "detection",
            "entityId": "CAM-02-VALLEY",
            "tick": 15,
            "payload": {
                "label": "convoy_truck",
                "confidence": 0.65,
                "lat": 32.7460,
                "lon": 74.8870,
                "model": "yolov8n-doip-v1.4",
            },
        },
    ]

    res = vision.adjudicate(detection_events, min_confidence=0.50, auto_accept_above=0.85)

    assert "tracks" in res
    assert "intrusions" in res
    assert "analytics" in res
    assert len(res["tracks"]) >= 2
    assert "activity_states" in res["analytics"]


def test_rest_api_vision_endpoints():
    """Verify REST API endpoints /vision/adjudicate and /vision/tracks with auth."""
    from app import auth

    client = TestClient(app)
    token = auth.issue("commander", "admin")
    headers = {"Authorization": f"Bearer {token}"}

    # Test /vision/adjudicate
    adj_res = client.post(
        "/vision/adjudicate",
        headers=headers,
        json={
            "detections": [
                {
                    "id": "DET-API-01",
                    "type": "detection",
                    "entityId": "CAM-01",
                    "tick": 20,
                    "payload": {
                        "label": "military_vehicle",
                        "confidence": 0.92,
                        "lat": 32.7410,
                        "lon": 74.8820,
                    },
                }
            ],
            "minConfidence": 0.50,
            "autoAcceptAbove": 0.80,
        },
    )
    assert adj_res.status_code == 200
    body = adj_res.json()
    assert "tracks" in body
    assert "analytics" in body
    assert len(body["confirmed"]) == 1

    # Test /vision/tracks
    tracks_res = client.get("/vision/tracks", headers=headers)
    assert tracks_res.status_code == 200
    tracks_data = tracks_res.json()
    assert "tracks" in tracks_data
    assert tracks_data["count"] >= 1
