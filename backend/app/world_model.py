"""Pan-India World Model Service for DOIP.

Manages two logically independent operational worlds:
1. Pan-India Live Context Baseline (worldMode="baseline"):
   - Real-world geography across all Indian sectors.
   - Synchronized with live environmental meteorological context (Open-Meteo observations/forecasts).
   - Synthetic operational entities, depots, personnel, and baseline patrols.
2. Isolated Artificial Impact Simulation Worlds (worldMode="simulation"):
   - Forked simulation branches initialized from a baseline snapshot.
   - Scenario impacts: cyclones, blizzards, comms blackouts, heatwaves, logistics chokepoints.
   - Instant reset and branching capabilities.
"""

from __future__ import annotations

import copy
import datetime
import logging
import uuid
from typing import Any

from .engine import SimEngine
from .environmental_context import environmental_context_service
from .scenarios import SCENARIOS

log = logging.getLogger(__name__)


class SimulationBranch:
    """An isolated simulation branch running independently from the baseline."""

    def __init__(self, branch_id: str, scenario_id: str, seed: int = 20261014, name: str | None = None) -> None:
        self.branch_id = branch_id
        self.scenario_id = scenario_id
        self.seed = seed
        self.name = name or f"Branch: {scenario_id}"
        self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.engine = SimEngine()
        self.init_events = self.engine.start(seed, scenario_id)
        self.initial_snapshot = self.engine.snapshot()

    def step(self) -> list[Any]:
        return self.engine.step()

    def reset(self) -> list[Any]:
        """Instant reset back to the branch's initial baseline state."""
        self.engine = SimEngine()
        self.init_events = self.engine.start(self.seed, self.scenario_id)
        return self.init_events

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "name": self.name,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "tick": self.engine.tick,
            "created_at": self.created_at,
            "units_count": len(self.engine._units),
            "depots_count": len(self.engine._depots),
            "weather_count": len(self.engine._weather),
        }


class WorldModelService:
    """Coordinates the Pan-India Live World and Artificial Impact Simulation Branches."""

    def __init__(self) -> None:
        self.baseline_scenario_id = "IN-BASE-LIVE"
        self.baseline_seed = 20261014
        self.baseline_revision_id = f"REV-BASE-{uuid.uuid4().hex[:8].upper()}"
        self.baseline_engine = SimEngine()
        self.baseline_init_events = self.baseline_engine.start(self.baseline_seed, self.baseline_scenario_id)
        self.baseline_snapshot = self.baseline_engine.snapshot()
        self.branches: dict[str, SimulationBranch] = {}
        self._seed_default_branches()

    def _seed_default_branches(self) -> None:
        """Seed representative impact branches for instant switching."""
        defaults = [
            ("BRANCH-CYCLONE", "IN-SC-CYCLONE", 8801, "Bay of Bengal Cyclone Impact"),
            ("BRANCH-NORTH-COMMS", "IN-SC-NORTH-COMMS", 8802, "Ladakh High-Altitude Comms Blackout"),
            ("BRANCH-WEST-HEAT", "IN-SC-WEST-HEAT", 8803, "Thar Desert Thermal Strain"),
            ("BRANCH-LOGISTICS", "IN-SC-LOGISTICS", 8804, "Central Corridor Chokepoint"),
        ]
        for b_id, sc_id, seed, name in defaults:
            self.branches[b_id] = SimulationBranch(b_id, sc_id, seed, name)

    async def get_baseline_world(self) -> dict[str, Any]:
        """Return the current Pan-India Live Context Baseline state with real meteorological data."""
        env_ctx = await environmental_context_service.get_environmental_context()
        snap = self.baseline_engine.snapshot()
        return {
            "worldMode": "baseline",
            "revisionId": self.baseline_revision_id,
            "subcontinent": "India",
            "center": [22.5937, 78.9629],
            "tick": self.baseline_engine.tick,
            "environmentalContext": env_ctx,
            "state": snap,
            "units": [u.to_dict() for u in self.baseline_engine._units],
            "depots": [d.to_dict() for d in self.baseline_engine._depots],
            "personnel": [p.to_dict() for p in self.baseline_engine._personnel],
            "zones": [
                {"id": "Z-IN-NORTH", "name": "LADAKH HIGH ALTITUDE PATROL GRID", "kind": "patrol", "sector": "NORTH"},
                {"id": "Z-IN-WEST", "name": "THAR DESERT SURVEILLANCE CORRIDOR", "kind": "restricted", "sector": "WEST"},
                {"id": "Z-IN-EAST", "name": "BAY OF BENGAL MARITIME SECTOR", "kind": "threat", "sector": "EAST"},
                {"id": "Z-IN-CENTRAL", "name": "CENTRAL FREIGHT LOGISTICS CORRIDOR", "kind": "patrol", "sector": "CENTRAL"},
                {"id": "Z-IN-LITTORAL", "name": "ANDAMAN SEA SURVEILLANCE ZONE", "kind": "restricted", "sector": "LITTORAL"},
            ],
        }

    def fork_simulation(
        self, scenario_id: str, seed: int = 20261014, branch_id: str | None = None, name: str | None = None
    ) -> SimulationBranch:
        """Fork an isolated artificial impact simulation world branch from baseline."""
        b_id = branch_id or f"BRANCH-{uuid.uuid4().hex[:8].upper()}"
        branch = SimulationBranch(b_id, scenario_id, seed, name)
        self.branches[b_id] = branch
        return branch

    def reset_simulation(self, branch_id: str) -> dict[str, Any]:
        """Instant reset of a simulation branch back to clean baseline state."""
        branch = self.branches.get(branch_id)
        if not branch:
            raise KeyError(f"Simulation branch {branch_id} not found")
        init_evs = branch.reset()
        return {
            "branch_id": branch.branch_id,
            "status": "reset_complete",
            "tick": branch.engine.tick,
            "initial_events": [ev.to_dict() for ev in init_evs],
        }

    def get_branch(self, branch_id: str) -> SimulationBranch | None:
        return self.branches.get(branch_id)

    def list_branches(self) -> list[dict[str, Any]]:
        return [b.to_dict() for b in self.branches.values()]

    def step_branch(self, branch_id: str) -> list[dict[str, Any]]:
        branch = self.branches.get(branch_id)
        if not branch:
            raise KeyError(f"Simulation branch {branch_id} not found")
        events = branch.step()
        return [ev.to_dict() for ev in events]


# Singleton
world_model_service = WorldModelService()
