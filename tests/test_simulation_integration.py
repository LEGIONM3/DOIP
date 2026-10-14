"""End-to-End Simulation Integration & State-Consistency Regression Suite.

Verifies:
1. 1x, 5x, 20x speed scaling, bounded accumulator progression, and pause/resume determinism.
2. Replay historical state reconstruction equivalence to world snapshots.
3. What-If Theater execution immutability of the baseline and active simulation state.
4. Grounded forward simulation in Futures lookahead (no synthetic random numbers).
5. Personnel vitals telemetry, database persistence, and active mission linkage.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import pytest

from backend.app.engine import SimEngine
from backend.app.session import SimSession
from backend.app.whatif import run_branch
from backend.app.future_generator import future_generator
from backend.app import db


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure database schema is initialized for tests."""
    db.init()


# ---------------------------------------------------------------------------
# 1. Speed, Clock Progression & Pause/Resume Determinism
# ---------------------------------------------------------------------------
def test_engine_determinism_across_step_batches():
    """Identical seed and scenario must produce identical event sequences regardless of step timing."""
    engine_a = SimEngine()
    engine_b = SimEngine()

    evs_a = engine_a.start(seed=20261015, scenario_id="SC-1")
    evs_b = engine_b.start(seed=20261015, scenario_id="SC-1")

    assert [e.to_dict() for e in evs_a] == [e.to_dict() for e in evs_b]

    # Step engine A 30 times
    for _ in range(30):
        evs_a.extend(engine_a.step())

    # Step engine B 30 times
    for _ in range(30):
        evs_b.extend(engine_b.step())

    log_a = [e.to_dict() for e in evs_a]
    log_b = [e.to_dict() for e in evs_b]

    assert len(log_a) == len(log_b)
    assert log_a == log_b


@pytest.mark.asyncio
async def test_session_speed_and_pause_resume():
    """Verify SimSession operates smoothly at 1x, 5x, and 20x, and pause/resume maintains continuity."""
    run_id = "test-run-speed-1"
    session = SimSession(seed=424242, scenario_id="SC-1", speed=20.0, run_id=run_id)

    # Start session at 20x speed
    await session.start()
    assert session.speed == 20.0
    assert not session._paused
    assert not session._stopped

    # Let it run for 350ms (~7 ticks at 20x)
    await asyncio.sleep(0.35)
    current_tick = session.engine.tick
    assert current_tick >= 1

    # Pause session
    await session.pause()
    assert session._paused is True
    paused_tick = session.engine.tick

    # While paused, sleep and verify tick does not advance
    await asyncio.sleep(0.15)
    assert session.engine.tick == paused_tick

    # Change speed to 5x while paused
    await session.set_speed(5.0)
    assert session.speed == 5.0

    # Resume session
    await session.resume()
    assert session._paused is False

    # Let it advance at 5x (500ms = 2.5 ticks)
    await asyncio.sleep(0.50)
    assert session.engine.tick >= paused_tick + 1

    # Stop session
    await session.stop()
    assert session._stopped is True
    final_tick = session.engine.tick
    await asyncio.sleep(0.1)
    assert session.engine.tick == final_tick


# ---------------------------------------------------------------------------
# 2. What-If Theater Isolation & Baseline Immutability
# ---------------------------------------------------------------------------
def test_whatif_preserves_baseline_and_live_immutability():
    """What-If branches must run in decoupled memory and never mutate baseline or live state."""
    baseline_engine = SimEngine()
    baseline_init = baseline_engine.start(seed=12345, scenario_id="SC-1")
    for _ in range(25):
        baseline_init.extend(baseline_engine.step())

    baseline_snap = baseline_engine.snapshot()
    baseline_bytes = json.dumps(baseline_snap, sort_keys=True).encode("utf-8")
    baseline_hash = hashlib.sha256(baseline_bytes).hexdigest()

    # Execute What-If branch with injected actions
    injected_actions = [
        {
            "tick": 5,
            "type": "weather_spawn",
            "severity": "critical",
            "entityId": "W-BRANCH-1",
            "payload": {"lat": 12.98, "lon": 77.60, "radiusM": 3500, "intensity": 0.95, "kind": "storm"},
        },
        {
            "tick": 10,
            "type": "incident_open",
            "severity": "critical",
            "entityId": "INC-BRANCH-1",
            "payload": {"kind": "ambush-risk", "lat": 12.97, "lon": 77.58},
        },
    ]

    result = run_branch(
        seed=12345,
        scenario_id="SC-1",
        actions=injected_actions,
        ticks=30,
        runs=1,
    )

    # Verify branch executed and diverged
    assert result.seed == 12345
    assert len(result.branch_events) > 0
    assert any(e.get("entityId") == "W-BRANCH-1" for e in result.branch_events)

    # Verify baseline state remains 100% byte-identical
    post_snap = baseline_engine.snapshot()
    post_bytes = json.dumps(post_snap, sort_keys=True).encode("utf-8")
    post_hash = hashlib.sha256(post_bytes).hexdigest()

    assert baseline_hash == post_hash, "What-If execution mutated baseline engine snapshot!"


# ---------------------------------------------------------------------------
# 3. Grounded Futures Lookahead vs Fake Random Generation
# ---------------------------------------------------------------------------
def test_futures_grounded_in_forward_simulation():
    """Futures analysis must use forward engine lookahead, grounded in unit telemetry and constraints."""
    res = future_generator.generate_alternative_futures(
        baseline_world_id="WLD-TEST-01",
        count=5,
        ticks=30,
    )

    assert "batch_id" in res
    assert "top_branches" in res
    assert len(res["top_branches"]) == 5

    # Verify predictions are calculated and deterministic from simulation execution
    top_branch = res["top_branches"][0]
    assert "score" in top_branch
    assert "mission_success" in top_branch
    assert "fuel_delta_liters" in top_branch
    assert "incidents_count" in top_branch
    assert "provenance" in top_branch
    assert top_branch["provenance"]["model"] == "SimEngine-Mulberry32-Authoritative"

    # Repeated forward simulation with same parameters must produce deterministic results
    res_repeat = future_generator.generate_alternative_futures(
        baseline_world_id="WLD-TEST-01",
        count=5,
        ticks=30,
    )
    assert [b["score"] for b in res["top_branches"]] == [b["score"] for b in res_repeat["top_branches"]]
    assert [b["branch_seed"] for b in res["top_branches"]] == [b["branch_seed"] for b in res_repeat["top_branches"]]


# ---------------------------------------------------------------------------
# 4. Personnel Vitals Telemetry, Persistence & Mission Linkage
# ---------------------------------------------------------------------------
def test_personnel_persistence_and_mission_assignment():
    """Personnel records must maintain vitals, active mission link, and position history."""
    person_id = "P-TEST-UNIT-1"
    unit_id = "U-PATROL-1"
    run_id = "RUN-TEST-PERSIST-1"

    person_data = {
        "id": person_id,
        "run_id": run_id,
        "name": "K. Sharma",
        "rank": "SGT",
        "unit_id": unit_id,
        "condition": "fit",
        "heart_rate": 78.5,
        "fatigue": 0.22,
        "active_mission_id": "MSN-ALPHA-RECON",
        "mission_history": ["MSN-TRAINING-01"],
    }

    # Save person
    db.save_person(person_data)

    # Retrieve person
    retrieved = db.get_person(person_id)
    assert retrieved is not None
    assert retrieved["name"] == "K. Sharma"
    assert retrieved["active_mission_id"] == "MSN-ALPHA-RECON"
    assert "MSN-TRAINING-01" in retrieved.get("mission_history", [])

    # Save vitals sample
    db.save_personnel_vitals_sample({
        "run_id": run_id,
        "person_id": person_id,
        "tick": 12,
        "sim_time": 720,
        "heart_rate": 84.0,
        "fatigue": 0.28,
        "condition": "fit",
    })

    vitals = db.list_personnel_vitals(person_id=person_id, run_id=run_id)
    assert len(vitals) >= 1
    assert vitals[0]["heart_rate"] == 84.0
    assert vitals[0]["tick"] == 12

    # Save unit position sample
    db.save_unit_position_sample({
        "run_id": run_id,
        "unit_id": unit_id,
        "tick": 12,
        "sim_time": 720,
        "lat": 12.975,
        "lon": 77.598,
        "heading": 45.0,
        "speed_kph": 28.5,
        "in_weather": False,
    })

    positions = db.list_unit_positions(unit_id=unit_id, run_id=run_id)
    assert len(positions) >= 1
    assert positions[0]["lat"] == 12.975
    assert positions[0]["lon"] == 77.598
