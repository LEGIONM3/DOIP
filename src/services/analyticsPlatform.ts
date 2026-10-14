/**
 * Operational Analytics, Forecasting Matrix, What-If & Observability Service (Phases 5C, 5D, 5E, 5F, 5G, 5H)
 */

export interface OperationalKPIs {
  time_window: string;
  theater: string;
  kpis: {
    mission_success_rate: number;
    fleet_readiness_pct: number;
    resource_utilization_pct: number;
    forecast_accuracy_pct: number;
    route_efficiency_index: number;
    active_missions_count: number;
    total_sorties_24h: number;
    avg_response_time_secs: number;
  };
  timestamp: string;
}

export interface AnalyticsDashboard {
  kpis: Record<string, any>;
  missions: Record<string, any>;
  resources: Record<string, any>;
  readiness: Record<string, any>;
  routing: Record<string, any>;
  generated_at: string;
}

export interface ForecastMatrix {
  id: string;
  horizon_hours: number;
  confidence: number;
  theaters: string[];
  matrix: Record<string, any>;
  risk_tensor: Record<string, any>;
  summary: string;
  created_at: string;
}

export interface WhatIfBatchResult {
  batch_id: string;
  total_scenarios: number;
  seed_base: number;
  comparison: Record<string, any>;
  ranked_top_10: Array<{
    scenario_seed: number;
    score: number;
    rank: number;
    parameters: Record<string, any>;
    metrics: Record<string, any>;
  }>;
  ranked_worst_5: Array<any>;
  created_at: string;
}

export interface KnowledgeSynthesis {
  synthesis_id: string;
  query: string;
  theater_id: string;
  narrative: string;
  doctrine_citations: Array<{
    doc_id: string;
    title: string;
    relevance_score: number;
    key_mandate: string;
  }>;
  graph_entities: Array<{ id: string; type: string; label: string }>;
  recommendations: string[];
  confidence_score: number;
  synthesized_at: string;
}

export interface ObservabilityMetrics {
  uptime_seconds: number;
  gauges: Record<string, number>;
  counters: Record<string, number>;
  latency_percentiles: Record<string, any>;
  timestamp: string;
}

export interface SystemHealth {
  status: string;
  uptime_seconds: number;
  subsystems: Record<string, string>;
  metrics: Record<string, any>;
}

const API_BASE = '/api';

export async function getOperationalKPIs(window: string = '24h', theater?: string): Promise<OperationalKPIs> {
  const params = new URLSearchParams({ window });
  if (theater) params.set('theater', theater);
  const resp = await fetch(`${API_BASE}/analytics/kpis?${params.toString()}`);
  if (!resp.ok) throw new Error(`Failed to get KPIs: ${resp.statusText}`);
  return resp.json();
}

export async function getAnalyticsDashboard(): Promise<AnalyticsDashboard> {
  const resp = await fetch(`${API_BASE}/analytics/dashboard`);
  if (!resp.ok) throw new Error(`Failed to get analytics dashboard: ${resp.statusText}`);
  return resp.json();
}

export async function generateForecastMatrix(
  theaters?: string[],
  horizonHours: number = 4.0,
  confidence: number = 0.95
): Promise<ForecastMatrix> {
  const resp = await fetch(`${API_BASE}/forecasting/matrix`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theaters, horizon_hours: horizonHours, confidence }),
  });
  if (!resp.ok) throw new Error(`Failed to generate forecast matrix: ${resp.statusText}`);
  return resp.json();
}

export async function listForecastMatrices(): Promise<ForecastMatrix[]> {
  const resp = await fetch(`${API_BASE}/forecasting/matrices`);
  if (!resp.ok) throw new Error(`Failed to list forecast matrices: ${resp.statusText}`);
  return resp.json();
}

export async function runMassiveWhatIf(
  nScenarios: number = 100,
  baseScenario?: Record<string, any>,
  seedBase: number = 42
): Promise<WhatIfBatchResult> {
  const resp = await fetch(`${API_BASE}/whatif/massive`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ n_scenarios: nScenarios, base_scenario: baseScenario, seed_base: seedBase }),
  });
  if (!resp.ok) throw new Error(`Failed to run massive what-if: ${resp.statusText}`);
  return resp.json();
}

export async function synthesizeKnowledge(
  query: string,
  theaterId?: string
): Promise<KnowledgeSynthesis> {
  const resp = await fetch(`${API_BASE}/knowledge/synthesize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, theater_id: theaterId }),
  });
  if (!resp.ok) throw new Error(`Failed to synthesize knowledge: ${resp.statusText}`);
  return resp.json();
}

export async function getObservabilityMetrics(): Promise<ObservabilityMetrics> {
  const resp = await fetch(`${API_BASE}/observability/metrics`);
  if (!resp.ok) throw new Error(`Failed to get observability metrics: ${resp.statusText}`);
  return resp.json();
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const resp = await fetch(`${API_BASE}/observability/health`);
  if (!resp.ok) throw new Error(`Failed to get system health: ${resp.statusText}`);
  return resp.json();
}
