"""Deterministic synthetic physics engine for operational simulation.

Models:
- Kinematics (position, velocity, acceleration, heading, turn rate)
- Energy (fuel, battery, payload mass, drag)
- Environment (wind vector, temperature, precipitation, visibility, terrain friction)
- Communications (RF path loss, distance to base/relays, terrain occlusion, jamming)
- Logistics (cargo, ammunition, medical kits, wear/tear, maintenance requirement)
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class KinematicState:
    lat: float
    lon: float
    altitude_m: float = 0.0
    speed_mps: float = 0.0
    heading_deg: float = 0.0
    acceleration_mps2: float = 0.0
    turn_rate_dps: float = 0.0
    max_speed_mps: float = 30.0  # ~108 km/h
    max_turn_rate_dps: float = 15.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnergyState:
    fuel_level_pct: float = 100.0      # 0 to 100%
    battery_level_pct: float = 100.0   # 0 to 100%
    payload_mass_kg: float = 250.0
    drag_coeff: float = 0.35
    base_burn_rate_per_sec: float = 0.01  # % per sec at idle
    speed_burn_factor: float = 0.001       # added % per mps

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EnvironmentState:
    wind_speed_mps: float = 5.0
    wind_heading_deg: float = 180.0
    temperature_c: float = 28.0
    precipitation_mm_hr: float = 0.0
    visibility_km: float = 10.0
    terrain_friction_coeff: float = 1.0  # 1.0 = asphalt/paved, 1.8 = mud/sand

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommsState:
    signal_strength_dbm: float = -65.0  # -120 (lost) to -30 (perfect)
    distance_to_relay_m: float = 1200.0
    terrain_occlusion_factor: float = 0.0  # 0.0 (line of sight) to 1.0 (blocked)
    jamming_intensity: float = 0.0        # 0.0 (clean) to 1.0 (max jamming)
    active_relays: int = 2
    packet_loss_pct: float = 0.0
    latency_ms: float = 25.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LogisticsState:
    ammunition_pct: float = 100.0
    medical_kits: int = 5
    depot_distance_m: float = 3500.0
    vehicle_wear_pct: float = 5.0  # 0 to 100%
    maintenance_required: bool = False
    supply_capacity_kg: float = 1000.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PhysicsEngineState:
    tick: int = 0
    sim_time_sec: float = 0.0
    unit_id: str = "PATROL-1"
    unit_type: str = "patrol"  # patrol, uav, convoy
    kinematics: KinematicState = field(default_factory=lambda: KinematicState(lat=12.9716, lon=77.5946))
    energy: EnergyState = field(default_factory=EnergyState)
    environment: EnvironmentState = field(default_factory=EnvironmentState)
    comms: CommsState = field(default_factory=CommsState)
    logistics: LogisticsState = field(default_factory=LogisticsState)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "sim_time_sec": self.sim_time_sec,
            "unit_id": self.unit_id,
            "unit_type": self.unit_type,
            "kinematics": self.kinematics.to_dict(),
            "energy": self.energy.to_dict(),
            "environment": self.environment.to_dict(),
            "comms": self.comms.to_dict(),
            "logistics": self.logistics.to_dict(),
        }


class PhysicsEngine:
    """Deterministic, physically grounded operational simulator step engine."""

    EARTH_RADIUS_M: float = 6371000.0

    def __init__(self, initial_state: Optional[PhysicsEngineState] = None) -> None:
        self.state = initial_state if initial_state is not None else PhysicsEngineState()

    def set_state(self, state: PhysicsEngineState) -> None:
        self.state = state

    def get_state(self) -> PhysicsEngineState:
        return self.state

    def step(
        self,
        dt_sec: float = 1.0,
        target_speed_mps: Optional[float] = None,
        target_heading_deg: Optional[float] = None,
        environmental_perturbation: Optional[dict[str, float]] = None,
    ) -> PhysicsEngineState:
        """Step the synthetic physics simulation deterministically forward by dt_sec."""
        k = self.state.kinematics
        e = self.state.energy
        env = self.state.environment
        c = self.state.comms
        log = self.state.logistics

        # 1. Update Environment if perturbation supplied
        if environmental_perturbation:
            if "wind_speed_mps" in environmental_perturbation:
                env.wind_speed_mps = max(0.0, float(environmental_perturbation["wind_speed_mps"]))
            if "precipitation_mm_hr" in environmental_perturbation:
                env.precipitation_mm_hr = max(0.0, float(environmental_perturbation["precipitation_mm_hr"]))
            if "jamming_intensity" in environmental_perturbation:
                c.jamming_intensity = min(1.0, max(0.0, float(environmental_perturbation["jamming_intensity"])))
            if "visibility_km" in environmental_perturbation:
                env.visibility_km = max(0.1, float(environmental_perturbation["visibility_km"]))

        # 2. Kinematics updates
        if target_speed_mps is not None:
            # Acceleration limited by terrain friction
            max_accel = 2.5 / env.terrain_friction_coeff
            speed_err = target_speed_mps - k.speed_mps
            k.acceleration_mps2 = max(-4.0, min(max_accel, speed_err / max(dt_sec, 0.001)))
            k.speed_mps = max(0.0, min(k.max_speed_mps, k.speed_mps + k.acceleration_mps2 * dt_sec))

        if target_heading_deg is not None:
            # Heading turn rate constrained
            diff = (target_heading_deg - k.heading_deg + 180.0) % 360.0 - 180.0
            max_turn = k.max_turn_rate_dps * dt_sec
            turn = max(-max_turn, min(max_turn, diff))
            k.turn_rate_dps = turn / max(dt_sec, 0.001)
            k.heading_deg = (k.heading_deg + turn) % 360.0

        # Displace position using heading and speed with wind drift effect
        speed_actual = k.speed_mps
        # Effective drag from wind
        wind_angle_rad = math.radians((env.wind_heading_deg - k.heading_deg + 360.0) % 360.0)
        headwind_comp = env.wind_speed_mps * math.cos(wind_angle_rad)
        effective_speed = max(0.0, speed_actual - (headwind_comp * 0.05 * e.drag_coeff))

        dist_m = effective_speed * dt_sec
        heading_rad = math.radians(k.heading_deg)
        d_lat = (dist_m * math.cos(heading_rad)) / self.EARTH_RADIUS_M
        d_lon = (dist_m * math.sin(heading_rad)) / (self.EARTH_RADIUS_M * math.cos(math.radians(k.lat)))

        k.lat += math.degrees(d_lat)
        k.lon += math.degrees(d_lon)

        # 3. Energy Consumption
        # Burn rate is dependent on mass, terrain friction, drag, and speed
        speed_factor = (effective_speed / max(1.0, k.max_speed_mps)) ** 1.5
        payload_factor = 1.0 + (e.payload_mass_kg / 1000.0) * 0.3
        terrain_factor = env.terrain_friction_coeff
        burn_pct = (
            e.base_burn_rate_per_sec
            + (e.speed_burn_factor * effective_speed * terrain_factor * payload_factor)
        ) * dt_sec

        e.fuel_level_pct = max(0.0, e.fuel_level_pct - burn_pct)
        if self.state.unit_type == "uav":
            # UAV also drains battery
            e.battery_level_pct = max(0.0, e.battery_level_pct - (burn_pct * 1.5))

        # 4. RF Communications propagation model
        # Friis / log-distance path loss + occlusion + jamming
        c.distance_to_relay_m = max(50.0, c.distance_to_relay_m + (dist_m * 0.2))  # gradual movement
        path_loss_db = 20.0 * math.log10(max(10.0, c.distance_to_relay_m)) + 32.4
        occlusion_penalty = c.terrain_occlusion_factor * 25.0
        jamming_penalty = c.jamming_intensity * 40.0
        weather_attenuation = (env.precipitation_mm_hr / 50.0) * 10.0

        c.signal_strength_dbm = -30.0 - (path_loss_db * 0.5) - occlusion_penalty - jamming_penalty - weather_attenuation
        c.signal_strength_dbm = max(-130.0, min(-20.0, c.signal_strength_dbm))

        if c.signal_strength_dbm > -70.0:
            c.packet_loss_pct = 0.0
            c.latency_ms = 15.0
        elif c.signal_strength_dbm > -90.0:
            c.packet_loss_pct = 5.0 + ((-70.0 - c.signal_strength_dbm) * 1.2)
            c.latency_ms = 30.0 + ((-70.0 - c.signal_strength_dbm) * 3.0)
        elif c.signal_strength_dbm > -110.0:
            c.packet_loss_pct = 35.0 + ((-90.0 - c.signal_strength_dbm) * 2.5)
            c.latency_ms = 120.0 + ((-90.0 - c.signal_strength_dbm) * 10.0)
        else:
            c.packet_loss_pct = 100.0
            c.latency_ms = 2500.0

        # 5. Logistics and mechanical wear
        wear_increment = (dist_m / 1000.0) * 0.05 * env.terrain_friction_coeff
        log.vehicle_wear_pct = min(100.0, log.vehicle_wear_pct + wear_increment)
        if log.vehicle_wear_pct > 75.0 or e.fuel_level_pct < 10.0:
            log.maintenance_required = True

        self.state.tick += 1
        self.state.sim_time_sec += dt_sec

        return self.state
