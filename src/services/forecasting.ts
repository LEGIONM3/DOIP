/**
 * Digital Twin Forecasting Engine Service (Phase 3C)
 * Connects frontend console to backend lookahead projections.
 */

export interface FuelUnitTimeline {
  initial_fuel: number;
  final_fuel: number;
  depletion_tick: number | null;
  pnr_breach_tick: number | null;
  pnr_breached: boolean;
  min_pnr_margin_pct: number;
  nearest_depot: {
    id: string;
    name: string;
    distance_km: number;
    fuel_to_reach_pct: number;
  };
}

export interface CommsDegradationWindow {
  unit_id: string;
  start_tick: number;
  end_tick: number;
  duration_ticks: number;
  primary_mast: string;
  min_rssi_dbm: number;
  severity: 'WARNING' | 'CRITICAL';
}

export interface ThreatPrediction {
  unit_id: string;
  incident_id: string;
  intercept_tick: number;
  closest_approach_km: number;
  intersection_probability: number;
  threat_severity: string;
}

export interface MissionArrivalPercentiles {
  route_distance_km: number;
  base_speed_kph: number;
  p10_ticks: number;
  p50_ticks: number;
  p90_ticks: number;
  p10_eta_minutes: number;
  p50_eta_minutes: number;
  p90_eta_minutes: number;
  weather_impact_factor: number;
  terrain_friction_factor: number;
}

export interface ExecutiveSummary {
  risk_level: 'NOMINAL' | 'ELEVATED' | 'HIGH' | 'CRITICAL';
  composite_risk_score: number;
  headline: string;
  key_findings: string[];
  recommended_actions: string[];
}

export interface ForecastPredictions {
  fuel_exhaustion: {
    units: Record<string, FuelUnitTimeline>;
    pnr_breaches_detected: number;
  };
  comms_degradation: {
    degradation_windows: CommsDegradationWindow[];
    comms_availability_pct: Record<string, number>;
  };
  threat_escalation: {
    predicted_contacts: ThreatPrediction[];
    escalation_trend_score: number;
  };
  mission_arrival: {
    units: Record<string, MissionArrivalPercentiles>;
  };
  executive_summary: ExecutiveSummary;
}

export interface ForecastTrajectoryPoint {
  tick: number;
  lat: number;
  lon: number;
  heading: number;
  fuel: number;
  battery: number;
  inWeather: boolean;
  effectiveSpeedKph: number;
}

export interface ForecastWeatherSnapshot {
  tick: number;
  cell?: any;
  cells: any[];
}

export interface ForecastIncidentSnapshot {
  id: string;
  tick: number;
  lat: number;
  lon: number;
  severity: string;
  kind: string;
}

export interface ForecastResult {
  id: string;
  scenario_id: string;
  horizon_hours: number;
  confidence: number;
  ticks: number;
  predictions: ForecastPredictions & {
    weather_timeline?: ForecastWeatherSnapshot[];
    incident_history?: ForecastIncidentSnapshot[];
    current_conditions?: any;
    route_impacts?: Record<string, any>;
    provenance?: any;
  };
  forecast_intelligence?: any;
  trajectories?: Record<string, ForecastTrajectoryPoint[]>;
  weather_timeline?: ForecastWeatherSnapshot[];
  incident_history?: ForecastIncidentSnapshot[];
  current_conditions?: any;
  route_impacts?: Record<string, any>;
  provenance?: any;
  masts?: any[];
  summary?: string;
  created_at?: string;
}

const API_BASE = '/api';

export async function fetchForecast(
  horizonHours: number = 2.0,
  confidence: number = 0.95,
  scenarioId: string = 'SC-DEFAULT',
  worldState?: any
): Promise<ForecastResult> {
  const resp = await fetch(`${API_BASE}/forecast`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      horizon_hours: horizonHours,
      confidence,
      scenario_id: scenarioId,
      world_state: worldState,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Forecast request failed with status: ${resp.status}`);
  }
  return resp.json();
}

export async function listForecastHistory(limit: number = 10): Promise<ForecastResult[]> {
  const resp = await fetch(`${API_BASE}/forecast/history?limit=${limit}`);
  if (!resp.ok) {
    throw new Error(`Forecast history request failed with status: ${resp.status}`);
  }
  return resp.json();
}
