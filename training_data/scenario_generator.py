"""Deterministic operational scenario specification generator for DOIP Phase 8.5."""

from __future__ import annotations
import random
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ScenarioSpec:
    scenario_id: str
    family: str
    unit_id: str
    unit_type: str
    initial_fuel: float
    initial_wear: float
    initial_ammo: float
    wind_speed: float
    precip_rate: float
    visibility_km: float
    terrain_friction: float
    initial_distance_m: float
    jamming_intensity: float
    target_speed: float
    duration_ticks: int = 25
    mission_deadline_ticks: int = 30
    payload_mass_kg: float = 250.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScenarioGenerator:
    """Generates rich, parameterized operational scenarios with deterministic seeded control."""

    FAMILIES = [
        "BASELINE_PATROL",
        "ADVERSE_WEATHER",
        "ELECTRONIC_WARFARE",
        "LOGISTICS_STRESS",
        "COMBINED_HIGH_THREAT",
        "BORDER_SURVEILLANCE",
        "EDGE_FAILURE_FUEL_EXHAUSTION",
        "EDGE_FAILURE_COMMS_BLACKOUT",
        "EDGE_FAILURE_SEVERE_BREAKDOWN",
        "EDGE_FAILURE_MASSIVE_STORM",
    ]

    UNIT_TYPES = ["patrol", "uav", "convoy"]

    def __init__(self, seed: int = 2026) -> None:
        self.rng = random.Random(seed)

    def generate_scenarios(self, count: int = 1000) -> list[ScenarioSpec]:
        """Generates a diverse set of scenario specifications deterministically."""
        specs: list[ScenarioSpec] = []
        for i in range(count):
            family = self.rng.choice(self.FAMILIES)
            unit_type = self.rng.choice(self.UNIT_TYPES)
            unit_id = f"{unit_type.upper()}-{i+1:04d}"

            # Baseline parameters
            init_fuel = self.rng.uniform(45.0, 95.0)
            init_wear = self.rng.uniform(5.0, 35.0)
            init_ammo = self.rng.uniform(60.0, 100.0)
            wind = self.rng.uniform(2.0, 10.0)
            precip = self.rng.uniform(0.0, 5.0)
            vis = self.rng.uniform(8.0, 15.0)
            friction = self.rng.uniform(1.0, 1.2)
            dist_m = self.rng.uniform(800.0, 3500.0)
            jamming = self.rng.uniform(0.0, 0.15)
            speed = self.rng.uniform(12.0, 24.0)
            duration = self.rng.randint(20, 35)
            deadline = duration + self.rng.randint(5, 15)
            payload = self.rng.uniform(150.0, 450.0)

            # Profile-specific overrides ensuring full coverage
            if family == "ADVERSE_WEATHER":
                wind = self.rng.uniform(18.0, 32.0)
                precip = self.rng.uniform(20.0, 48.0)
                vis = self.rng.uniform(1.0, 3.5)
                friction = self.rng.uniform(1.4, 2.2)
                deadline = duration + self.rng.randint(0, 4)

            elif family == "ELECTRONIC_WARFARE":
                jamming = self.rng.uniform(0.65, 0.95)
                dist_m = self.rng.uniform(5000.0, 12000.0)

            elif family == "LOGISTICS_STRESS":
                init_fuel = self.rng.uniform(6.0, 22.0)
                init_wear = self.rng.uniform(65.0, 88.0)
                init_ammo = self.rng.uniform(5.0, 20.0)
                dist_m = self.rng.uniform(6000.0, 16000.0)

            elif family == "COMBINED_HIGH_THREAT":
                init_fuel = self.rng.uniform(10.0, 25.0)
                wind = self.rng.uniform(20.0, 32.0)
                precip = self.rng.uniform(25.0, 50.0)
                jamming = self.rng.uniform(0.6, 0.92)
                init_wear = self.rng.uniform(60.0, 85.0)
                deadline = duration + self.rng.randint(-2, 3)

            elif family == "BORDER_SURVEILLANCE":
                speed = self.rng.uniform(22.0, 29.0)
                dist_m = self.rng.uniform(2000.0, 5000.0)

            elif family == "EDGE_FAILURE_FUEL_EXHAUSTION":
                init_fuel = self.rng.uniform(0.0, 4.0)
                speed = self.rng.uniform(5.0, 15.0)
                duration = 20
                deadline = 15

            elif family == "EDGE_FAILURE_COMMS_BLACKOUT":
                jamming = self.rng.uniform(0.92, 1.0)
                dist_m = self.rng.uniform(14000.0, 25000.0)

            elif family == "EDGE_FAILURE_SEVERE_BREAKDOWN":
                init_wear = self.rng.uniform(92.0, 100.0)
                friction = self.rng.uniform(2.2, 3.0)

            elif family == "EDGE_FAILURE_MASSIVE_STORM":
                wind = self.rng.uniform(32.0, 48.0)
                precip = self.rng.uniform(55.0, 85.0)
                vis = self.rng.uniform(0.1, 0.8)
                friction = self.rng.uniform(2.0, 2.8)
                deadline = duration - 2

            spec = ScenarioSpec(
                scenario_id=f"SCEN-{i+1:05d}",
                family=family,
                unit_id=unit_id,
                unit_type=unit_type,
                initial_fuel=round(init_fuel, 2),
                initial_wear=round(init_wear, 2),
                initial_ammo=round(init_ammo, 2),
                wind_speed=round(wind, 2),
                precip_rate=round(precip, 2),
                visibility_km=round(vis, 2),
                terrain_friction=round(friction, 2),
                initial_distance_m=round(dist_m, 2),
                jamming_intensity=round(jamming, 2),
                target_speed=round(speed, 2),
                duration_ticks=duration,
                mission_deadline_ticks=deadline,
                payload_mass_kg=round(payload, 1),
            )
            specs.append(spec)
        return specs
