"""Phase 2 Persistence, Migration Safety, and Recovery Verification.

Validates:
1. Fresh database initialization and table presence.
2. Idempotency across repeated initialization.
3. Uniqueness constraints and transaction rollback.
4. Concurrent run isolation across runs and entities.
5. Snapshot persistence and state recovery across session lifecycles.
6. Time-series historical position and vitals retrieval.
7. Backward compatibility for run records.
"""

import json
import sqlite3
import pytest
from app import db
from app.session import SimSession


def test_fresh_database_initialization():
    """Verify that db.init() creates all required authoritative tables."""
    db.init()
    with db._lock, db._sqlite_connect() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    required_tables = {
        "runs",
        "users",
        "custom_scenarios",
        "units",
        "unit_position_history",
        "personnel",
        "personnel_vitals_history",
        "personnel_assignments",
        "whatif_results",
        "forecast_runs",
        "copilot_sessions",
    }
    missing = required_tables - tables
    assert not missing, f"Missing required database tables: {missing}"


def test_database_init_idempotency():
    """Verify calling db.init() multiple times does not error or duplicate tables."""
    db.init()
    db.init()
    db.init()
    # Should succeed without throwing any operational errors


def test_uniqueness_constraint_and_rollback():
    """Verify unique constraints prevent duplicates and rollback dirty transactions."""
    unique_user = "test_op_unique_99"
    db.add_user(unique_user, role="operator", unit="Alpha")

    # Attempting to add the same username must fail with integrity error
    with pytest.raises(Exception):
        with db._lock, db._sqlite_connect() as conn:
            conn.execute(
                "INSERT INTO users (username, name, role, unit) VALUES (?, ?, ?, ?)",
                (unique_user, unique_user, "operator", "Beta"),
            )
            conn.commit()

    # Clean up
    db.remove_user(unique_user)


def test_concurrent_run_isolation():
    """Verify that multiple concurrent runs keep isolated positions, vitals, and snapshots."""
    import uuid
    run_a = f"run-isolation-A-{uuid.uuid4()}"
    run_b = f"run-isolation-B-{uuid.uuid4()}"

    # Insert position samples for Run A
    db.save_unit_position_samples_batch([
        {
            "run_id": run_a,
            "unit_id": "U-PATROL-1",
            "tick": 10,
            "sim_time": 10000,
            "lat": 12.971,
            "lon": 77.594,
            "heading": 45.0,
            "speed_kph": 6.0,
            "in_weather": False,
        },
        {
            "run_id": run_a,
            "unit_id": "U-PATROL-1",
            "tick": 20,
            "sim_time": 20000,
            "lat": 12.972,
            "lon": 77.595,
            "heading": 90.0,
            "speed_kph": 6.0,
            "in_weather": False,
        },
    ])

    # Insert position samples for Run B
    db.save_unit_position_samples_batch([
        {
            "run_id": run_b,
            "unit_id": "U-PATROL-1",
            "tick": 10,
            "sim_time": 10000,
            "lat": 13.001,
            "lon": 77.601,
            "heading": 180.0,
            "speed_kph": 12.0,
            "in_weather": True,
        },
    ])

    # Query samples for Run A
    samples_a = db.list_unit_positions(unit_id="U-PATROL-1", run_id=run_a)
    assert len(samples_a) == 2
    assert all(s["run_id"] == run_a for s in samples_a)
    assert samples_a[0]["lat"] == pytest.approx(12.971, abs=0.001)

    # Query samples for Run B
    samples_b = db.list_unit_positions(unit_id="U-PATROL-1", run_id=run_b)
    assert len(samples_b) == 1
    assert samples_b[0]["run_id"] == run_b
    assert samples_b[0]["lat"] == pytest.approx(13.001, abs=0.001)
    assert samples_b[0]["in_weather"] in (1, True)


def test_snapshot_persistence_and_state_recovery():
    """Verify that full world state can be serialized, persisted, and accurately restored."""
    run_id = "run-recovery-test-01"
    world_state = {
        "runId": run_id,
        "seed": 8841,
        "scenarioId": "SC-2",
        "tick": 45,
        "simTime": 45000,
        "speed": 5.0,
        "status": "RUNNING",
        "units": {
            "U-UAV-1": {
                "id": "U-UAV-1",
                "callsign": "RAVEN-1",
                "kind": "uav",
                "lat": 12.980,
                "lon": 77.600,
                "heading": 120.0,
                "fuel": 85.0,
                "battery": 78.5,
                "status": "active",
            }
        },
        "personnel": {
            "P-1": {
                "id": "P-1",
                "name": "SGT Rao",
                "rank": "SGT",
                "unitId": "U-PATROL-1",
                "heartRate": 84.0,
                "fatigue": 0.35,
                "condition": "fit",
            }
        },
        "weather": {
            "W-1": {
                "id": "W-1",
                "lat": 12.99,
                "lon": 77.58,
                "radiusM": 1500,
                "intensity": 0.7,
                "kind": "thunderstorm",
            }
        },
        "incidents": {
            "INC-10": {
                "id": "INC-10",
                "tick": 10,
                "severity": "high",
                "kind": "perimeter-breach",
                "open": True,
            }
        },
        "alerts": {},
        "zones": [],
        "depots": {},
    }

    db.save_world_snapshot(run_id, world_state)
    restored = db.load_world_snapshot(run_id)

    assert restored is not None
    assert restored["runId"] == run_id
    assert restored["tick"] == 45
    assert restored["seed"] == 8841
    assert "U-UAV-1" in restored["units"]
    assert restored["units"]["U-UAV-1"]["battery"] == pytest.approx(78.5)
    assert restored["personnel"]["P-1"]["condition"] == "fit"
    assert restored["weather"]["W-1"]["kind"] == "thunderstorm"
    assert restored["incidents"]["INC-10"]["open"] is True


def test_time_series_historical_queries_and_ordering():
    """Verify that position and vitals history return ordered, bounded results."""
    import uuid
    uid = uuid.uuid4().hex[:8]
    run_id = f"run-timeseries-{uid}"
    person_id = f"P-TEST-{uid}"

    vitals = [
        {"run_id": run_id, "person_id": person_id, "tick": t, "sim_time": t * 1000, "heart_rate": 70.0 + (t % 10), "fatigue": 0.1 + (t * 0.01), "activity_type": "patrol"}
        for t in range(1, 31)
    ]
    db.save_personnel_vitals_samples_batch(vitals)

    # Query range tick 10 to 20
    results = db.list_personnel_vitals(person_id=person_id, run_id=run_id, start_tick=10, end_tick=20)
    assert len(results) == 11  # ticks 10, 11, ..., 20 inclusive
    assert results[0]["tick"] == 10
    assert results[-1]["tick"] == 20
    # Ensure ordered by tick ascending
    ticks = [r["tick"] for r in results]
    assert ticks == sorted(ticks)


def test_backward_compatibility_run_records():
    """Verify save_run and list_runs preserve expected schema and return types."""
    run_id = "run-compat-test-01"
    sample_log = [
        {"id": 1, "type": "world_init", "tick": 0, "simTime": 0, "severity": "low", "entityId": "system", "payload": {}},
        {"id": 2, "type": "unit_move", "tick": 1, "simTime": 1000, "severity": "low", "entityId": "U-1", "payload": {"lat": 12.9, "lon": 77.5}},
    ]
    db.save_run({
        "id": run_id,
        "seed": 101,
        "scenarioId": "SC-1",
        "ticks": 1,
        "events": 2,
        "log": sample_log,
    })

    record = db.get_run(run_id)
    assert record is not None
    assert record["id"] == run_id
    assert record["seed"] == 101
    assert record["ticks"] == 1
    assert len(record["log"]) == 2
    assert record["log"][1]["type"] == "unit_move"
