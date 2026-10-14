"""Generates simulation state trajectories from scenario specifications using PhysicsEngine."""

from __future__ import annotations
from typing import Generator
from backend.app.simulation.physics_engine import (
    PhysicsEngine,
    PhysicsEngineState,
    KinematicState,
    EnergyState,
    EnvironmentState,
    CommsState,
    LogisticsState,
)
from .scenario_generator import ScenarioSpec


import copy


class StateTrajectoryGenerator:
    """Executes scenario specifications through deterministic physics simulator to record states."""

    def run_trajectory(self, spec: ScenarioSpec) -> list[PhysicsEngineState]:
        """Runs a complete trajectory for the given scenario spec, returning state snapshots."""
        # Setup initial state
        kinematics = KinematicState(
            lat=12.9716,
            lon=77.5946,
            speed_mps=spec.target_speed * 0.5,
            heading_deg=45.0,
        )
        energy = EnergyState(
            fuel_level_pct=spec.initial_fuel,
            battery_level_pct=spec.initial_fuel if spec.unit_type == "uav" else 100.0,
        )
        environment = EnvironmentState(
            wind_speed_mps=spec.wind_speed,
            wind_heading_deg=180.0,
            precipitation_mm_hr=spec.precip_rate,
            visibility_km=spec.visibility_km,
            terrain_friction_coeff=spec.terrain_friction,
        )
        comms = CommsState(
            distance_to_relay_m=spec.initial_distance_m,
            jamming_intensity=spec.jamming_intensity,
        )
        logistics = LogisticsState(
            ammunition_pct=spec.initial_ammo,
            vehicle_wear_pct=spec.initial_wear,
            depot_distance_m=spec.initial_distance_m * 1.5,
        )

        init_state = PhysicsEngineState(
            tick=0,
            sim_time_sec=0.0,
            unit_id=spec.unit_id,
            unit_type=spec.unit_type,
            kinematics=kinematics,
            energy=energy,
            environment=environment,
            comms=comms,
            logistics=logistics,
        )

        physics = PhysicsEngine(init_state)
        trajectory: list[PhysicsEngineState] = [copy.deepcopy(init_state)]

        for step in range(1, spec.duration_ticks + 1):
            next_state = physics.step(
                dt_sec=1.0,
                target_speed_mps=spec.target_speed,
                target_heading_deg=(45.0 + step * 3.0) % 360.0,
            )
            # Create snapshot copy
            trajectory.append(copy.deepcopy(next_state))

        return trajectory
