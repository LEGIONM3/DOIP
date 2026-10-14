"""Feature extractor for converting simulation state to numeric vectors and Laya state texts."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import numpy as np
from .physics_engine import PhysicsEngineState


@dataclass
class SimulationFeatures:
    numeric_vector: list[float]
    feature_names: list[str]
    raw_dict: dict[str, Any]
    prompt_text: str

    def to_numpy(self) -> np.ndarray:
        return np.array(self.numeric_vector, dtype=np.float32)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_names": self.feature_names,
            "numeric_vector": self.numeric_vector,
            "raw_dict": self.raw_dict,
            "prompt_text": self.prompt_text,
        }


class FeatureExtractor:
    """Extracts normalized continuous feature vectors and contextual text descriptions."""

    FEATURE_NAMES: list[str] = [
        "lat_norm",
        "lon_norm",
        "speed_norm",
        "heading_norm",
        "fuel_norm",
        "battery_norm",
        "wind_speed_norm",
        "precip_norm",
        "visibility_norm",
        "terrain_friction_norm",
        "signal_strength_norm",
        "jamming_norm",
        "vehicle_wear_norm",
        "depot_dist_norm",
        "ammo_norm",
    ]

    def extract(self, state: PhysicsEngineState) -> SimulationFeatures:
        k = state.kinematics
        e = state.energy
        env = state.environment
        c = state.comms
        log = state.logistics

        # Normalization to [0.0, 1.0] domain
        # Coordinates centered around Bangalore base (12.9716, 77.5946) with 1 degree range
        lat_norm = max(0.0, min(1.0, (k.lat - 12.0) / 2.0))
        lon_norm = max(0.0, min(1.0, (k.lon - 76.5) / 2.0))
        speed_norm = max(0.0, min(1.0, k.speed_mps / max(1.0, k.max_speed_mps)))
        heading_norm = max(0.0, min(1.0, k.heading_deg / 360.0))
        fuel_norm = max(0.0, min(1.0, e.fuel_level_pct / 100.0))
        battery_norm = max(0.0, min(1.0, e.battery_level_pct / 100.0))
        wind_speed_norm = max(0.0, min(1.0, env.wind_speed_mps / 40.0))
        precip_norm = max(0.0, min(1.0, env.precipitation_mm_hr / 60.0))
        visibility_norm = max(0.0, min(1.0, env.visibility_km / 15.0))
        terrain_friction_norm = max(0.0, min(1.0, (env.terrain_friction_coeff - 0.8) / 1.5))
        signal_norm = max(0.0, min(1.0, (c.signal_strength_dbm + 130.0) / 110.0))
        jamming_norm = max(0.0, min(1.0, c.jamming_intensity))
        wear_norm = max(0.0, min(1.0, log.vehicle_wear_pct / 100.0))
        depot_dist_norm = max(0.0, min(1.0, log.depot_distance_m / 20000.0))
        ammo_norm = max(0.0, min(1.0, log.ammunition_pct / 100.0))

        vec = [
            round(lat_norm, 4),
            round(lon_norm, 4),
            round(speed_norm, 4),
            round(heading_norm, 4),
            round(fuel_norm, 4),
            round(battery_norm, 4),
            round(wind_speed_norm, 4),
            round(precip_norm, 4),
            round(visibility_norm, 4),
            round(terrain_friction_norm, 4),
            round(signal_norm, 4),
            round(jamming_norm, 4),
            round(wear_norm, 4),
            round(depot_dist_norm, 4),
            round(ammo_norm, 4),
        ]

        raw = {
            "lat": k.lat,
            "lon": k.lon,
            "speed_mps": k.speed_mps,
            "heading_deg": k.heading_deg,
            "fuel_level_pct": e.fuel_level_pct,
            "battery_level_pct": e.battery_level_pct,
            "wind_speed_mps": env.wind_speed_mps,
            "precipitation_mm_hr": env.precipitation_mm_hr,
            "visibility_km": env.visibility_km,
            "terrain_friction_coeff": env.terrain_friction_coeff,
            "signal_strength_dbm": c.signal_strength_dbm,
            "jamming_intensity": c.jamming_intensity,
            "packet_loss_pct": c.packet_loss_pct,
            "vehicle_wear_pct": log.vehicle_wear_pct,
            "depot_distance_m": log.depot_distance_m,
            "ammunition_pct": log.ammunition_pct,
        }

        prompt = (
            f"Operational telemetry for unit {state.unit_id} ({state.unit_type.upper()}) at tick {state.tick}:\n"
            f"Kinematics: Position ({k.lat:.4f}, {k.lon:.4f}), Heading {k.heading_deg:.1f} deg, Speed {k.speed_mps:.1f} m/s (max {k.max_speed_mps:.1f} m/s).\n"
            f"Energy: Fuel {e.fuel_level_pct:.1f}%, Battery {e.battery_level_pct:.1f}%, Payload {e.payload_mass_kg:.0f} kg.\n"
            f"Environment: Wind {env.wind_speed_mps:.1f} m/s, Visibility {env.visibility_km:.1f} km, Rain {env.precipitation_mm_hr:.1f} mm/h, Friction {env.terrain_friction_coeff:.2f}.\n"
            f"Comms: Signal {c.signal_strength_dbm:.1f} dBm, Jamming {c.jamming_intensity * 100:.0f}%, Packet Loss {c.packet_loss_pct:.1f}%, Latency {c.latency_ms:.0f} ms.\n"
            f"Logistics: Ammo {log.ammunition_pct:.1f}%, Wear {log.vehicle_wear_pct:.1f}%, Distance to Depot {log.depot_distance_m:.0f} m."
        )

        return SimulationFeatures(
            numeric_vector=vec,
            feature_names=self.FEATURE_NAMES,
            raw_dict=raw,
            prompt_text=prompt,
        )
