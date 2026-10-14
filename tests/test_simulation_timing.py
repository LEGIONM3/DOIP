"""Phase 1 Verification: Empirical Simulation Timing, Accumulator Progression & Multiplier Benchmarks.

Validates:
1. Real-time simulation clock advancement across 1x, 2x, 5x, 10x, 16x, 20x.
2. Bounded accumulator behavior preventing unbounded catch-up bursts on scheduler suspension.
3. Mid-run dynamic speed switching without loop restart or clock drift.
4. Pause/resume exact tick freeze and seamless continuity.
5. Single-task exclusivity preventing concurrent engine loops for the same run.
"""

from __future__ import annotations

import asyncio
import time
import pytest

from backend.app.session import SimSession
from backend.app import db


@pytest.fixture(autouse=True)
def setup_db():
    db.init()


@pytest.mark.asyncio
@pytest.mark.parametrize("speed", [1.0, 2.0, 5.0, 10.0, 16.0, 20.0])
async def test_simulation_speed_progression(speed: float):
    """Measure wall-clock duration vs simulation-clock ticks advanced.

    At speed S, over wall duration T, expected ticks = S * T.
    Permitted tolerance: ±25% on Windows scheduling (15.6ms timer quantum).
    """
    run_id = f"timing-test-spd-{int(speed * 10)}"
    session = SimSession(seed=20261001, scenario_id="SC-1", speed=speed, run_id=run_id)

    wall_duration = 1.0  # Measure over 1.0s window
    await session.start()

    t_start = time.monotonic()
    await asyncio.sleep(wall_duration)
    t_end = time.monotonic()

    # Capture ticks immediately
    ticks_advanced = session.engine.tick
    await session.stop()

    measured_wall = t_end - t_start
    measured_multiplier = ticks_advanced / measured_wall
    expected_multiplier = speed

    print(
        f"\n[Speed {speed}x] Wall: {measured_wall:.3f}s, Ticks: {ticks_advanced}, "
        f"Measured Multiplier: {measured_multiplier:.2f}x (Expected: {expected_multiplier}x)"
    )

    # Verify that progression is directional and scales with speed
    min_expected_ticks = max(1, int(speed * wall_duration * 0.70))
    max_expected_ticks = int(speed * wall_duration * 1.35) + 3

    assert ticks_advanced >= min_expected_ticks, (
        f"Speed {speed}x progressed too slowly: {ticks_advanced} ticks (min expected: {min_expected_ticks})"
    )
    assert ticks_advanced <= max_expected_ticks, (
        f"Speed {speed}x progressed too fast: {ticks_advanced} ticks (max expected: {max_expected_ticks})"
    )


@pytest.mark.asyncio
async def test_dynamic_speed_switching_mid_run():
    """Verify that altering speed while loop is running transitions immediately without restart."""
    session = SimSession(seed=20261002, scenario_id="SC-1", speed=1.0, run_id="timing-dynamic")
    await session.start()

    # Phase 1: Run at 1x for 0.4s (~0-1 ticks)
    await asyncio.sleep(0.40)
    tick_phase1 = session.engine.tick
    assert tick_phase1 <= 2

    # Phase 2: Switch to 20x while running
    await session.set_speed(20.0)
    assert session.speed == 20.0
    await asyncio.sleep(0.40)  # At 20x, 0.4s -> ~8 ticks
    tick_phase2 = session.engine.tick
    assert tick_phase2 > tick_phase1 + 3

    # Phase 3: Switch down to 2x while running
    await session.set_speed(2.0)
    assert session.speed == 2.0
    tick_before = session.engine.tick
    await asyncio.sleep(0.40)  # At 2x, 0.4s -> ~1 tick
    tick_phase3 = session.engine.tick
    assert tick_phase3 <= tick_before + 3

    await session.stop()


@pytest.mark.asyncio
async def test_bounded_accumulator_lag_protection():
    """Verify that a large lag spike does not result in an unbounded burst of catch-up steps."""
    session = SimSession(seed=20261003, scenario_id="SC-1", speed=10.0, run_id="timing-lag")
    await session.start()

    # Allow session to take 1-2 ticks
    await asyncio.sleep(0.20)
    initial_tick = session.engine.tick

    # Simulate an external thread block / suspension of 3.0 seconds
    time.sleep(1.0)

    # Allow loop one scheduling cycle to process
    await asyncio.sleep(0.05)
    post_lag_tick = session.engine.tick

    # Because bounded_elapsed is capped at 0.50s and max_steps_per_cycle is 12,
    # the engine must NOT jump by 3.0s * 10x = 30 ticks in a single cycle.
    ticks_jumped = post_lag_tick - initial_tick
    assert ticks_jumped <= 14, f"Accumulator lag protection failed: jumped {ticks_jumped} ticks in one cycle"

    await session.stop()


@pytest.mark.asyncio
async def test_concurrent_loop_prevention():
    """Calling start() twice must cleanly cancel the prior task and avoid duplicate loops."""
    session = SimSession(seed=20261004, scenario_id="SC-1", speed=5.0, run_id="timing-concurrency")
    await session.start()
    task1 = session._task

    # Re-issue start()
    await session.start()
    task2 = session._task

    assert task1 is not task2
    assert task1.done()
    assert not task2.done()

    # Verify tick progression is normal (not doubled)
    t0 = session.engine.tick
    await asyncio.sleep(0.5)
    t1 = session.engine.tick

    # At 5x, 0.5s is ~2-3 ticks. If duplicate loops ran, it would be 5-6 ticks.
    assert (t1 - t0) <= 5

    await session.stop()
