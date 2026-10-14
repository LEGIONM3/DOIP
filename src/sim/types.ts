export type Severity = "low" | "medium" | "high" | "critical";

export type Role = "admin" | "planner" | "operator" | "viewer";

export type RunStatus = "IDLE" | "RUNNING" | "PAUSED" | "REPLAY" | "STOPPED";

export type UnitKind = "patrol" | "uav" | "convoy" | "depot";

export type EventType =
  | "world_init"
  | "unit_move"
  | "unit_status"
  | "comms_loss"
  | "comms_restore"
  | "incident_open"
  | "incident_close"
  | "alert_raise"
  | "alert_ack"
  | "resource_level"
  | "vitals"
  | "weather_spawn"
  | "weather_move"
  | "weather_clear"
  | "detection"
  | "mission_assigned"
  | "system";

export interface SimEvent {
  id: number;
  tick: number;
  simTime: number;
  type: EventType;
  severity: Severity;
  entityId: string;
  payload: Record<string, unknown>;
}

export interface Unit {
  id: string;
  callsign: string;
  kind: UnitKind;
  lat: number;
  lon: number;
  heading: number;
  speedKph: number;
  status: "active" | "slowed" | "halted" | "stale";
  fuel: number;
  battery: number;
  lastSeenTick: number;
  sector: string;
  route: Array<[number, number]>;
  activeMissionId?: string;
  personnelCount?: number;
}

export interface Incident {
  id: string;
  tick: number;
  severity: Severity;
  kind: string;
  lat: number;
  lon: number;
  entityId: string;
  open: boolean;
  closedTick?: number;
  sector?: string;
}

export interface AlertItem {
  id: string;
  tick: number;
  severity: Severity;
  message: string;
  entityId: string;
  acked: boolean;
  ackedTick?: number;
  ackedBy?: string;
  sector?: string;
}

export interface Depot {
  id: string;
  name: string;
  lat: number;
  lon: number;
  stock: { fuel: number; medkit: number; rations: number; battery: number };
  capacity: { fuel: number; medkit: number; rations: number; battery: number };
  sector?: string;
  facilityType?: "depot" | "airbase" | "forward_operating_base" | "naval_anchorage" | "medical_hub" | "comms_relay";
}

export interface Person {
  id: string;
  name: string;
  rank: string;
  unitId: string;
  heartRate: number;
  fatigue: number;
  history: number[];
  activeMissionId?: string;
  condition?: string;
  missionHistory?: string[];
  role?: string;
  sector?: string;
}

export interface WeatherCell {
  id: string;
  lat: number;
  lon: number;
  radiusM: number;
  intensity: number;
  kind: string;
  sector?: string;
}

export interface Zone {
  id: string;
  name: string;
  kind: "patrol" | "restricted" | "threat";
  points: Array<[number, number]>;
  sector?: string;
}

export type WorldMode = "baseline" | "simulation";

export type EnvironmentalProvenance =
  | "REAL_OBSERVATION"
  | "REAL_FORECAST"
  | "CACHED_REAL_DATA"
  | "SYNTHETIC_ENVIRONMENT";

export interface EnvironmentalStation {
  id: string;
  name: string;
  region: string;
  lat: number;
  lon: number;
  elevationM: number;
  temperatureC: number;
  humidityPct: number;
  cloudPct?: number;
  windSpeedKph: number;
  windDirectionDeg: number;
  precipitationMm: number;
  weatherCode: number;
  conditionLabel: string;
  conditionIcon?: string | null;
  severeAlert?: string | null;
  provenance: EnvironmentalProvenance;
  lastUpdated: string;
}

export interface EnvironmentalAlert {
  id: string;
  stationId?: string;
  region: string;
  severity: Severity;
  message: string;
  timestamp: string;
}

export interface EnvironmentalContext {
  subcontinent: string;
  center: [number, number];
  globalProvenance: EnvironmentalProvenance;
  stationsCount: number;
  stations: Record<string, EnvironmentalStation>;
  activeAlerts: EnvironmentalAlert[];
  lastSync: string;
}

export interface WorldState {
  seed: number;
  scenarioId: string;
  tick: number;
  simTime: number;
  units: Record<string, Unit>;
  incidents: Record<string, Incident>;
  alerts: Record<string, AlertItem>;
  depots: Record<string, Depot>;
  personnel: Record<string, Person>;
  weather: Record<string, WeatherCell>;
  zones: Zone[];
  worldMode?: WorldMode;
  branchId?: string;
  baselineRevisionId?: string;
  environmentalContext?: EnvironmentalContext;
}

/**
 * Backend seam. The mock tick engine implements this; a FastAPI WebSocket
 * feed can implement the same interface later with zero UI changes.
 */
export interface SimSource {
  start(opts: { seed: number; scenarioId: string }): void;
  pause(): void;
  resume(): void;
  stop(): void;
  setSpeed(speed: number): void;
  inject(events: Omit<SimEvent, "id" | "tick" | "simTime">[]): void;
  subscribe(cb: (events: SimEvent[]) => void): () => void;
}

export type WeatherFreshness = "fresh" | "stale" | "fallback";

export interface WeatherObservation {
  provider: string;
  location_query: string;
  resolved_name?: string | null;
  region?: string | null;
  country?: string | null;
  lat: number;
  lon: number;
  timezone_id?: string | null;
  provider_localtime?: string | null;
  provider_observation_time_epoch?: number | null;
  provider_observation_time_utc?: string | null;
  fetch_timestamp_utc: string;
  temp_c?: number | null;
  feelslike_c?: number | null;
  temp_f?: number | null;
  feelslike_f?: number | null;
  humidity_pct?: number | null;
  wind_kph?: number | null;
  wind_mph?: number | null;
  wind_degree?: number | null;
  wind_dir?: string | null;
  gust_kph?: number | null;
  precip_mm?: number | null;
  cloud_pct?: number | null;
  visibility_km?: number | null;
  pressure_mb?: number | null;
  uv_index?: number | null;
  is_day?: boolean | null;
  condition_text?: string | null;
  condition_icon?: string | null;
  condition_code?: number | null;
  provenance: EnvironmentalProvenance;
  freshness: WeatherFreshness;
  is_cached: boolean;
  cache_age_seconds: number;
  stale_warning?: string | null;
}

export interface WeatherDiagnostics {
  service: string;
  is_configured: boolean;
  cache_ttl_seconds: number;
  cache_total_entries: number;
  cache_fresh_entries: number;
  metrics: {
    total_requests: number;
    cache_hits: number;
    cache_misses: number;
    stale_serves: number;
    provider_errors: number;
    last_error: string | null;
    last_success_utc: string | null;
  };
}


