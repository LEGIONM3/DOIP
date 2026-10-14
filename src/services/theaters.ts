/**
 * Multi-Theater & Multi-World Digital Twin Service (Phase 4B)
 */

export interface Theater {
  id: string;
  name: string;
  code: string;
  bounds: [number, number][];
  active_world_id: string;
  status: 'active' | 'standby' | 'archived';
  description?: string;
}

export interface SimulationWorld {
  id: string;
  theater_id: string;
  name: string;
  tick: number;
  status: 'running' | 'paused' | 'completed';
  state_snapshot?: {
    seed: number;
    units?: Record<string, any>;
    depots?: Record<string, any>;
    weather?: Record<string, any>;
    incidents?: Record<string, any>;
  };
}

export interface CrossTheaterAnalysis {
  timestamp: string;
  theaters_active: number;
  total_units_deployed: number;
  total_depot_fuel_liters: number;
  total_active_incidents: number;
  global_readiness_score: number;
  threat_density_index: number;
  theaters: Array<{
    theater_id: string;
    world_id: string;
    units_count: number;
    avg_unit_fuel_pct: number;
    depot_fuel_liters: number;
    active_incidents: number;
    readiness_score: number;
  }>;
}

const API_BASE = '/api';

export async function listTheaters(): Promise<Theater[]> {
  const resp = await fetch(`${API_BASE}/theaters`);
  if (!resp.ok) {
    throw new Error(`Failed to list theaters: ${resp.status}`);
  }
  return resp.json();
}

export async function getTheater(theaterId: string): Promise<Theater> {
  const resp = await fetch(`${API_BASE}/theaters/${encodeURIComponent(theaterId)}`);
  if (!resp.ok) {
    throw new Error(`Failed to get theater: ${resp.status}`);
  }
  return resp.json();
}

export async function listWorlds(theaterId?: string): Promise<SimulationWorld[]> {
  const url = theaterId ? `${API_BASE}/worlds?theater_id=${encodeURIComponent(theaterId)}` : `${API_BASE}/worlds`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to list worlds: ${resp.status}`);
  }
  return resp.json();
}

export async function getCrossTheaterAnalysis(): Promise<CrossTheaterAnalysis> {
  const resp = await fetch(`${API_BASE}/theaters/cross-analysis`);
  if (!resp.ok) {
    throw new Error(`Failed to get cross theater analysis: ${resp.status}`);
  }
  return resp.json();
}
