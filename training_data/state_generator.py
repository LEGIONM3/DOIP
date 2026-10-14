"""Deterministic physics state generator for DOIP simulation data program."""

from __future__ import annotations
import math
import copy
from dataclasses import dataclass, field, asdict
from typing import Any

from backend.app.simulation.physics_engine import (
    PhysicsEngineState,
    KinematicState,
    EnergyState,
    EnvironmentState,
    CommsState,
    LogisticsState,
)
from .scenario_generator import ScenarioSpec


@dataclass
class ExtendedPhysicsState(PhysicsEngineState):
    """Augmented world state capturing route and mission progress for Laya multi-task decisions."""
    route_progress_pct: float = 0.0
    mission_progress_pct: float = 0.0
    mission_deadline_ticks: int = 30
    arrival_estimate_ticks: int = 25

    def to_extended_dict(self) -> dict[str, Any]:
        d = self.to_dict()
        d.update({
            "route_progress_pct": round(self.route_progress_pct, 2),
            "mission_progress_pct": round(self.mission_progress_pct, 2),
            "mission_deadline_ticks": self.mission_deadline_ticks,
            "arrival_estimate_ticks": self.arrival_estimate_ticks,
        })
        return d


class StateGenerator:
    """Initializes and steps physical world states deterministically according to scenario specs."""

    def initialize_state(self, spec: ScenarioSpec) -> ExtendedPhysicsState:
        """Initializes a reproducible starting state from ScenarioSpec."""
        kinematics = KinematicState(
            lat=12.9716,
            lon=77.5946,
            altitude_m=120.0 if spec.unit_type == "uav" else 0.0,
            speed_mps=spec.target_speed * 0.5,
            heading_deg=45.0,
            max_speed_mps=30.0,
            max_turn_rate_dps=15.0,
        )
        energy = EnergyState(
            fuel_level_pct=spec.initial_fuel,
            battery_level_pct=spec.initial_fuel if spec.unit_type == "uav" else 100.0,
            payload_mass_kg=spec.payload_mass_kg,
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
            depot_distance_m=spec.initial_distance_m * 1.4,
            maintenance_required=spec.initial_wear > 85.0,
        )

        state = ExtendedPhysicsState(
            tick=0,
            sim_time_sec=0.0,
            unit_id=spec.unit_id,
            unit_type=spec.unit_type,
            kinematics=kinematics,
            energy=energy,
            environment=environment,
            comms=comms,
            logistics=logistics,
            route_progress_pct=0.0,
            mission_progress_pct=0.0,
            mission_deadline_ticks=spec.mission_deadline_ticks,
            arrival_estimate_ticks=spec.duration_ticks,
        )
        return state

    def step_state(
        self,
        current_state: ExtendedPhysicsState,
        spec: ScenarioSpec,
        dt_sec: float = 1.0,
        target_heading_delta_deg: float = 2.0,
    ) -> ExtendedPhysicsState:
        """Deterministically steps state through physics transitions."""
        next_s = copy.deepcopy(current_state)
        next_s.tick += 1
        next_s.sim_time_sec += dt_sec

        k = next_s.kinematics
        e = next_s.energy
        env = next_s.environment
        c = next_s.comms
        log = next_s.logistics

        # Dynamic environmental resistance factor
        precip_drag = 1.0 + (env.precipitation_mm_hr / 100.0)
        terrain_resist = env.terrain_friction_coeff
        effective_drag = precip_drag * terrain_resist

        # Heading & turn rate update
        k.heading_deg = (k.heading_deg + target_heading_delta_deg) % 360.0

        # Velocity transition
        if e.fuel_level_pct <= 0.0 or log.vehicle_wear_pct >= 98.0:
            k.speed_mps = max(0.0, k.speed_mps - (2.5 * dt_sec))
            k.acceleration_mps2 = -2.5
        else:
            achievable_target = min(spec.target_speed / effective_drag, k.max_speed_mps)
            dv = achievable_target - k.speed_mps
            k.acceleration_mps2 = max(-3.0, min(2.0, dv))
            k.speed_mps = max(0.0, min(k.max_speed_mps, k.speed_mps + (k.acceleration_mps2 * dt_sec)))

        # Position integration
        dist_m = k.speed_mps * dt_sec
        k.lat += (dist_m * math.cos(math.radians(k.heading_deg))) / 111139.0
        k.lon += (dist_m * math.sin(math.radians(k.heading_deg))) / (111139.0 * math.cos(math.radians(k.lat)))

        # Energy consumption
        burn_rate = (e.base_burn_rate_per_sec + (e.speed_burn_factor * k.speed_mps)) * effective_drag
        e.fuel_level_pct = max(0.0, e.fuel_level_pct - (burn_rate * dt_sec))
        if next_s.unit_type == "uav":
            e.battery_level_pct = max(0.0, e.battery_level_pct - (burn_rate * 1.2 * dt_sec))

        # Wear accumulation
        wear_increment = (0.008 + (0.003 * (k.speed_mps / 10.0))) * terrain_resist * dt_sec
        log.vehicle_wear_pct = min(100.0, log.vehicle_wear_pct + wear_increment)
        log.maintenance_required = log.vehicle_wear_pct >= 85.0

        # RF Comms physics
        c.distance_to_relay_m += 15.0 * dt_sec
        path_loss_db = 20.0 * math.log10(max(10.0, c.distance_to_relay_m)) + 20.0 * math.log10(300.0) - 147.55
        c.signal_strength_dbm = max(-130.0, min(-30.0, -35.0 - path_loss_db - (c.jamming_intensity * 60.0)))
        if c.signal_strength_dbm < -100.0 or c.jamming_intensity > 0.8:
            c.packet_loss_pct = min(100.0, 10.0 + (abs(c.signal_strength_dbm + 100.0) * 3.5) + (c.jamming_intensity * 50.0))
        else:
            c.packet_loss_pct = max(0.0, c.jamming_intensity * 25.0)

        # Route & mission progress tracking
        next_s.route_progress_pct = min(100.0, (next_s.tick / max(1, spec.duration_ticks)) * 100.0)
        next_s.mission_progress_pct = next_s.route_progress_pct
        if k.speed_mps > 1.0:
            remaining_dist = max(0.0, (spec.duration_ticks - next_s.tick) * spec.target_speed)
            eta_seconds = remaining_dist / k.speed_mps
            next_s.arrival_estimate_ticks = next_s.tick + int(eta_seconds)
        else:
            next_s.arrival_estimate_ticks = 999  # stalled/stopped

        return next_s
