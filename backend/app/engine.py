"""Deterministic simulation engine — faithful Python port of src/sim/engine.ts.

The mulberry32 PRNG (prng.py) produces bit-identical float sequences to the
TypeScript original, so recorded event logs are fully interchangeable between
server and browser replay.

Entry point for callers: `SimEngine`. Use `start()` to initialise a run and
call `step()` in a loop (or let `SimSession` drive the async loop via WS).
Supports legacy scenarios (SC-1..SC-4) and Pan-India live baseline / artificial impact scenarios.
"""

from __future__ import annotations

import math
from typing import Any

from .prng import Rand, between, mulberry32, pick
from .sim_types import Depot, Person, SimEvent, Unit, WeatherCell, Zone

BASE_LAT = 12.9716
BASE_LON = 77.5946

# Strategic Indian regional anchors (all 11 weather-monitored sectors)
INDIAN_SECTORS = {
    "NORTH": {
        "name": "Northern Sector (Ladakh)",
        "lat": 34.1526,
        "lon": 77.5771,
        "radius": 0.35,
        "weatherStationId": "STN-LEH",
        "depotName": "NORTHERN FORWARD TACTICAL DEPOT (LEH)",
        "facilityType": "forward_operating_base",
    },
    "KASHMIR": {
        "name": "Northern Sector (Kashmir Valley)",
        "lat": 34.0837,
        "lon": 74.7973,
        "radius": 0.30,
        "weatherStationId": "STN-SRINAGAR",
        "depotName": "KASHMIR VALLEY LOGISTICS & AIR SUPPORT HUB (SRINAGAR)",
        "facilityType": "airbase",
    },
    "NCR": {
        "name": "Northern Sector (NCR / Plains)",
        "lat": 28.6139,
        "lon": 77.2090,
        "radius": 0.35,
        "weatherStationId": "STN-DELHI",
        "depotName": "NCR STRATEGIC LOGISTICS & RADAR FACILITY (DELHI)",
        "facilityType": "depot",
    },
    "WEST": {
        "name": "Western Sector (Rajasthan / Thar)",
        "lat": 26.9157,
        "lon": 70.9083,
        "radius": 0.40,
        "weatherStationId": "STN-JAISALMER",
        "depotName": "WESTERN DESERT TACTICAL LOGISTICS DEPOT (JAISALMER)",
        "facilityType": "forward_operating_base",
    },
    "KUTCH": {
        "name": "Western Sector (Gujarat / Kutch Littoral)",
        "lat": 23.2420,
        "lon": 69.6669,
        "radius": 0.35,
        "weatherStationId": "STN-BHUJ",
        "depotName": "KUTCH LITTORAL & MARITIME SUPPORT DEPOT (BHUJ)",
        "facilityType": "naval_anchorage",
    },
    "CENTRAL": {
        "name": "Central Sector (Nagpur Transit Corridor)",
        "lat": 21.1458,
        "lon": 79.0882,
        "radius": 0.45,
        "weatherStationId": "STN-NAGPUR",
        "depotName": "CENTRAL LOGISTICS TRANSIT HUB (NAGPUR)",
        "facilityType": "depot",
    },
    "EAST": {
        "name": "Eastern Sector (Odisha Coast / Paradip)",
        "lat": 20.3160,
        "lon": 86.6110,
        "radius": 0.35,
        "weatherStationId": "STN-PARADIP",
        "depotName": "BAY OF BENGAL NAVAL & RESCUE DEPOT (PARADIP)",
        "facilityType": "naval_anchorage",
    },
    "BENGAL": {
        "name": "Eastern Sector (West Bengal / Delta)",
        "lat": 22.5726,
        "lon": 88.3639,
        "radius": 0.30,
        "weatherStationId": "STN-KOLKATA",
        "depotName": "EASTERN COMMAND AIR & LOGISTICS DEPOT (KOLKATA)",
        "facilityType": "airbase",
    },
    "NORTHEAST": {
        "name": "North-Eastern Sector (Assam / Arunachal)",
        "lat": 26.6338,
        "lon": 92.7926,
        "radius": 0.35,
        "weatherStationId": "STN-TEZPUR",
        "depotName": "BRAHMAPUTRA VALLEY FRONTIER AIRBASE DEPOT (TEZPUR)",
        "facilityType": "airbase",
    },
    "SOUTH": {
        "name": "Southern Sector (Bengaluru Plateau)",
        "lat": 12.9716,
        "lon": 77.5946,
        "radius": 0.30,
        "weatherStationId": "STN-BENGALURU",
        "depotName": "SOUTHERN COMMAND HEADQUARTERS DEPOT (BENGALURU)",
        "facilityType": "depot",
    },
    "LITTORAL": {
        "name": "Littoral & Island Sector (Andaman & Nicobar)",
        "lat": 11.6234,
        "lon": 92.7265,
        "radius": 0.25,
        "weatherStationId": "STN-PORTBLAIR",
        "depotName": "PORT BLAIR MARITIME SUPPORT DEPOT",
        "facilityType": "naval_anchorage",
    },
}

PATROL_NAMES = ["ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF", "HOTEL"]
UAV_NAMES = ["RAVEN", "KITE", "FALCON", "OSPREY", "SHRIKE", "HARRIER", "MERLIN", "CONDOR"]
CONVOY_NAMES = ["MULE", "CARAVAN", "IRONHORSE", "PACKHORSE", "OXCART", "DRAY"]
SECTORS = ["A", "B", "C", "D"]
FIRST = ["A. Rao", "S. Menon", "K. Iyer", "P. Singh", "N. Das", "R. Kapoor", "V. Nair", "M. Bose"]
RANKS = ["SGT", "CPL", "LT", "PVT", "SSG"]
INDIA_FIRST = [
    "A. Rao", "S. Menon", "K. Iyer", "P. Singh", "N. Das", "R. Kapoor",
    "V. Nair", "M. Bose", "D. Sharma", "T. Chatterjee", "A. Kulkarni", "R. Varma"
]
INDIA_RANKS = ["SGT", "CPL", "LT", "PVT", "SSG", "CAPT"]
INCIDENT_KINDS = [
    "unauthorized-entry", "signal-jamming", "vehicle-breakdown",
    "unidentified-contact", "perimeter-breach", "medical", "supply-shortfall",
]
SEVERITIES = ["low", "medium", "high", "critical"]

SCENARIOS: dict[str, dict] = {
    "SC-1": {"id": "SC-1", "name": "Night Patrol Baseline",
             "incidentRate": 0.05, "weatherRate": 0.02,
             "uavCount": 4, "patrolCount": 8, "convoyCount": 3},
    "SC-2": {"id": "SC-2", "name": "Border Surveillance",
             "incidentRate": 0.09, "weatherRate": 0.04,
             "uavCount": 6, "patrolCount": 7, "convoyCount": 2},
    "SC-3": {"id": "SC-3", "name": "Counter-UAV Airspace Watch",
             "incidentRate": 0.14, "weatherRate": 0.03,
             "uavCount": 8, "patrolCount": 5, "convoyCount": 2},
    "SC-4": {"id": "SC-4", "name": "Convoy Escort",
             "incidentRate": 0.10, "weatherRate": 0.08,
             "uavCount": 3, "patrolCount": 6, "convoyCount": 6},
    # Pan-India Scenarios (all 11 sectors populated)
    "IN-BASE-LIVE": {"id": "IN-BASE-LIVE", "name": "Pan-India Live Context Baseline",
                    "incidentRate": 0.04, "weatherRate": 0.02,
                    "uavCount": 11, "patrolCount": 22, "convoyCount": 11},
    "IN-SC-CYCLONE": {"id": "IN-SC-CYCLONE", "name": "Bay of Bengal Severe Cyclone & Coastal Flooding",
                     "incidentRate": 0.16, "weatherRate": 0.15,
                     "uavCount": 11, "patrolCount": 22, "convoyCount": 11},
    "IN-SC-NORTH-COMMS": {"id": "IN-SC-NORTH-COMMS", "name": "Himalayan High-Altitude Comms Blackout & Blizzard",
                          "incidentRate": 0.12, "weatherRate": 0.10,
                          "uavCount": 11, "patrolCount": 22, "convoyCount": 11},
    "IN-SC-WEST-HEAT": {"id": "IN-SC-WEST-HEAT", "name": "Thar Desert Extreme Heatwave & Fuel Boil-off",
                        "incidentRate": 0.11, "weatherRate": 0.05,
                        "uavCount": 11, "patrolCount": 22, "convoyCount": 11},
    "IN-SC-LOGISTICS": {"id": "IN-SC-LOGISTICS", "name": "Central Corridor Supply Chokepoint & Depot Breakdown",
                        "incidentRate": 0.14, "weatherRate": 0.03,
                        "uavCount": 11, "patrolCount": 22, "convoyCount": 11},
    "IN-SC-CASCADE": {"id": "IN-SC-CASCADE", "name": "Pan-India Multi-Sector Cascading Crisis",
                      "incidentRate": 0.18, "weatherRate": 0.16,
                      "uavCount": 11, "patrolCount": 22, "convoyCount": 11},
}


def _ring(rand: Rand, cx: float, cy: float, r: float, n: int) -> list[tuple[float, float]]:
    pts = []
    phase = rand() * math.pi * 2
    for i in range(n):
        a = phase + (i / n) * math.pi * 2
        rr = r * (0.7 + rand() * 0.6)
        pts.append((cx + math.sin(a) * rr, cy + math.cos(a) * rr))
    return pts


class SimEngine:
    """One simulation run. Thread-safe for a single asyncio task."""

    def __init__(self) -> None:
        self.seed = 20260101
        self.scenario_id = "SC-1"
        self._rand: Rand = mulberry32(self.seed)
        self._next_id = 1
        self.tick = 0
        self._units: list[Unit] = []
        self._personnel: list[Person] = []
        self._depots: list[Depot] = []
        self._zones: list[dict[str, Any]] = []
        self._weather: list[WeatherCell] = []
        self._route_idx: dict[str, int] = {}
        self._silence: dict[str, int] = {}  # unit_id -> silent_until_tick
        self._sc: dict = SCENARIOS["SC-1"]

    # ------------------------------------------------------------------
    def start(self, seed: int, scenario_id: str) -> list[SimEvent]:
        self.seed = seed
        self.scenario_id = scenario_id
        self._sc = SCENARIOS.get(scenario_id, SCENARIOS["SC-1"])
        self._rand = mulberry32(seed)
        self._next_id = 1
        self.tick = 0
        self._route_idx.clear()
        self._silence.clear()
        self._weather = []

        if scenario_id.startswith("IN-"):
            return self._start_pan_india(seed, scenario_id)

        # Legacy SC-1..SC-4 Start (Preserves Golden Run bit-identical PRNG)
        rand = self._rand

        def mk(kind: str, callsign: str, i: int) -> Unit:
            cx = BASE_LAT + between(rand, -0.05, 0.05)
            cy = BASE_LON + between(rand, -0.05, 0.05)
            radius = 0.03 if kind == "uav" else 0.018
            route = _ring(rand, cx, cy, radius, 6)
            speed = 68.0 if kind == "uav" else (34.0 if kind == "convoy" else 6.0)
            return Unit(
                id=f"U-{kind.upper()}-{i}",
                callsign=callsign,
                kind=kind,
                lat=route[0][0], lon=route[0][1],
                heading=0.0, speedKph=speed,
                status="active",
                fuel=between(rand, 55, 100),
                battery=between(rand, 60, 100),
                lastSeenTick=0,
                sector=pick(rand, SECTORS),
                route=route,
            )

        sc = self._sc
        self._units = []
        self._personnel = []

        for i in range(sc["patrolCount"]):
            u = mk("patrol", f"{PATROL_NAMES[i % len(PATROL_NAMES)]}-{1 + (i % 3)}", i + 1)
            self._units.append(u)
            team_size = 2 + int(rand() * 2)
            for p_idx in range(team_size):
                self._personnel.append(Person(
                    id=f"P-{u.id}-{p_idx}",
                    name=pick(rand, FIRST), rank=pick(rand, RANKS),
                    unitId=u.id,
                    heartRate=round(between(rand, 62, 92)),
                    fatigue=round(between(rand, 0.1, 0.55), 2),
                    history=[],
                ))

        for i in range(sc["uavCount"]):
            self._units.append(mk("uav", f"{UAV_NAMES[i % len(UAV_NAMES)]}-{1 + (i % 3)}", i + 1))
        for i in range(sc["convoyCount"]):
            self._units.append(mk("convoy", f"{CONVOY_NAMES[i % len(CONVOY_NAMES)]}-{1 + (i % 3)}", i + 1))

        self._depots = []
        for i, label in enumerate(["NORTH", "CENTRAL", "SOUTH"]):
            self._depots.append(Depot(
                id=f"D-{i + 1}", name=f"{label} DEPOT",
                lat=BASE_LAT + between(rand, -0.04, 0.04),
                lon=BASE_LON + between(rand, -0.04, 0.04),
                stock={"fuel": round(between(rand, 2200, 4000)),
                       "medkit": round(between(rand, 60, 140)),
                       "rations": round(between(rand, 300, 700)),
                       "battery": round(between(rand, 80, 200))},
                capacity={"fuel": 4000, "medkit": 150, "rations": 700, "battery": 200},
            ))

        zones = [
            {"id": "Z-1", "name": "PATROL GRID NORTH", "kind": "patrol",
             "points": _ring(rand, BASE_LAT + 0.03, BASE_LON - 0.02, 0.035, 7)},
            {"id": "Z-2", "name": "PATROL GRID SOUTH", "kind": "patrol",
             "points": _ring(rand, BASE_LAT - 0.035, BASE_LON + 0.02, 0.03, 6)},
            {"id": "Z-3", "name": "RESTRICTED AIRSPACE R-12", "kind": "restricted",
             "points": _ring(rand, BASE_LAT + 0.01, BASE_LON + 0.045, 0.022, 5)},
            {"id": "Z-4", "name": "THREAT SECTOR C", "kind": "threat",
             "points": _ring(rand, BASE_LAT - 0.02, BASE_LON - 0.045, 0.026, 6)},
        ]

        self._zones = zones
        world_init = self._make_event(
            "world_init", "low", "system",
            {
                "seed": seed, "scenarioId": scenario_id,
                "units": [u.to_dict() for u in self._units],
                "depots": [d.to_dict() for d in self._depots],
                "personnel": [p.to_dict() for p in self._personnel],
                "zones": zones,
            }
        )
        return [world_init]

    # ------------------------------------------------------------------
    def _start_pan_india(self, seed: int, scenario_id: str) -> list[SimEvent]:
        """Initialise Pan-India world state distributed across Indian strategic sectors."""
        rand = self._rand
        sc = self._sc
        sector_keys = list(INDIAN_SECTORS.keys())

        def mk_india_unit(kind: str, callsign: str, i: int, sector_key: str) -> Unit:
            sec = INDIAN_SECTORS[sector_key]
            cx = sec["lat"] + between(rand, -sec["radius"] * 0.5, sec["radius"] * 0.5)
            cy = sec["lon"] + between(rand, -sec["radius"] * 0.5, sec["radius"] * 0.5)
            radius = sec["radius"] * (0.6 if kind == "uav" else 0.3)
            route = _ring(rand, cx, cy, radius, 6)
            speed = 120.0 if kind == "uav" else (48.0 if kind == "convoy" else 8.0)
            return Unit(
                id=f"U-IN-{kind.upper()}-{i}",
                callsign=callsign,
                kind=kind,
                lat=route[0][0], lon=route[0][1],
                heading=0.0, speedKph=speed,
                status="active",
                fuel=between(rand, 65, 100),
                battery=between(rand, 70, 100),
                lastSeenTick=0,
                sector=sector_key,
                route=route,
                personnelCount=1 if kind == "uav" else (2 if kind == "convoy" else 3),
            )

        self._units = []
        self._personnel = []

        # Tactical Patrols (2 per sector across all 11 sectors)
        roles = ["Squad Leader", "Scout", "Combat Medic", "Comms Specialist"]
        for i in range(sc["patrolCount"]):
            sec_k = sector_keys[i % len(sector_keys)]
            suffix = "ALPHA" if (i // len(sector_keys)) == 0 else "BRAVO"
            callsign = f"PATROL-{sec_k}-{suffix}"
            u = mk_india_unit("patrol", callsign, i + 1, sec_k)
            self._units.append(u)
            team_size = 2 + int(rand() * 2)
            u.personnelCount = team_size
            for p_idx in range(team_size):
                self._personnel.append(Person(
                    id=f"P-{u.id}-{p_idx}",
                    name=pick(rand, INDIA_FIRST),
                    rank=pick(rand, INDIA_RANKS),
                    unitId=u.id,
                    heartRate=round(between(rand, 65, 88)),
                    fatigue=round(between(rand, 0.05, 0.40), 2),
                    history=[],
                    condition="fit",
                    role=roles[p_idx % len(roles)],
                    sector=sec_k,
                ))

        # UAV Surveillance Drones (1 per sector across all 11 sectors)
        for i in range(sc["uavCount"]):
            sec_k = sector_keys[i % len(sector_keys)]
            callsign = f"UAV-{sec_k}-{UAV_NAMES[i % len(UAV_NAMES)]}"
            u = mk_india_unit("uav", callsign, i + 1, sec_k)
            self._units.append(u)
            self._personnel.append(Person(
                id=f"P-{u.id}-0",
                name=pick(rand, INDIA_FIRST),
                rank=pick(rand, INDIA_RANKS),
                unitId=u.id,
                heartRate=round(between(rand, 68, 82)),
                fatigue=round(between(rand, 0.05, 0.25), 2),
                history=[],
                condition="fit",
                role="UAV Remote Pilot",
                sector=sec_k,
            ))

        # Logistics Convoys (1 per sector across all 11 sectors)
        for i in range(sc["convoyCount"]):
            sec_k = sector_keys[i % len(sector_keys)]
            callsign = f"CONVOY-{sec_k}-{CONVOY_NAMES[i % len(CONVOY_NAMES)]}"
            u = mk_india_unit("convoy", callsign, i + 1, sec_k)
            u.personnelCount = 2
            self._units.append(u)
            for p_idx in range(2):
                self._personnel.append(Person(
                    id=f"P-{u.id}-{p_idx}",
                    name=pick(rand, INDIA_FIRST),
                    rank=pick(rand, INDIA_RANKS),
                    unitId=u.id,
                    heartRate=round(between(rand, 70, 85)),
                    fatigue=round(between(rand, 0.10, 0.35), 2),
                    history=[],
                    condition="fit",
                    role="Convoy Commander" if p_idx == 0 else "Heavy Transport Driver",
                    sector=sec_k,
                ))

        # Strategic Depots & Support Facilities across all 11 Indian sectors
        self._depots = []
        for sec_k in sector_keys:
            sec = INDIAN_SECTORS[sec_k]
            self._depots.append(
                Depot(
                    id=f"D-IN-{sec_k}",
                    name=sec["depotName"],
                    lat=sec["lat"],
                    lon=sec["lon"],
                    stock={
                        "fuel": round(between(rand, 3800, 6500)),
                        "medkit": round(between(rand, 100, 250)),
                        "rations": round(between(rand, 600, 1500)),
                        "battery": round(between(rand, 120, 350)),
                    },
                    capacity={"fuel": 8000, "medkit": 350, "rations": 2000, "battery": 500},
                    sector=sec_k,
                    facilityType=sec.get("facilityType", "depot"),
                )
            )

        # Strategic Tactical Zones covering all 11 Indian sectors
        zones = []
        for sec_k in sector_keys:
            sec = INDIAN_SECTORS[sec_k]
            kind = "threat" if sec_k == "EAST" else ("restricted" if sec_k in ("WEST", "KUTCH", "LITTORAL") else "patrol")
            zones.append({
                "id": f"Z-IN-{sec_k}",
                "name": f"{sec['name'].upper()} TACTICAL GRID",
                "kind": kind,
                "points": _ring(rand, sec["lat"], sec["lon"], sec["radius"] * 1.1, 7),
                "sector": sec_k,
            })
        self._zones = zones

        # Injects initial artificial scenario weather / effects
        if scenario_id == "IN-SC-CYCLONE":
            # Initialize Cyclone Vardah-Sim in Bay of Bengal
            cell = WeatherCell(
                id="W-CYCLONE-BOB",
                lat=18.50, lon=87.20,
                radiusM=180000,
                intensity=0.95,
                kind="storm",
            )
            self._weather.append(cell)
        elif scenario_id == "IN-SC-NORTH-COMMS":
            # Initialize Himalayan blizzard cell in Ladakh
            cell = WeatherCell(
                id="W-BLIZZARD-LEH",
                lat=34.15, lon=77.58,
                radiusM=95000,
                intensity=0.90,
                kind="storm",
            )
            self._weather.append(cell)
        elif scenario_id == "IN-SC-WEST-HEAT":
            # Initialize extreme dust / thermal wave in Thar
            cell = WeatherCell(
                id="W-HEATWAVE-THAR",
                lat=26.91, lon=70.91,
                radiusM=120000,
                intensity=0.92,
                kind="dust",
            )
            self._weather.append(cell)
        elif scenario_id == "IN-SC-CASCADE":
            # Compound crisis across all Indian sectors
            self._weather.extend([
                WeatherCell(id="W-CYCLONE-BOB", lat=18.50, lon=87.20, radiusM=180000, intensity=0.95, kind="storm"),
                WeatherCell(id="W-BLIZZARD-LEH", lat=34.15, lon=77.58, radiusM=95000, intensity=0.90, kind="storm"),
                WeatherCell(id="W-HEATWAVE-THAR", lat=26.91, lon=70.91, radiusM=120000, intensity=0.92, kind="dust"),
                WeatherCell(id="W-SQUALL-ANDAMAN", lat=11.62, lon=92.73, radiusM=80000, intensity=0.85, kind="rain"),
            ])

        world_init = self._make_event(
            "world_init", "low", "system",
            {
                "seed": seed, "scenarioId": scenario_id,
                "worldMode": "baseline" if scenario_id == "IN-BASE-LIVE" else "simulation",
                "subcontinent": "India",
                "center": [22.5937, 78.9629],
                "units": [u.to_dict() for u in self._units],
                "depots": [d.to_dict() for d in self._depots],
                "personnel": [p.to_dict() for p in self._personnel],
                "zones": zones,
                "weather": [w.to_dict() for w in self._weather],
            }
        )
        return [world_init]

    # ------------------------------------------------------------------
    def inject(self, partial: dict) -> list[SimEvent]:
        """Apply an operator-sourced event (mission tasking, ack, close)."""
        p = partial.get("payload", {})
        target_id = partial.get("entityId")
        if (partial.get("type") in ("system", "mission_assigned", "route_assigned") and (p.get("mission") or p.get("route"))):
            for u in self._units:
                if u.id == target_id:
                    if p.get("route"):
                        u.route = [tuple(wp) for wp in p["route"]]
                        self._route_idx[u.id] = 0
                    mid = p.get("missionId", f"MSN-{self.tick}-{u.id}")
                    u.activeMissionId = mid
                    for prs in self._personnel:
                        if prs.unitId == u.id:
                            prs.activeMissionId = mid
                            if mid not in prs.missionHistory:
                                prs.missionHistory.append(mid)
        ev = self._make_event(
            partial["type"], partial.get("severity", "low"),
            partial.get("entityId", "system"), p,
        )
        return [ev]

    def step(self) -> list[SimEvent]:
        """Advance the simulation by one tick; return the produced events."""
        if self.scenario_id.startswith("IN-"):
            return self._step_pan_india()

        # Legacy SC-1..SC-4 step (Preserves Golden Run bit-identical PRNG)
        self.tick += 1
        rand = self._rand
        sc = self._sc
        out: list[dict[str, Any]] = []

        # weather
        if rand() < sc["weatherRate"] and len(self._weather) < 4:
            cell = WeatherCell(
                id=f"W-{self.tick}",
                lat=BASE_LAT + between(rand, -0.05, 0.05),
                lon=BASE_LON + between(rand, -0.05, 0.05),
                radiusM=round(between(rand, 900, 2600)),
                intensity=round(between(rand, 0.3, 1.0), 2),
                kind=pick(rand, ["rain", "storm", "fog", "dust"]),
            )
            self._weather.append(cell)
            out.append({"type": "weather_spawn",
                         "severity": "high" if cell.intensity > 0.7 else "medium",
                         "entityId": cell.id, "payload": cell.to_dict()})

        surviving = []
        for w in self._weather:
            w.lat += between(rand, -0.0016, 0.0016)
            w.lon += between(rand, -0.0016, 0.0016)
            w.intensity = round(max(0.0, w.intensity - 0.004), 3)
            if w.intensity <= 0.05:
                out.append({"type": "weather_clear", "severity": "low",
                             "entityId": w.id, "payload": {}})
            else:
                out.append({"type": "weather_move", "severity": "low",
                             "entityId": w.id,
                             "payload": {"lat": w.lat, "lon": w.lon, "intensity": w.intensity}})
                surviving.append(w)
        self._weather = surviving

        # units
        for u in self._units:
            silent_until = self._silence.get(u.id, 0)
            if silent_until > self.tick:
                continue
            if rand() < 0.004:
                self._silence[u.id] = self.tick + round(between(rand, 180, 320))
                out.append({"type": "comms_loss", "severity": "high",
                             "entityId": u.id, "payload": {"callsign": u.callsign}})
                out.append({"type": "alert_raise", "severity": "high",
                             "entityId": u.id,
                             "payload": {"message": f"{u.callsign} comms silence detected",
                                          "alertId": f"AL-{self.tick}-{u.id}"}})
                continue
            if silent_until == self.tick:
                out.append({"type": "comms_restore", "severity": "low",
                             "entityId": u.id, "payload": {"callsign": u.callsign}})

            idx = self._route_idx.get(u.id, 0)
            target = u.route[idx % len(u.route)]
            d_lat = target[0] - u.lat
            d_lon = target[1] - u.lon
            dist = math.hypot(d_lat, d_lon)
            in_weather = any(
                math.hypot(w.lat - u.lat, w.lon - u.lon) * 111000 < w.radiusM
                for w in self._weather
            )
            base_step = (u.speedKph / 3600 / 111) * (0.45 if in_weather else 1.0) * 4
            if dist < base_step * 1.2:
                self._route_idx[u.id] = idx + 1
            else:
                u.lat += (d_lat / dist) * base_step
                u.lon += (d_lon / dist) * base_step
                u.heading = math.degrees(math.atan2(d_lon, d_lat))

            new_status = "slowed" if in_weather else "active"
            if new_status != u.status:
                u.status = new_status
                out.append({"type": "unit_status", "severity": "low",
                             "entityId": u.id, "payload": {"status": new_status}})
            u.lastSeenTick = self.tick
            out.append({"type": "unit_move", "severity": "low",
                         "entityId": u.id,
                         "payload": {"lat": u.lat, "lon": u.lon,
                                      "heading": u.heading, "inWeather": in_weather}})

            if self.tick % 5 == 0:
                u.fuel = max(0.0, u.fuel - between(rand, 0.05, 0.35))
                bat_drain = between(rand, 0.1, 0.5) * (2 if u.kind == "uav" else 1)
                u.battery = max(0.0, u.battery - bat_drain)
                sev = "high" if u.battery < 15 or u.fuel < 15 else "low"
                out.append({"type": "resource_level", "severity": sev,
                             "entityId": u.id,
                             "payload": {"fuel": round(u.fuel, 1), "battery": round(u.battery, 1)}})
                if u.battery < 12:
                    out.append({"type": "alert_raise", "severity": "critical",
                                 "entityId": u.id,
                                 "payload": {"message": f"{u.callsign} battery critical ({u.battery:.0f}%)",
                                              "alertId": f"AL-{self.tick}-BAT-{u.id}"}})

            if u.kind == "uav" and rand() < 0.02:
                out.append({"type": "detection", "severity": "medium",
                             "entityId": u.id,
                             "payload": {"label": pick(rand, ["vehicle", "person", "uav", "structure"]),
                                          "confidence": round(between(rand, 0.45, 0.98), 2),
                                          "model": "yolov8n-doip-v1.4",
                                          "lat": u.lat, "lon": u.lon,
                                          "frame": f"F-{self.tick}-{u.id}"}})

        # depots
        if self.tick % 10 == 0:
            for d in self._depots:
                d.stock["fuel"] = max(0, d.stock["fuel"] - round(between(rand, 2, 14)))
                d.stock["medkit"] = max(0, d.stock["medkit"] - (1 if rand() < 0.3 else 0))
                d.stock["rations"] = max(0, d.stock["rations"] - round(between(rand, 1, 5)))
                d.stock["battery"] = max(0, d.stock["battery"] - (1 if rand() < 0.5 else 0))
                out.append({"type": "resource_level",
                             "severity": "high" if d.stock["fuel"] < 600 else "low",
                             "entityId": d.id, "payload": {"stock": dict(d.stock)}})

        # vitals
        if self.tick % 8 == 0:
            for p in self._personnel:
                p.heartRate = round(min(180, max(52, p.heartRate + between(rand, -5, 6))))
                p.fatigue = round(min(1.0, p.fatigue + between(rand, -0.004, 0.012)), 3)
                out.append({"type": "vitals",
                             "severity": "high" if p.fatigue > 0.8 else "low",
                             "entityId": p.id,
                             "payload": {"heartRate": p.heartRate, "fatigue": p.fatigue}})

        # incidents
        if rand() < sc["incidentRate"]:
            u = pick(rand, self._units)
            bump = 0.6 if sc["incidentRate"] > 0.1 else 0
            sev_idx = min(3, int(rand() * 4 + bump))
            sev = SEVERITIES[sev_idx]
            inc_id = f"INC-{self.tick}"
            out.append({"type": "incident_open", "severity": sev,
                         "entityId": inc_id,
                         "payload": {"kind": pick(rand, INCIDENT_KINDS),
                                      "lat": u.lat + between(rand, -0.004, 0.004),
                                      "lon": u.lon + between(rand, -0.004, 0.004),
                                      "reportedBy": u.id, "callsign": u.callsign}})
            out.append({"type": "alert_raise", "severity": sev,
                         "entityId": inc_id,
                         "payload": {"message": f"Incident {inc_id} reported by {u.callsign}",
                                      "alertId": f"AL-{inc_id}"}})

        return [self._make_event(p["type"], p["severity"], p["entityId"], p["payload"])
                for p in out]

    # ------------------------------------------------------------------
    def _step_pan_india(self) -> list[SimEvent]:
        """Step Pan-India world simulation with scenario-specific artificial impacts."""
        self.tick += 1
        rand = self._rand
        sc = self._sc
        sc_id = self.scenario_id
        out: list[dict[str, Any]] = []

        # Weather updates & movement
        # Cyclone scenario: Move cyclone NW towards Odisha coast
        for w in self._weather:
            if "CYCLONE" in w.id:
                # Tracks NW: lat increases, lon decreases slightly
                w.lat += between(rand, 0.003, 0.008)
                w.lon -= between(rand, 0.002, 0.006)
                out.append({"type": "weather_move", "severity": "high",
                             "entityId": w.id,
                             "payload": {"lat": round(w.lat, 4), "lon": round(w.lon, 4),
                                          "intensity": w.intensity, "name": "Cyclone Vardah-Sim"}})
            elif "BLIZZARD" in w.id:
                w.lat += between(rand, -0.002, 0.002)
                w.lon += between(rand, -0.002, 0.002)
                out.append({"type": "weather_move", "severity": "high",
                             "entityId": w.id,
                             "payload": {"lat": round(w.lat, 4), "lon": round(w.lon, 4),
                                          "intensity": w.intensity, "name": "Himalayan Blizzard Cell"}})
            elif "HEATWAVE" in w.id:
                w.lat += between(rand, -0.001, 0.001)
                w.lon += between(rand, -0.001, 0.001)
                out.append({"type": "weather_move", "severity": "medium",
                             "entityId": w.id,
                             "payload": {"lat": round(w.lat, 4), "lon": round(w.lon, 4),
                                          "intensity": w.intensity, "name": "Thar High Thermal Cell"}})
            elif "SQUALL" in w.id:
                w.lat += between(rand, -0.003, 0.003)
                w.lon += between(rand, -0.003, 0.003)
                out.append({"type": "weather_move", "severity": "medium",
                             "entityId": w.id,
                             "payload": {"lat": round(w.lat, 4), "lon": round(w.lon, 4),
                                          "intensity": w.intensity, "name": "Andaman Maritime Squall"}})
            else:
                w.lat += between(rand, -0.002, 0.002)
                w.lon += between(rand, -0.002, 0.002)
                out.append({"type": "weather_move", "severity": "low",
                             "entityId": w.id,
                             "payload": {"lat": round(w.lat, 4), "lon": round(w.lon, 4),
                                          "intensity": w.intensity}})

        # Unit movements and impacts
        for u in self._units:
            silent_until = self._silence.get(u.id, 0)
            if silent_until > self.tick:
                continue

            # Comms loss rate elevated in North Comms Blackout & Cascade
            comms_fail_rate = 0.025 if (sc_id in ("IN-SC-NORTH-COMMS", "IN-SC-CASCADE") and u.sector == "NORTH") else 0.004
            if rand() < comms_fail_rate:
                self._silence[u.id] = self.tick + round(between(rand, 180, 420))
                out.append({"type": "comms_loss", "severity": "high",
                             "entityId": u.id, "payload": {"callsign": u.callsign, "sector": u.sector}})
                out.append({"type": "alert_raise", "severity": "high",
                             "entityId": u.id,
                             "payload": {"message": f"{u.callsign} RF link silence in {u.sector} sector",
                                          "alertId": f"AL-IN-{self.tick}-{u.id}"}})
                continue

            if silent_until == self.tick:
                out.append({"type": "comms_restore", "severity": "low",
                             "entityId": u.id, "payload": {"callsign": u.callsign}})

            idx = self._route_idx.get(u.id, 0)
            target = u.route[idx % len(u.route)]
            d_lat = target[0] - u.lat
            d_lon = target[1] - u.lon
            dist = math.hypot(d_lat, d_lon)

            # Weather proximity check (using geographic distance)
            in_weather = any(
                math.hypot(w.lat - u.lat, w.lon - u.lon) * 111000 < w.radiusM
                for w in self._weather
            )

            # Special scenario speed slowdowns:
            # - Cyclone floods East Coast routes
            # - Central logistics breakdown halts Central convoys
            speed_mult = 1.0
            if in_weather:
                speed_mult = 0.35 if (sc_id in ("IN-SC-CYCLONE", "IN-SC-CASCADE")) else 0.50
            if (sc_id in ("IN-SC-LOGISTICS", "IN-SC-CASCADE")) and u.sector == "CENTRAL" and u.kind == "convoy":
                speed_mult = 0.15  # Bottleneck halt

            base_step = (u.speedKph / 3600 / 111) * speed_mult * 4
            if dist < base_step * 1.2:
                self._route_idx[u.id] = idx + 1
            else:
                u.lat += (d_lat / dist) * base_step
                u.lon += (d_lon / dist) * base_step
                u.heading = math.degrees(math.atan2(d_lon, d_lat))

            new_status = "halted" if speed_mult <= 0.20 else ("slowed" if speed_mult < 0.70 else "active")
            if new_status != u.status:
                u.status = new_status
                out.append({"type": "unit_status", "severity": "medium" if new_status == "halted" else "low",
                             "entityId": u.id, "payload": {"status": new_status}})
            u.lastSeenTick = self.tick
            out.append({"type": "unit_move", "severity": "low",
                         "entityId": u.id,
                         "payload": {"lat": round(u.lat, 5), "lon": round(u.lon, 5),
                                      "heading": round(u.heading, 1), "inWeather": in_weather,
                                      "sector": u.sector}})

            # Resource consumption
            if self.tick % 5 == 0:
                # Fuel drain: higher in Thar heatwave due to boil-off
                fuel_rate_mult = 2.4 if (sc_id in ("IN-SC-WEST-HEAT", "IN-SC-CASCADE") and u.sector == "WEST") else 1.0
                u.fuel = max(0.0, u.fuel - between(rand, 0.05, 0.35) * fuel_rate_mult)

                # Battery drain: 3x in Himalayan freeze
                bat_rate_mult = 3.0 if (sc_id in ("IN-SC-NORTH-COMMS", "IN-SC-CASCADE") and u.sector == "NORTH") else 1.0
                bat_drain = between(rand, 0.1, 0.5) * (2 if u.kind == "uav" else 1) * bat_rate_mult
                u.battery = max(0.0, u.battery - bat_drain)

                sev = "high" if u.battery < 15 or u.fuel < 15 else "low"
                out.append({"type": "resource_level", "severity": sev,
                             "entityId": u.id,
                             "payload": {"fuel": round(u.fuel, 1), "battery": round(u.battery, 1)}})
                if u.battery < 12:
                    out.append({"type": "alert_raise", "severity": "critical",
                                 "entityId": u.id,
                                 "payload": {"message": f"{u.callsign} battery critical ({u.battery:.0f}%)",
                                              "alertId": f"AL-IN-{self.tick}-BAT-{u.id}"}})

            # UAV detections
            if u.kind == "uav" and rand() < 0.025:
                out.append({"type": "detection", "severity": "medium",
                             "entityId": u.id,
                             "payload": {"label": pick(rand, ["patrol", "transport", "relay-station", "radar-contact"]),
                                          "confidence": round(between(rand, 0.55, 0.98), 2),
                                          "model": "yolov8n-pan-india-v2.0",
                                          "lat": round(u.lat, 5), "lon": round(u.lon, 5),
                                          "sector": u.sector,
                                          "frame": f"F-IN-{self.tick}-{u.id}"}})

        # Depot consumption & logistics breakdown
        if self.tick % 10 == 0:
            for d in self._depots:
                burn_mult = 3.5 if (sc_id in ("IN-SC-LOGISTICS", "IN-SC-CASCADE") and d.id == "D-IN-CENTRAL") else 1.0
                d.stock["fuel"] = max(0, d.stock["fuel"] - round(between(rand, 3, 20) * burn_mult))
                d.stock["rations"] = max(0, d.stock["rations"] - round(between(rand, 2, 8) * burn_mult))
                d.stock["medkit"] = max(0, d.stock["medkit"] - (1 if rand() < 0.25 else 0))
                d.stock["battery"] = max(0, d.stock["battery"] - (1 if rand() < 0.4 else 0))
                is_crit = d.stock["fuel"] < 1000 or d.stock["rations"] < 200
                out.append({"type": "resource_level",
                             "severity": "critical" if is_crit else "low",
                             "entityId": d.id, "payload": {"stock": dict(d.stock)}})
                if is_crit and self.tick % 30 == 0:
                    out.append({"type": "alert_raise", "severity": "critical",
                                 "entityId": d.id,
                                 "payload": {"message": f"Supply depletion alert at {d.name}",
                                              "alertId": f"AL-IN-DEP-{self.tick}-{d.id}"}})

        # Incidents
        if rand() < sc["incidentRate"]:
            u = pick(rand, self._units)
            inc_kind = pick(rand, INCIDENT_KINDS)
            if sc_id == "IN-SC-LOGISTICS":
                inc_kind = "supply-shortfall"
            elif sc_id == "IN-SC-NORTH-COMMS":
                inc_kind = "signal-jamming"
            elif sc_id == "IN-SC-WEST-HEAT":
                inc_kind = "vehicle-breakdown"
            elif sc_id == "IN-SC-CASCADE":
                if u.sector == "NORTH":
                    inc_kind = "signal-jamming"
                elif u.sector == "WEST":
                    inc_kind = "vehicle-breakdown"
                elif u.sector == "CENTRAL":
                    inc_kind = "supply-shortfall"
                elif u.sector == "EAST":
                    inc_kind = "perimeter-breach"
                else:
                    inc_kind = pick(rand, INCIDENT_KINDS)

            inc_id = f"INC-IN-{self.tick}"
            sev = "critical" if inc_kind in ("supply-shortfall", "signal-jamming") else "high"
            out.append({"type": "incident_open", "severity": sev,
                         "entityId": inc_id,
                         "payload": {"kind": inc_kind,
                                      "lat": round(u.lat + between(rand, -0.01, 0.01), 5),
                                      "lon": round(u.lon + between(rand, -0.01, 0.01), 5),
                                      "sector": u.sector,
                                      "reportedBy": u.id, "callsign": u.callsign}})
            out.append({"type": "alert_raise", "severity": sev,
                         "entityId": inc_id,
                         "payload": {"message": f"Incident {inc_id} ({inc_kind}) reported in {u.sector} by {u.callsign}",
                                      "alertId": f"AL-{inc_id}"}})

        return [self._make_event(p["type"], p["severity"], p["entityId"], p["payload"])
                for p in out]

    # ------------------------------------------------------------------
    def _make_event(self, type_: str, severity: str, entity_id: str,
                    payload: dict) -> SimEvent:
        ev = SimEvent(
            id=self._next_id,
            tick=self.tick,
            simTime=self.tick * 1000,
            type=type_,
            severity=severity,
            entityId=entity_id,
            payload=payload,
        )
        self._next_id += 1
        return ev

    def snapshot(self) -> dict[str, Any]:
        """Return a serializable dictionary snapshot of the current engine state."""
        return {
            "tick": self.tick,
            "scenarioId": getattr(self, "scenario_id", "SC-1"),
            "seed": getattr(self, "seed", 0),
            "units": [u.to_dict() for u in self._units],
            "depots": [d.to_dict() for d in self._depots],
            "personnel": [p.to_dict() for p in self._personnel],
            "zones": self._zones,
            "weather": [w.to_dict() for w in self._weather],
        }
