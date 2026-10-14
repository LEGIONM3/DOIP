import { useCallback, useSyncExternalStore } from "react";
import { simSource as localSource } from "./engine";
import { WsSimSource } from "./wsSource";
import { api } from "@/lib/api";
import type { SimSource } from "./types";

// Active source: starts as local engine, silently upgraded to WS on login.
let activeSource: SimSource = localSource;
import { applyEvent, emptyWorld } from "./reducer";
import type {
  EnvironmentalContext,
  Role,
  RunStatus,
  SimEvent,
  WeatherObservation,
  WorldMode,
  WorldState,
} from "./types";

export interface RunRecord {
  id: string;
  seed: number;
  scenarioId: string;
  ticks: number;
  events: number;
  /** Event-log snapshot for this run — powers per-run replay, export and run-vs-run compare. */
  log: SimEvent[];
}

export interface SimStoreState {
  world: WorldState;
  events: SimEvent[];
  status: RunStatus;
  speed: number;
  seed: number;
  scenarioId: string;
  role: Role | null;
  userName: string;
  eventRate: number[];
  runs: RunRecord[];
  snapshot: { tick: number; world: WorldState; events: SimEvent[] } | null;
  worldMode: WorldMode;
  activeBranchId: string | null;
  baselineSnapshot: WorldState | null;
  environmentalContext: EnvironmentalContext | null;
  selectedLocationWeather: WeatherObservation | null;
  weatherLoading: boolean;
  weatherError: string | null;
  cloudOpacity: number;
  weatherLayerVisible: boolean;
  movementTrailsVisible: boolean;
  windVectorsVisible: boolean;
}

export const DEFAULT_INDIA_ENVIRONMENT: EnvironmentalContext = {
  subcontinent: "India",
  center: [22.5937, 78.9629],
  globalProvenance: "SYNTHETIC_ENVIRONMENT",
  stationsCount: 11,
  stations: {
    "STN-LEH": {
      id: "STN-LEH",
      name: "Leh High-Altitude Station",
      region: "Northern Sector (Ladakh)",
      lat: 34.1526,
      lon: 77.5771,
      elevationM: 3524,
      temperatureC: -4.2,
      humidityPct: 42,
      cloudPct: 65,
      windSpeedKph: 28.5,
      windDirectionDeg: 315,
      precipitationMm: 0,
      weatherCode: 71,
      conditionLabel: "Light Snow Flurries",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-SRINAGAR": {
      id: "STN-SRINAGAR",
      name: "Srinagar Valley Observatory",
      region: "Northern Sector (J&K)",
      lat: 34.0837,
      lon: 74.7973,
      elevationM: 1585,
      temperatureC: 8.5,
      humidityPct: 68,
      cloudPct: 85,
      windSpeedKph: 12,
      windDirectionDeg: 280,
      precipitationMm: 0.2,
      weatherCode: 3,
      conditionLabel: "Overcast",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-DELHI": {
      id: "STN-DELHI",
      name: "NCR Central Met Center",
      region: "Northern Sector (NCR)",
      lat: 28.6139,
      lon: 77.209,
      elevationM: 216,
      temperatureC: 26.4,
      humidityPct: 54,
      cloudPct: 25,
      windSpeedKph: 14.5,
      windDirectionDeg: 120,
      precipitationMm: 0,
      weatherCode: 1,
      conditionLabel: "Mainly Clear",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-JAISALMER": {
      id: "STN-JAISALMER",
      name: "Thar Desert Border Observatory",
      region: "Western Sector (Rajasthan)",
      lat: 26.9157,
      lon: 70.9083,
      elevationM: 225,
      temperatureC: 38.8,
      humidityPct: 22,
      cloudPct: 10,
      windSpeedKph: 24,
      windDirectionDeg: 240,
      precipitationMm: 0,
      weatherCode: 0,
      conditionLabel: "Clear / High Thermal",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-BHUJ": {
      id: "STN-BHUJ",
      name: "Kutch Littoral Station",
      region: "Western Sector (Gujarat)",
      lat: 23.242,
      lon: 69.6669,
      elevationM: 110,
      temperatureC: 32.1,
      humidityPct: 58,
      cloudPct: 15,
      windSpeedKph: 19.5,
      windDirectionDeg: 210,
      precipitationMm: 0,
      weatherCode: 1,
      conditionLabel: "Clear / Coastal Breeze",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-NAGPUR": {
      id: "STN-NAGPUR",
      name: "Central Transit Met Hub",
      region: "Central Sector (Maharashtra/MP)",
      lat: 21.1458,
      lon: 79.0882,
      elevationM: 310,
      temperatureC: 29.5,
      humidityPct: 48,
      cloudPct: 35,
      windSpeedKph: 11.2,
      windDirectionDeg: 90,
      precipitationMm: 0,
      weatherCode: 2,
      conditionLabel: "Partly Cloudy",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-PARADIP": {
      id: "STN-PARADIP",
      name: "Bay of Bengal Coastal Radar Station",
      region: "Eastern Sector (Odisha Coast)",
      lat: 20.316,
      lon: 86.611,
      elevationM: 4,
      temperatureC: 28.2,
      humidityPct: 82,
      cloudPct: 80,
      windSpeedKph: 38,
      windDirectionDeg: 160,
      precipitationMm: 4.5,
      weatherCode: 61,
      conditionLabel: "Coastal Rain Showers",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-KOLKATA": {
      id: "STN-KOLKATA",
      name: "Bengal Delta Met Station",
      region: "Eastern Sector (West Bengal)",
      lat: 22.5726,
      lon: 88.3639,
      elevationM: 9,
      temperatureC: 29.0,
      humidityPct: 76,
      cloudPct: 70,
      windSpeedKph: 16.5,
      windDirectionDeg: 170,
      precipitationMm: 1.2,
      weatherCode: 51,
      conditionLabel: "Light Drizzle",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-TEZPUR": {
      id: "STN-TEZPUR",
      name: "Brahmaputra Valley Station",
      region: "North-Eastern Sector (Assam/Arunachal)",
      lat: 26.6338,
      lon: 92.7926,
      elevationM: 48,
      temperatureC: 22.4,
      humidityPct: 88,
      cloudPct: 75,
      windSpeedKph: 8,
      windDirectionDeg: 60,
      precipitationMm: 2.8,
      weatherCode: 53,
      conditionLabel: "Valley Fog / Mist",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-BENGALURU": {
      id: "STN-BENGALURU",
      name: "Southern Plateau Headquarters",
      region: "Southern Sector (Karnataka/TN)",
      lat: 12.9716,
      lon: 77.5946,
      elevationM: 920,
      temperatureC: 24.6,
      humidityPct: 62,
      cloudPct: 40,
      windSpeedKph: 15,
      windDirectionDeg: 260,
      precipitationMm: 0,
      weatherCode: 2,
      conditionLabel: "Scattered Clouds",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
    "STN-PORTBLAIR": {
      id: "STN-PORTBLAIR",
      name: "Andaman Maritime Station",
      region: "Littoral & Island Sector (Andaman & Nicobar)",
      lat: 11.6234,
      lon: 92.7265,
      elevationM: 16,
      temperatureC: 27.8,
      humidityPct: 84,
      cloudPct: 85,
      windSpeedKph: 26,
      windDirectionDeg: 220,
      precipitationMm: 3,
      weatherCode: 63,
      conditionLabel: "Maritime Rain Squalls",
      provenance: "SYNTHETIC_ENVIRONMENT",
      lastUpdated: new Date().toISOString(),
    },
  },
  activeAlerts: [],
  lastSync: new Date().toISOString(),
};

function getInitialSession(): { role: Role | null; userName: string } {
  if (typeof window === "undefined") return { role: null, userName: "" };
  try {
    const raw = window.localStorage.getItem("doip.session");
    if (!raw) return { role: null, userName: "" };
    const s = JSON.parse(raw) as { role: Role; userName: string };
    if (s?.role) return { role: s.role, userName: s.userName || "" };
  } catch {
    /* ignore parse error */
  }
  return { role: null, userName: "" };
}

const savedSession = getInitialSession();

const initial: SimStoreState = {
  world: emptyWorld(),
  events: [],
  status: "IDLE",
  speed: 1,
  seed: 20260101,
  scenarioId: "SC-1",
  role: savedSession.role,
  userName: savedSession.userName,
  eventRate: [],
  runs: [],
  snapshot: null,
  worldMode: "baseline",
  activeBranchId: null,
  baselineSnapshot: null,
  environmentalContext: DEFAULT_INDIA_ENVIRONMENT,
  selectedLocationWeather: null,
  weatherLoading: false,
  weatherError: null,
  cloudOpacity: 0.75,
  weatherLayerVisible: true,
  movementTrailsVisible: true,
  windVectorsVisible: true,
};

class SimStore {
  private state: SimStoreState = initial;
  private listeners = new Set<() => void>();
  private lastTick = 0;
  private tickCount = 0;
  private started = false;
  private runCounter = 0;

  getState = () => this.state;

  subscribe = (cb: () => void) => {
    this.listeners.add(cb);
    if (!this.started) this.bind();
    return () => this.listeners.delete(cb);
  };

  private set(patch: Partial<SimStoreState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((l) => l());
  }

  private bind() {
    this.started = true;
    activeSource.subscribe((batch) => this.ingest(batch));
  }

  /** Try to upgrade to the backend WS engine; fall back silently if offline. */
  private async tryUpgradeToWs() {
    if (typeof window === "undefined") return;
    const backendUp = await api.available();
    if (!backendUp) return; // backend absent — keep local engine
    const wsSource = new WsSimSource();
    wsSource.setOnFail(() => {
      // WS failed after token — stay on local engine, no UI disruption
    });
    activeSource = wsSource;
    // Rebind listener to the new source
    wsSource.subscribe((batch) => this.ingest(batch));
  }

  /** Single adapter seam: swap simSource for a WebSocket feed, this stays. */
  ingest(batch: SimEvent[]) {
    let world = this.state.world;
    for (const e of batch) world = applyEvent(world, e);
    const events = [...this.state.events, ...batch].slice(-20000);
    const tick = batch[batch.length - 1]?.tick ?? this.state.world.tick;
    let rate = this.state.eventRate;
    if (tick !== this.lastTick) {
      rate = [...rate, this.tickCount].slice(-60);
      this.tickCount = batch.length;
      this.lastTick = tick;
    } else {
      this.tickCount += batch.length;
    }
    const statusEvent = batch.find(
      (e) => e.type === "system" && (e.payload as { status?: string }).status,
    );
    const status = statusEvent
      ? ((statusEvent.payload as { status: string }).status as RunStatus)
      : this.state.status;
    this.set({ world, events, eventRate: rate, status });
  }

  /** Restores the demo session after a page reload (client-only). */
  hydrateSession() {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem("doip.session");
      if (!raw) return;
      const s = JSON.parse(raw) as { role: Role; userName: string };
      if (s?.role) {
        if (!this.state.role) {
          this.set({ role: s.role, userName: s.userName });
        }
        void (async () => {
          await api.login(s.role, s.userName);
          await this.tryUpgradeToWs();
          await this.hydrateRuns();
        })();
        if (this.state.status === "IDLE") this.startRun(this.state.seed, this.state.scenarioId);
      }
    } catch {
      /* ignore corrupt session */
    }
  }

  login(role: Role, userName: string) {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("doip.session", JSON.stringify({ role, userName }));
    }
    this.set({ role, userName });
    // MVP backend: get token, upgrade to WS engine, hydrate runs. All fail-soft.
    void (async () => {
      await api.login(role, userName);
      await this.tryUpgradeToWs();
      await this.hydrateRuns();
    })();
    if (this.state.status === "IDLE") this.startRun(this.state.seed, this.state.scenarioId);
  }

  logout() {
    if (typeof window !== "undefined") window.localStorage.removeItem("doip.session");
    this.set({ role: null, userName: "" });
  }

  /** Pulls previously persisted runs from the MVP backend (no-op offline). */
  private async hydrateRuns() {
    const serverRuns = await api.listRuns();
    if (!serverRuns?.length) return;
    const known = new Set(this.state.runs.map((r) => r.id));
    const merged = [...serverRuns.filter((r) => !known.has(r.id)), ...this.state.runs].slice(-8);
    for (const r of merged) {
      const n = Number(r.id.replace("RUN-", ""));
      if (Number.isFinite(n) && n > this.runCounter) this.runCounter = n;
    }
    this.set({ runs: merged });
  }

  /** Archives the in-flight run (if any) into the run list. */
  private recordRun(): RunRecord[] {
    const { seed, scenarioId, world, events } = this.state;
    if (!world.tick || !events.length) return this.state.runs;
    this.runCounter += 1;
    const record: RunRecord = {
      id: `RUN-${this.runCounter}`,
      seed,
      scenarioId,
      ticks: world.tick,
      events: events.length,
      log: events,
    };
    // MVP backend: persist fire-and-forget; the UI never blocks on the server.
    void api.saveRun(record);
    return [...this.state.runs, record].slice(-8);
  }

  startRun(seed: number, scenarioId: string) {
    const runs =
      this.state.status === "RUNNING" || this.state.status === "PAUSED"
        ? this.recordRun()
        : this.state.runs;
    this.lastTick = 0;
    this.tickCount = 0;
    this.set({
      events: [],
      world: emptyWorld(),
      eventRate: [],
      seed,
      scenarioId,
      status: "RUNNING",
      runs,
    });
    activeSource.start({ seed, scenarioId });
  }

  /** Re-runs a recorded run with the same scenario and seed — reproduces it event-for-event. */
  cloneRun(run: RunRecord) {
    this.startRun(run.seed, run.scenarioId);
  }

  pause() {
    activeSource.pause();
    this.set({ status: "PAUSED" });
  }

  resume() {
    activeSource.resume();
    this.set({ status: "RUNNING" });
  }

  stop() {
    activeSource.stop();
    this.set({ status: "STOPPED", runs: this.recordRun() });
  }

  setSpeed(speed: number) {
    activeSource.setSpeed(speed);
    this.set({ speed });
  }

  setStatus(status: RunStatus) {
    this.set({ status });
  }

  ackAlert(alertId: string, by: string) {
    activeSource.inject([
      { type: "alert_ack", severity: "low", entityId: alertId, payload: { alertId, by } },
    ]);
  }

  closeIncident(id: string) {
    activeSource.inject([{ type: "incident_close", severity: "low", entityId: id, payload: {} }]);
  }

  launchMission(opts: { unitId: string; waypoints: Array<[number, number]>; by: string }) {
    activeSource.inject([
      {
        type: "system",
        severity: "medium",
        entityId: opts.unitId,
        payload: { mission: true, route: opts.waypoints, by: opts.by },
      },
    ]);
  }

  injectRaw(events: Omit<SimEvent, "id" | "tick" | "simTime">[]) {
    activeSource.inject(events);
  }

  saveSnapshot() {
    if (!this.state.world.tick) return;
    this.set({
      snapshot: {
        tick: this.state.world.tick,
        world: JSON.parse(JSON.stringify(this.state.world)) as WorldState,
        events: [...this.state.events],
      },
    });
  }

  restoreSnapshot() {
    if (!this.state.snapshot) return;
    const { world, events } = this.state.snapshot;
    this.set({
      world: JSON.parse(JSON.stringify(world)) as WorldState,
      events: [...events],
    });
  }

  switchWorldMode(mode: WorldMode) {
    if (mode === this.state.worldMode) return;
    if (mode === "simulation") {
      const baselineSnapshot = JSON.parse(JSON.stringify(this.state.world)) as WorldState;
      const branchId = "BRANCH-" + Math.random().toString(36).substring(2, 8).toUpperCase();
      this.set({
        worldMode: "simulation",
        baselineSnapshot,
        activeBranchId: branchId,
      });
      if (this.state.scenarioId === "IN-BASE-LIVE" || this.state.scenarioId.startsWith("SC-")) {
        this.startRun(20261014, "IN-SC-CYCLONE");
      }
    } else {
      this.set({
        worldMode: "baseline",
        activeBranchId: null,
      });
      if (this.state.baselineSnapshot && this.state.baselineSnapshot.scenarioId === "IN-BASE-LIVE") {
        this.set({ world: JSON.parse(JSON.stringify(this.state.baselineSnapshot)) as WorldState });
      } else {
        this.startRun(20261014, "IN-BASE-LIVE");
      }
    }
  }

  forkSimulation(scenarioId: string, seed: number = 20261014) {
    const branchId = "BRANCH-" + Math.random().toString(36).substring(2, 8).toUpperCase();
    const baselineSnapshot =
      this.state.worldMode === "baseline"
        ? (JSON.parse(JSON.stringify(this.state.world)) as WorldState)
        : this.state.baselineSnapshot;

    this.set({
      worldMode: "simulation",
      activeBranchId: branchId,
      baselineSnapshot,
    });
    this.startRun(seed, scenarioId);
  }

  resetToBaseline() {
    this.set({
      worldMode: "baseline",
      activeBranchId: null,
    });
    if (this.state.baselineSnapshot && this.state.baselineSnapshot.scenarioId === "IN-BASE-LIVE") {
      this.set({ world: JSON.parse(JSON.stringify(this.state.baselineSnapshot)) as WorldState });
    } else {
      this.startRun(20261014, "IN-BASE-LIVE");
    }
  }

  async fetchEnvironmentalContext(): Promise<EnvironmentalContext> {
    try {
      const res = await fetch("/api/environment/context");
      if (res.ok) {
        const data = (await res.json()) as EnvironmentalContext;
        this.set({ environmentalContext: data });
        return data;
      }
    } catch {
      /* offline fallback */
    }
    this.set({ environmentalContext: DEFAULT_INDIA_ENVIRONMENT });
    return DEFAULT_INDIA_ENVIRONMENT;
  }

  async fetchWeatherForLocation(
    lat: number,
    lon: number,
    refresh = false,
  ): Promise<WeatherObservation | null> {
    this.set({ weatherLoading: true, weatherError: null });
    try {
      const url = `/api/weather/current?lat=${lat}&lon=${lon}${refresh ? "&refresh=true" : ""}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        if (data.ok && data.observation) {
          const obs = data.observation as WeatherObservation;
          this.set({ selectedLocationWeather: obs, weatherLoading: false });
          return obs;
        } else {
          this.set({
            weatherError: data.detail || data.message || "Failed to load weather observation",
            weatherLoading: false,
          });
        }
      } else {
        this.set({ weatherError: `HTTP ${res.status}`, weatherLoading: false });
      }
    } catch (err) {
      this.set({ weatherError: String(err), weatherLoading: false });
    }
    return null;
  }

  setCloudOpacity(cloudOpacity: number) {
    this.set({ cloudOpacity: Math.max(0, Math.min(1, cloudOpacity)) });
  }

  setWeatherLayerVisible(weatherLayerVisible: boolean) {
    this.set({ weatherLayerVisible });
  }

  setMovementTrailsVisible(movementTrailsVisible: boolean) {
    this.set({ movementTrailsVisible });
  }

  setWindVectorsVisible(windVectorsVisible: boolean) {
    this.set({ windVectorsVisible });
  }

  clearSelectedLocationWeather() {
    this.set({ selectedLocationWeather: null, weatherError: null });
  }
}

export const simStore = new SimStore();

export function useSim<T>(selector: (s: SimStoreState) => T): T {
  const getSnapshot = useCallback(() => selector(simStore.getState()), [selector]);
  return useSyncExternalStore(simStore.subscribe, getSnapshot, getSnapshot);
}

export const useSimState = () => useSim((s) => s);
