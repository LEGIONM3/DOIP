"""Phase 1C Test Suite: PostgreSQL/PostGIS Engine with SQLite Seamless Fallback.

Invariants:
- SQLAlchemy 2.0 ORM models for all domain entities.
- Dual-mode support (PostgreSQL primary / SQLite fallback).
- Spatial types (SpatialPoint, SpatialPolygon) functioning seamlessly across both engines.
- Spatial containment and proximity helpers (spatial_query_zones_containing, spatial_query_events_within).
- Clean CRUD for users, runs, events, whatif, zones, doctrine, and audit trail.
"""

import json
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import db
from app.models import (
    AuditEvent,
    Base,
    DoctrineChunk,
    DoctrineDocument,
    Run,
    SimEvent,
    TacticalZone,
    User,
    WhatIfResult,
)


def test_database_status_and_connection():
    """Database status probe returns healthy status and engine type."""
    status = db.get_database_status()
    assert status["status"] == "online"
    assert status["connected"] is True
    assert status["type"] in ["sqlite", "postgresql"]


def test_audit_event_persistence():
    """Operational audit logging persists and retrieves audit records."""
    test_actor = "test_operator_pytest"
    test_action = "ENGAGE_RADAR_TEST"
    test_detail = "Simulated radar sweep for unit pytest"

    db.add_audit(test_actor, test_action, test_detail)

    logs = db.list_audit(limit=20)
    assert any(
        log["actor"] == test_actor and log["action"] == test_action for log in logs
    ), "Newly added audit event must appear in audit log"


def test_user_roster_crud():
    """User roster supports add, list, and removal with DB persistence."""
    test_name = "pytest_agent_user"
    test_role = "operator"
    test_unit = "UNIT-TEST-99"

    # Clean up previous runs if needed
    db.remove_user(test_name)

    # Add user
    added = db.add_user(name=test_name, role=test_role, unit=test_unit)
    assert added["name"] == test_name

    # List users
    users = db.list_users()
    assert any(u["name"] == test_name and u["role"] == test_role for u in users)

    # Remove user
    removed = db.remove_user(test_name)
    assert removed is True
    assert not any(u["name"] == test_name for u in db.list_users())


def test_whatif_persistence():
    """What-if Monte Carlo results persist with deltas and scores."""
    result_id = db.save_whatif_result(
        seed=4242,
        scenario_id="SC-TEST",
        ticks=60,
        actions=[{"tick": 5, "kind": "REROUTE"}],
        deltas={"threat_score": {"baseline": 80.0, "branch": 45.0, "delta": -35.0}},
        score=0.88,
    )
    assert result_id > 0

    results = db.list_whatif_results(limit=10)
    assert any(r["id"] == result_id and r["seed"] == 4242 for r in results)


def test_doctrine_document_and_chunks_persistence():
    """Doctrine documents and chunks persist with metadata and vector embeddings."""
    db.save_doctrine_document(
        doc_id="TEST-01",
        category="test",
        title="Test Doctrine Manual",
        tags=["test", "unit"],
        version="1.0",
        source_file="test/TEST-01.md",
        content="This is a test doctrine document for unit tests.",
    )

    doc = db.get_doctrine_document("TEST-01")
    assert doc is not None
    assert doc["title"] == "Test Doctrine Manual"
    assert "test" in doc["tags"]

    # Persist chunks
    chunk_count = db.save_doctrine_chunks([
        {
            "chunk_id": "TEST-01-SEC-01-intro",
            "document_id": "TEST-01",
            "document_type": "test",
            "section": "1. Introduction",
            "source": "test/TEST-01.md",
            "citation": "TEST-01 §1",
            "text": "Introductory section text for unit test verification.",
            "token_count": 8,
            "embedding": [0.1] * 384,
        }
    ])
    assert chunk_count == 1

    chunks = db.get_doctrine_chunks("TEST-01")
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "TEST-01-SEC-01-intro"
    assert len(chunks[0]["embedding"]) == 384


def test_spatial_zone_containment():
    """Spatial query correctly detects when a coordinate is inside or outside a tactical zone."""
    # Define a bounding polygon around 12.0-13.0 Lat, 77.0-78.0 Lon
    zone_coords = [
        {"lat": 12.0, "lon": 77.0},
        {"lat": 13.0, "lon": 77.0},
        {"lat": 13.0, "lon": 78.0},
        {"lat": 12.0, "lon": 78.0},
    ]

    db.save_tactical_zone(
        zone_id="ZONE-TEST-ALPHA",
        name="Alpha Test Geofence",
        zone_type="NFZ",
        coordinates=zone_coords,
        min_alt_m=0.0,
        max_alt_m=5000.0,
        active=True,
    )

    # Point strictly inside: 12.5, 77.5
    inside_zones = db.spatial_query_zones_containing(lat=12.5, lon=77.5)
    assert any(z["zone_id"] == "ZONE-TEST-ALPHA" for z in inside_zones)

    # Point strictly outside: 15.0, 80.0
    outside_zones = db.spatial_query_zones_containing(lat=15.0, lon=80.0)
    assert not any(z["zone_id"] == "ZONE-TEST-ALPHA" for z in outside_zones)


def test_spatial_event_proximity():
    """Spatial query retrieves events within a given kilometer radius."""
    run_id = "RUN-SPATIAL-TEST"
    # Save a run first to satisfy FK constraint
    db.save_run({
        "id": run_id,
        "seed": 999,
        "scenario_id": "SC-1",
        "ticks": 10,
        "events": 2,
        "log": [],
    })

    # Save 2 events: one near (12.0, 77.0) and one far (15.0, 80.0)
    db.save_events_batch([
        {
            "run_id": run_id,
            "tick": 1,
            "event_type": "incident_open",
            "severity": "high",
            "entity_id": "INC-NEAR",
            "payload": {"title": "Near event"},
            "lat": 12.01,
            "lon": 77.01,
        },
        {
            "run_id": run_id,
            "tick": 2,
            "event_type": "incident_open",
            "severity": "low",
            "entity_id": "INC-FAR",
            "payload": {"title": "Far event"},
            "lat": 15.0,
            "lon": 80.0,
        },
    ])

    # Search within 10 km of (12.0, 77.0)
    nearby_events = db.spatial_query_events_within(lat=12.0, lon=77.0, radius_km=15.0)
    nearby_entities = {e["entity_id"] for e in nearby_events}

    assert "INC-NEAR" in nearby_entities
    assert "INC-FAR" not in nearby_entities
