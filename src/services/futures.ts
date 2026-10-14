/**
 * Autonomous Simulation Branching & Future Generator Service (Phase 4G)
 */

export interface FutureBranch {
  id?: string;
  branch_id?: string;
  baseline_world_id?: string;
  branch_seed: number;
  ticks: number;
  score: number;
  outcome_rank?: number;
  risk_band?: 'P10' | 'P50' | 'P90' | 'WORST';
  mission_success?: boolean;
  fuel_delta_liters?: number;
  incidents_count?: number;
  outcome?: any;
}

export interface FutureBatchResult {
  batch_id: string;
  baseline_world_id: string;
  branches_count: number;
  ticks: number;
  risk_bands: {
    P10_optimistic: { score: number; branch_id: string; incidents: number };
    P50_median: { score: number; branch_id: string; incidents: number };
    P90_conservative: { score: number; branch_id: string; incidents: number };
    WORST_case: { score: number; branch_id: string; incidents: number };
  };
  top_branches: FutureBranch[];
  worst_branch: FutureBranch;
  summary: string;
}

const API_BASE = '/api';

export async function generateAlternativeFutures(
  baselineWorldId: string = 'WLD-NORTH-01',
  count: number = 10,
  ticks: number = 120
): Promise<FutureBatchResult> {
  const resp = await fetch(`${API_BASE}/futures/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      baseline_world_id: baselineWorldId,
      count,
      ticks,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to generate futures: ${resp.status}`);
  }
  return resp.json();
}

export async function listFutures(
  baselineWorldId?: string,
  limit: number = 50
): Promise<FutureBranch[]> {
  const url = baselineWorldId
    ? `${API_BASE}/futures?baseline_world_id=${encodeURIComponent(baselineWorldId)}&limit=${limit}`
    : `${API_BASE}/futures?limit=${limit}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to list futures: ${resp.status}`);
  }
  return resp.json();
}
