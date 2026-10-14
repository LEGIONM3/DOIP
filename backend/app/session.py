"""SimSession — wraps SimEngine in an async loop and streams events over WebSocket.

Authoritative simulation session:
- Bounded clock accumulator separating wall-clock scheduling from simulation advancement.
- Speed multiplier 0.25x to 20x applied immediately without engine restarts.
- Full state persistence: world snapshots, units, positions, personnel, vitals samples.
- Live stream resilience, late-joiner log replays, and clean stop/pause/resume semantics.
"""

import asyncio
import json
import time
from typing import Any
from fastapi import WebSocket, WebSocketDisconnect
from .engine import SimEngine
from . import db as db_mod

SNAPSHOT_EVERY = 10   # ticks between world_json upserts


class SimSession:
    def __init__(self, seed: int, scenario_id: str, speed: float = 1.0,
                 run_id: str | None = None) -> None:
        self.engine = SimEngine()
        self.seed = seed
        self.scenario_id = scenario_id
        self.speed = max(0.25, min(20.0, speed))
        self.run_id = run_id or f"RUN-{seed}-{scenario_id}"
        self._clients: list[WebSocket] = []
        self._paused = False
        self._stopped = False
        self._task: asyncio.Task | None = None
        self._log: list[dict] = []    # full event log for run persistence

        # Lightweight world state maintained for snapshot serialisation and APIs
        self._units: dict[str, dict] = {}
        self._depots: dict[str, dict] = {}
        self._personnel: dict[str, dict] = {}
        self._weather: dict[str, dict] = {}
        self._incidents: dict[str, dict] = {}
        self._alerts: dict[str, dict] = {}
        self._zones: list = []
        self._pending_pos_samples: list[dict] = []
        self._pending_vitals_samples: list[dict] = []

    def _flush_pending_samples(self) -> None:
        """Batch-persist queued position and vitals samples to SQLite / PostgreSQL."""
        if self._pending_pos_samples:
            batch = self._pending_pos_samples
            self._pending_pos_samples = []
            try:
                db_mod.save_unit_position_samples_batch(batch)
            except Exception:
                pass
        if self._pending_vitals_samples:
            batch = self._pending_vitals_samples
            self._pending_vitals_samples = []
            try:
                db_mod.save_personnel_vitals_samples_batch(batch)
            except Exception:
                pass

    # ------------------------------------------------------------------
    async def start(self) -> None:
        """Initialise the engine and begin the tick loop."""
        if self._task and not self._task.done():
            self._stopped = True
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

        self._stopped = False
        self._paused = False
        init_events = self.engine.start(self.seed, self.scenario_id)
        for ev in init_events:
            d = ev.to_dict()
            self._log.append(d)
            self._apply(d)
        await self._broadcast(init_events)
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        """Fixed-tick accumulator loop separating wall clock from sim advancement."""
        last_wall_time = time.monotonic()
        accumulator = 0.0

        try:
            while not self._stopped:
                now = time.monotonic()
                elapsed = max(0.0, now - last_wall_time)
                last_wall_time = now

                if self._paused or self._stopped:
                    accumulator = 0.0
                    await asyncio.sleep(0.05)
                    continue

                # Bound elapsed time to 0.5s to prevent large time jumps after system lag
                bounded_elapsed = min(0.50, elapsed)
                accumulator += bounded_elapsed * self.speed

                stepped_any = False
                max_steps_per_cycle = 12
                steps_taken = 0

                while accumulator >= 1.0 and steps_taken < max_steps_per_cycle and not self._stopped and not self._paused:
                    accumulator -= 1.0
                    steps_taken += 1
                    stepped_any = True

                    events = self.engine.step()
                    if events:
                        for ev in events:
                            d = ev.to_dict()
                            self._log.append(d)
                            self._apply(d)
                        await self._broadcast(events)

                    # Persist snapshot every SNAPSHOT_EVERY ticks
                    if self.run_id and self.engine.tick % SNAPSHOT_EVERY == 0:
                        world = self._world_snapshot()
                        try:
                            db_mod.save_world_snapshot(self.run_id, world)
                        except Exception:
                            pass

                if stepped_any:
                    self._flush_pending_samples()

                # Calculate next sleep interval
                if accumulator < 1.0:
                    time_until_next = (1.0 - accumulator) / max(0.25, self.speed)
                    sleep_dur = max(0.005, min(0.05, time_until_next))
                    await asyncio.sleep(sleep_dur)
                else:
                    await asyncio.sleep(0.002)
        except asyncio.CancelledError:
            pass
        except Exception as ex:
            print(f"[SimSession] Loop error: {ex}")

    # ------------------------------------------------------------------
    def _apply(self, ev: dict) -> None:
        """Incrementally update the authoritative world mirror and persistent stores."""
        t = ev.get("type")
        p = ev.get("payload", {})
        eid = ev.get("entityId", "")
        tick = ev.get("tick", self.engine.tick)
        sim_time = ev.get("simTime", tick * 1000)

        if t == "world_init":
            for u in p.get("units", []):
                self._units[u["id"]] = dict(u)
                try:
                    db_mod.save_unit({**u, "run_id": self.run_id})
                except Exception:
                    pass
            for d in p.get("depots", []):
                self._depots[d["id"]] = dict(d)
            for prs in p.get("personnel", []):
                self._personnel[prs["id"]] = dict(prs)
                try:
                    db_mod.save_person({**prs, "run_id": self.run_id})
                except Exception:
                    pass
            self._zones = p.get("zones", [])

        elif t == "unit_move":
            if eid in self._units:
                self._units[eid].update({
                    "lat": p.get("lat"),
                    "lon": p.get("lon"),
                    "heading": p.get("heading"),
                    "inWeather": p.get("inWeather", False),
                    "lastSeenTick": tick,
                })
                self._pending_pos_samples.append({
                    "run_id": self.run_id,
                    "unit_id": eid,
                    "tick": tick,
                    "sim_time": sim_time,
                    "lat": p.get("lat"),
                    "lon": p.get("lon"),
                    "heading": p.get("heading", 0.0),
                    "speed_kph": self._units[eid].get("speedKph", 0.0),
                    "in_weather": p.get("inWeather", False),
                })

        elif t == "unit_status":
            if eid in self._units:
                self._units[eid]["status"] = p.get("status")

        elif t == "resource_level":
            if eid in self._units:
                if "fuel" in p:
                    self._units[eid]["fuel"] = p["fuel"]
                if "battery" in p:
                    self._units[eid]["battery"] = p["battery"]
            if eid in self._depots and "stock" in p:
                self._depots[eid]["stock"] = p["stock"]

        elif t == "vitals":
            if eid in self._personnel:
                hr = p.get("heartRate")
                fatigue = p.get("fatigue")
                self._personnel[eid].update({
                    "heartRate": hr,
                    "fatigue": fatigue,
                })
                # Determine physiological condition
                if fatigue is not None and hr is not None:
                    if fatigue > 0.80 or hr > 150:
                        cond = "strained"
                    elif fatigue > 0.60 or hr > 130:
                        cond = "fatigued"
                    else:
                        cond = "fit"
                    self._personnel[eid]["condition"] = cond
                self._pending_vitals_samples.append({
                    "run_id": self.run_id,
                    "person_id": eid,
                    "tick": tick,
                    "sim_time": sim_time,
                    "heart_rate": hr or 72.0,
                    "fatigue": fatigue or 0.20,
                    "activity_type": "patrol",
                })

        elif t == "weather_spawn":
            self._weather[eid] = dict(p)
        elif t == "weather_move":
            if eid in self._weather:
                self._weather[eid].update({"lat": p.get("lat"), "lon": p.get("lon"),
                                            "intensity": p.get("intensity")})
        elif t == "weather_clear":
            self._weather.pop(eid, None)

        elif t == "incident_open":
            self._incidents[eid] = {
                "id": eid,
                "tick": tick,
                "severity": ev.get("severity", "medium"),
                "kind": p.get("kind", "incident"),
                "lat": p.get("lat"),
                "lon": p.get("lon"),
                "open": True,
            }
        elif t == "incident_close":
            if eid in self._incidents:
                self._incidents[eid]["open"] = False

        elif t == "alert_raise":
            aid = p.get("alertId", f"AL-{ev.get('id', 0)}")
            self._alerts[aid] = {
                "id": aid,
                "tick": tick,
                "severity": ev.get("severity", "low"),
                "message": p.get("message", ""),
                "acked": False,
            }
        elif t == "alert_ack":
            aid = p.get("alertId", eid)
            if aid in self._alerts:
                self._alerts[aid]["acked"] = True

        elif t == "mission_assigned" or (t == "system" and p.get("mission") and p.get("route")):
            route = p.get("route", [])
            mid = p.get("missionId", f"MSN-{tick}-{eid}")
            if eid in self._units:
                self._units[eid]["route"] = [list(wp) for wp in route]
                self._units[eid]["activeMissionId"] = mid
            for prs in self._personnel.values():
                if prs.get("unitId") == eid:
                    prs["activeMissionId"] = mid
                    if "missionHistory" not in prs:
                        prs["missionHistory"] = []
                    prs["missionHistory"].append(mid)

    def _world_snapshot(self) -> dict:
        """Return a serialisable world snapshot for DB persistence and APIs."""
        return {
            "runId": self.run_id,
            "seed": self.seed,
            "scenarioId": self.scenario_id,
            "tick": self.engine.tick,
            "simTime": self.engine.tick * 1000,
            "speed": self.speed,
            "status": "PAUSED" if self._paused else ("STOPPED" if self._stopped else "RUNNING"),
            "units": dict(self._units),
            "depots": dict(self._depots),
            "personnel": dict(self._personnel),
            "weather": dict(self._weather),
            "incidents": dict(self._incidents),
            "alerts": dict(self._alerts),
            "zones": self._zones,
        }

    # ------------------------------------------------------------------
    async def pause(self) -> None:
        self._paused = True
        self._flush_pending_samples()
        ev = self.engine._make_event("system", "low", "system", {"status": "PAUSED", "tick": self.engine.tick})
        d = ev.to_dict()
        self._log.append(d)
        await self._broadcast([ev])

    async def resume(self) -> None:
        self._paused = False
        ev = self.engine._make_event("system", "low", "system", {"status": "RUNNING", "tick": self.engine.tick})
        d = ev.to_dict()
        self._log.append(d)
        await self._broadcast([ev])

    async def stop(self) -> None:
        self._stopped = True
        if self._task:
            self._task.cancel()
        self._flush_pending_samples()
        ev = self.engine._make_event("system", "low", "system", {"status": "STOPPED", "tick": self.engine.tick})
        d = ev.to_dict()
        self._log.append(d)
        await self._broadcast([ev])

        # Persist final state
        try:
            db_mod.save_run({
                "id": self.run_id,
                "seed": self.seed,
                "scenarioId": self.scenario_id,
                "ticks": self.engine.tick,
                "events": len(self._log),
                "log": self._log,
            })
            db_mod.save_world_snapshot(self.run_id, self._world_snapshot())
        except Exception as exc:
            print(f"[SimSession] Final save notice: {exc}")

    async def set_speed(self, speed: float) -> None:
        self.speed = max(0.25, min(20.0, speed))
        ev = self.engine._make_event("system", "low", "system", {"speed": self.speed, "tick": self.engine.tick})
        d = ev.to_dict()
        self._log.append(d)
        await self._broadcast([ev])

    async def inject(self, partial: dict) -> list[dict]:
        events = self.engine.inject(partial)
        out_dicts = []
        for ev in events:
            d = ev.to_dict()
            self._log.append(d)
            self._apply(d)
            out_dicts.append(d)
        await self._broadcast(events)
        return out_dicts

    # ------------------------------------------------------------------
    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        # Send world snapshot and full in-memory log so late joiners see current state
        try:
            snapshot = self._world_snapshot()
            await ws.send_text(json.dumps({
                "type": "log_replay",
                "events": self._log,
                "snapshot": snapshot,
            }))
        except Exception:
            pass

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)

    async def _broadcast(self, events: list) -> None:
        if not events or not self._clients:
            return
        msg = json.dumps({"type": "events", "events": [e.to_dict() for e in events]})
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    # ------------------------------------------------------------------
    async def handle_client(self, ws: WebSocket) -> None:
        """Receive operator commands from a single client socket."""
        await self.connect(ws)
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                cmd = msg.get("cmd")
                if cmd == "pause":
                    await self.pause()
                elif cmd == "resume":
                    await self.resume()
                elif cmd == "stop":
                    await self.stop()
                elif cmd == "speed":
                    await self.set_speed(float(msg.get("value", 1)))
                elif cmd == "inject":
                    await self.inject(msg.get("event", {}))
        except WebSocketDisconnect:
            pass
        finally:
            self.disconnect(ws)
