"""Dataclass mirrors of src/sim/types.ts — used by engine.py and reducers."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["low", "medium", "high", "critical"]
EventType = Literal[
    "world_init", "unit_move", "unit_status", "comms_loss", "comms_restore",
    "incident_open", "incident_close", "alert_raise", "alert_ack",
    "resource_level", "vitals", "weather_spawn", "weather_move",
    "weather_clear", "detection", "system",
]


@dataclass
class SimEvent:
    id: int
    tick: int
    simTime: int
    type: str
    severity: str
    entityId: str
    payload: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tick": self.tick,
            "simTime": self.simTime,
            "type": self.type,
            "severity": self.severity,
            "entityId": self.entityId,
            "payload": self.payload,
        }


@dataclass
class Unit:
    id: str
    callsign: str
    kind: str  # patrol | uav | convoy | depot
    lat: float
    lon: float
    heading: float
    speedKph: float
    status: str  # active | slowed | halted | stale
    fuel: float
    battery: float
    lastSeenTick: int
    sector: str
    route: list[tuple[float, float]]
    activeMissionId: str | None = None
    personnelCount: int | None = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "callsign": self.callsign,
            "kind": self.kind,
            "lat": self.lat,
            "lon": self.lon,
            "heading": self.heading,
            "speedKph": self.speedKph,
            "status": self.status,
            "fuel": self.fuel,
            "battery": self.battery,
            "lastSeenTick": self.lastSeenTick,
            "sector": self.sector,
            "route": self.route,
        }
        if self.activeMissionId is not None:
            d["activeMissionId"] = self.activeMissionId
        if self.personnelCount is not None:
            d["personnelCount"] = self.personnelCount
        return d


@dataclass
class Depot:
    id: str
    name: str
    lat: float
    lon: float
    stock: dict[str, float]
    capacity: dict[str, float]
    sector: str | None = None
    facilityType: str | None = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "stock": self.stock,
            "capacity": self.capacity,
        }
        if self.sector is not None:
            d["sector"] = self.sector
        if self.facilityType is not None:
            d["facilityType"] = self.facilityType
        return d


@dataclass
class Person:
    id: str
    name: str
    rank: str
    unitId: str
    heartRate: float
    fatigue: float
    history: list[float] = field(default_factory=list)
    condition: str = "fit"
    activeMissionId: str | None = None
    missionHistory: list[str] = field(default_factory=list)
    role: str | None = None
    sector: str | None = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "rank": self.rank,
            "unitId": self.unitId,
            "heartRate": self.heartRate,
            "fatigue": self.fatigue,
            "history": self.history,
        }
        if self.condition != "fit":
            d["condition"] = self.condition
        if self.activeMissionId is not None:
            d["activeMissionId"] = self.activeMissionId
        if self.missionHistory:
            d["missionHistory"] = self.missionHistory
        if self.role is not None:
            d["role"] = self.role
        if self.sector is not None:
            d["sector"] = self.sector
        return d


@dataclass
class WeatherCell:
    id: str
    lat: float
    lon: float
    radiusM: float
    intensity: float
    kind: str
    sector: str | None = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "lat": self.lat,
            "lon": self.lon,
            "radiusM": self.radiusM,
            "intensity": self.intensity,
            "kind": self.kind,
        }
        if self.sector is not None:
            d["sector"] = self.sector
        return d


@dataclass
class Zone:
    id: str
    name: str
    kind: str  # patrol | restricted | threat
    points: list[tuple[float, float]]
    sector: str | None = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "points": self.points,
        }
        if self.sector is not None:
            d["sector"] = self.sector
        return d
