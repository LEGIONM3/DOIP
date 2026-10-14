/**
 * Replay Intelligence & After Action Review Service (Phase 3F)
 * Connects frontend to turning point detection, AI AAR reports, and What-If run comparisons.
 */

export interface TurningPoint {
  tick: number;
  kind: 'TRAJECTORY_DIVERGENCE' | 'THREAT_ESCALATION' | 'FUEL_CRITICAL' | 'COMMS_LOSS' | 'RESUPPLY_MISSED' | string;
  severity: 'CRITICAL' | 'WARNING' | 'INFO';
  description: string;
  significance_score: number;
  entity_id?: string;
  metadata?: Record<string, any>;
}

export interface AarSummary {
  run_id: string;
  executive_brief: string;
  objectives_summary: {
    achieved: string[];
    failed: string[];
  };
  resource_efficiency: {
    fuel_consumed_liters: number;
    fuel_budget_liters: number;
    efficiency_ratio: number;
    comms_uptime_pct: number;
  };
  key_decision_points: Array<{
    tick: number;
    event: string;
    impact: string;
    intervention_taken: boolean;
  }>;
  root_cause_attribution?: {
    primary_failure_cause: string;
    confidence: number;
    contributing_factors: string[];
  };
  recommendations: string[];
}

export interface RunComparisonResult {
  baseline_run_id: string;
  branch_run_id: string;
  kpi_deltas: {
    fuel_consumed_delta: number;
    casualty_delta: number;
    incidents_delta: number;
    duration_ticks_delta: number;
  };
  spatial_divergence: {
    max_divergence_km: number;
    avg_divergence_km: number;
    max_divergence_tick: number;
  };
  outcome_diff: {
    baseline_success: boolean;
    branch_success: boolean;
    narrative: string;
  };
}

export interface ReplayReport {
  id: string;
  run_id: string;
  comparison_run_id?: string | null;
  summary: string;
  turning_points: TurningPoint[];
  kpi_deltas: Record<string, any>;
  created_at?: string;
}

const API_BASE = '/api';

export async function detectTurningPoints(runId?: string, events?: any[]): Promise<TurningPoint[]> {
  const resp = await fetch(`${API_BASE}/replay/turning-points`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, events }),
  });
  if (!resp.ok) {
    throw new Error(`Detect turning points failed: ${resp.status}`);
  }
  const data = await resp.json();
  return data.turning_points || [];
}

export async function generateAarReport(runId: string, turningPoints?: TurningPoint[]): Promise<AarSummary> {
  const resp = await fetch(`${API_BASE}/replay/aar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, turning_points: turningPoints }),
  });
  if (!resp.ok) {
    throw new Error(`Generate AAR report failed: ${resp.status}`);
  }
  return resp.json();
}

export async function compareRuns(baselineRunId: string, branchRunId: string): Promise<RunComparisonResult> {
  const resp = await fetch(`${API_BASE}/replay/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      baseline_run_id: baselineRunId,
      branch_run_id: branchRunId,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Compare runs failed: ${resp.status}`);
  }
  return resp.json();
}

export async function listReplayReports(limit: number = 20): Promise<ReplayReport[]> {
  const resp = await fetch(`${API_BASE}/replay/reports?limit=${limit}`);
  if (!resp.ok) {
    throw new Error(`List replay reports failed: ${resp.status}`);
  }
  return resp.json();
}
