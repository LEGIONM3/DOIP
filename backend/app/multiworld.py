"""Multi-Theater Digital Twin & World Manager for DOIP (Phase 4B).

Manages distributed operational theaters and isolated simulation worlds:
- TheaterManager: Oversees regional battle spaces (THEATER-NORTH, THEATER-EAST, THEATER-LITTORAL).
- WorldManager: Runs independent simultaneous simulation worlds with distinct weather, units,
  logistics stocks, and active incident streams.
- Cross-Theater Analysis: Aggregates global multi-world readiness, threat exposure, and supply draw.
"""

from __future__ import annotations

import copy
import datetime
import logging
import uuid
from typing import Any

try:
    from . import db
    from .engine import SimEngine, BASE_LAT, BASE_LON
except ImportError:
    from app import db
    from app.engine import SimEngine, BASE_LAT, BASE_LON

log = logging.getLogger(__name__)


class TheaterManager:
    """Manages operational theater definitions and active battle spaces."""

    def __init__(self) -> None:
        self.theaters: dict[str, dict[str, Any]] = {}
        self._seed_default_theaters()

    def _seed_default_theaters(self) -> None:
        """Seed primary defense theaters."""
        defaults = [
            {
                "id": "THEATER-NORTH",
                "name": "Northern Mountain Front",
                "code": "NORTH",
                "bounds": [
                    [13.1000, 77.4000],
                    [13.1000, 77.8000],
                    [12.8000, 77.8000],
                    [12.8000, 77.4000],
                ],
                "active_world_id": "WLD-NORTH-01",
                "status": "active",
            },
            {
                "id": "THEATER-EAST",
                "name": "Eastern Littoral & Coastal Corridor",
                "code": "EAST",
                "bounds": [
                    [13.2000, 77.7000],
                    [13.2000, 78.1000],
                    [12.9000, 78.1000],
                    [12.9000, 77.7000],
                ],
                "active_world_id": "WLD-EAST-01",
                "status": "active",
            },
            {
                "id": "THEATER-LITTORAL",
                "name": "Southern Maritime Air Defense Sector",
                "code": "LITTORAL",
                "bounds": [
                    [12.7000, 77.3000],
                    [12.7000, 77.7000],
                    [12.4000, 77.7000],
                    [12.4000, 77.3000],
                ],
                "active_world_id": "WLD-LITTORAL-01",
                "status": "active",
            },
        ]
        for t in defaults:
            self.theaters[t["id"]] = t
            db.save_theater(t)

    def register_theater(self, theater_data: dict[str, Any]) -> dict[str, Any]:
        t_id = theater_data.get("id") or f"THEATER-{uuid.uuid4().hex[:6].upper()}"
        theater_data["id"] = t_id
        self.theaters[t_id] = theater_data
        return db.save_theater(theater_data)

    def list_theaters(self) -> list[dict[str, Any]]:
        return list(self.theaters.values())

    def get_theater(self, theater_id: str) -> dict[str, Any] | None:
        return self.theaters.get(theater_id) or db.get_theater(theater_id)


class WorldManager:
    """Manages concurrent independent simulation worlds."""

    def __init__(self) -> None:
        self.worlds: dict[str, dict[str, Any]] = {}
        self._seed_default_worlds()

    def _seed_default_worlds(self) -> None:
        """Initialize simultaneous worlds for active theaters."""
        seed_configs = [
            ("WLD-NORTH-01", "THEATER-NORTH", "Northern High-Altitude World", 42),
            ("WLD-EAST-01", "THEATER-EAST", "Eastern Maritime Littoral World", 101),
            ("WLD-LITTORAL-01", "THEATER-LITTORAL", "Southern Coastal Air Defense World", 777),
        ]
        for w_id, t_id, name, seed in seed_configs:
            eng = SimEngine()
            init_evs = eng.start(seed=seed, scenario_id="SC-1")
            payload = init_evs[0].payload if init_evs else {}
            world_record = {
                "id": w_id,
                "theater_id": t_id,
                "name": name,
                "tick": 45,
                "status": "running",
                "state_snapshot": {
                    "seed": seed,
                    "units": {u["id"]: u for u in payload.get("units", [])},
                    "depots": {d["id"]: d for d in payload.get("depots", [])},
                    "weather": payload.get("weather", {}),
                    "incidents": {
                        f"INC-{t_id[:5]}-01": {
                            "id": f"INC-{t_id[:5]}-01",
                            "severity": "medium",
                            "type": "radar_anomaly",
                            "tick": 12,
                        }
                    },
                },
            }
            self.worlds[w_id] = world_record
            db.save_world(world_record)

    def get_world(self, world_id: str) -> dict[str, Any] | None:
        return self.worlds.get(world_id) or db.get_world(world_id)

    def list_worlds(self, theater_id: str | None = None) -> list[dict[str, Any]]:
        if theater_id:
            return [w for w in self.worlds.values() if w["theater_id"] == theater_id]
        return list(self.worlds.values())

    def cross_theater_analysis(self) -> dict[str, Any]:
        """Aggregate cross-theater intelligence, supply draw, and threat density."""
        total_units = 0
        total_fuel_burn = 0.0
        total_depot_fuel = 0.0
        total_incidents = 0
        theaters_breakdown: list[dict[str, Any]] = []

        for w in self.worlds.values():
            snap = w.get("state_snapshot", {})
            u_dict = snap.get("units", {})
            d_dict = snap.get("depots", {})
            inc_dict = snap.get("incidents", {})

            u_count = len(u_dict)
            total_units += u_count

            # Calculate theater fuel reserves
            depot_fuel = sum(
                float(d.get("stock", {}).get("fuel", 0.0)) for d in d_dict.values()
            )
            total_depot_fuel += depot_fuel

            # Calculate units remaining fuel average
            avg_unit_fuel = (
                sum(float(u.get("fuel", 100.0)) for u in u_dict.values()) / max(1, u_count)
                if u_count
                else 100.0
            )
            total_fuel_burn += (100.0 - avg_unit_fuel) * u_count

            inc_count = len(inc_dict)
            total_incidents += inc_count

            # Determine theater readiness
            readiness = max(
                40.0,
                min(100.0, avg_unit_fuel * 0.6 + (100.0 - inc_count * 12.0) * 0.4),
            )

            theaters_breakdown.append({
                "theater_id": w["theater_id"],
                "world_id": w["id"],
                "units_count": u_count,
                "avg_unit_fuel_pct": round(avg_unit_fuel, 1),
                "depot_fuel_liters": round(depot_fuel, 1),
                "active_incidents": inc_count,
                "readiness_score": round(readiness, 1),
            })

        global_readiness = (
            sum(t["readiness_score"] for t in theaters_breakdown) / max(1, len(theaters_breakdown))
            if theaters_breakdown
            else 85.0
        )

        return {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "theaters_active": len(theaters_breakdown),
            "total_units_deployed": total_units,
            "total_depot_fuel_liters": round(total_depot_fuel, 1),
            "total_active_incidents": total_incidents,
            "global_readiness_score": round(global_readiness, 1),
            "threat_density_index": round(min(100.0, total_incidents * 18.5), 1),
            "theaters": theaters_breakdown,
        }


# Singletons
theater_manager = TheaterManager()
world_manager = WorldManager()
