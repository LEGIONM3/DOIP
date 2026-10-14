"""Deterministic scenario parameterization generator for operational training data synthesis."""

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
    duration_ticks: int = 20

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScenarioGenerator:
    """Generates parameterized operational scenarios across diverse threat and logistical profiles."""

    FAMILIES = [
        "BASELINE_PATROL",
        "ADVERSE_WEATHER",
        "ELECTRONIC_WARFARE",
        "LOGISTICS_STRESS",
        "COMBINED_HIGH_THREAT",
        "BORDER_SURVEILLANCE",
    ]

    UNIT_TYPES = ["patrol", "uav", "convoy"]

    def __init__(self, seed: int = 42) -> None:
        self.rng = random.Random(seed)

    def generate_scenarios(self, count: int = 100) -> list[ScenarioSpec]:
        """Generates a diverse list of scenario specifications deterministically."""
        specs: list[ScenarioSpec] = []
        for i in range(count):
            family = self.rng.choice(self.FAMILIES)
            unit_type = self.rng.choice(self.UNIT_TYPES)
            unit_id = f"{unit_type.upper()}-{i+1:03d}"

            # Base parameters
            init_fuel = self.rng.uniform(40.0, 100.0)
            init_wear = self.rng.uniform(0.0, 30.0)
            init_ammo = self.rng.uniform(50.0, 100.0)
            wind = self.rng.uniform(1.0, 10.0)
            precip = 0.0
            vis = self.rng.uniform(8.0, 15.0)
            friction = 1.0
            dist_m = self.rng.uniform(500.0, 3000.0)
            jamming = 0.0
            speed = self.rng.uniform(10.0, 25.0)

            # Apply family profiles
            if family == "ADVERSE_WEATHER":
                wind = self.rng.uniform(15.0, 32.0)
                precip = self.rng.uniform(15.0, 50.0)
                vis = self.rng.uniform(0.5, 4.0)
                friction = self.rng.uniform(1.3, 2.0)
            elif family == "ELECTRONIC_WARFARE":
                jamming = self.rng.uniform(0.4, 0.95)
                dist_m = self.rng.uniform(4000.0, 9000.0)
            elif family == "LOGISTICS_STRESS":
                init_fuel = self.rng.uniform(5.0, 25.0)
                init_wear = self.rng.uniform(55.0, 92.0)
                init_ammo = self.rng.uniform(5.0, 20.0)
                dist_m = self.rng.uniform(6000.0, 15000.0)
            elif family == "COMBINED_HIGH_THREAT":
                init_fuel = self.rng.uniform(8.0, 30.0)
                wind = self.rng.uniform(18.0, 30.0)
                precip = self.rng.uniform(20.0, 45.0)
                jamming = self.rng.uniform(0.5, 0.9)
                init_wear = self.rng.uniform(50.0, 85.0)
            elif family == "BORDER_SURVEILLANCE":
                speed = self.rng.uniform(20.0, 30.0)
                dist_m = self.rng.uniform(1500.0, 4500.0)

            spec = ScenarioSpec(
                scenario_id=f"SCEN-{i+1:04d}",
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
                duration_ticks=self.rng.randint(15, 30),
            )
            specs.append(spec)
        return specs
