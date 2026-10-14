/**
 * Operational Knowledge Graph Service (Phase 3D)
 * Connects frontend visualization to NetworkX causal and dependency graph API.
 */

export interface GraphNode {
  id: string;
  label: string;
  type: 'MISSION' | 'UNIT' | 'ASSET' | 'INCIDENT' | 'ROUTE' | 'OPERATOR' | 'WEATHER' | 'DOCTRINE' | string;
  degree?: number;
  properties?: Record<string, any>;
}

export interface GraphLink {
  source: string;
  target: string;
  relation: 'participates_in' | 'assigned_to' | 'affected_by' | 'depends_on' | 'caused_by' | 'supports' | string;
  weight: number;
  properties?: Record<string, any>;
}

export interface SubgraphResponse {
  nodes: GraphNode[];
  links: GraphLink[];
  center_id?: string;
  depth?: number;
  total_nodes: number;
  total_links: number;
}

export interface CausalChainStep {
  step: number;
  node_id: string;
  label: string;
  entity_type: string;
  role: 'origin' | 'intermediate' | 'impact' | string;
  properties?: Record<string, any>;
}

export interface RootCauseResponse {
  incident_id: string;
  root_cause_id: string;
  root_cause_label: string;
  root_cause_type: string;
  attribution_score: number;
  confidence: number;
  causal_chain: CausalChainStep[];
  contributors: Array<{
    node_id: string;
    label: string;
    entity_type: string;
    attribution_score: number;
    depth: number;
    is_root_cause: boolean;
  }>;
  summary: string;
}

export interface SinglePointOfFailure {
  asset_id: string;
  label: string;
  dependent_count: number;
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM';
}

export interface DependencyResponse {
  entity_id: string;
  direct_count: number;
  transitive_count: number;
  dependencies: Array<{
    target_id: string;
    label: string;
    entity_type: string;
    relation_type: string;
    weight: number;
    depth: number;
  }>;
  single_points_of_failure: SinglePointOfFailure[];
}

const API_BASE = '/api';

export async function fetchSubgraph(centerId?: string, depth: number = 2): Promise<SubgraphResponse> {
  const query = new URLSearchParams();
  if (centerId) query.append('center_id', centerId);
  query.append('depth', depth.toString());

  const resp = await fetch(`${API_BASE}/graph/subgraph?${query.toString()}`);
  if (!resp.ok) {
    throw new Error(`Graph subgraph request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchRootCause(incidentId: string): Promise<RootCauseResponse> {
  const resp = await fetch(`${API_BASE}/graph/root-cause/${encodeURIComponent(incidentId)}`);
  if (!resp.ok) {
    throw new Error(`Graph root cause request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchDependencies(entityId: string): Promise<DependencyResponse> {
  const resp = await fetch(`${API_BASE}/graph/dependencies/${encodeURIComponent(entityId)}`);
  if (!resp.ok) {
    throw new Error(`Graph dependencies request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function seedDemoGraph(): Promise<{ success: boolean; nodes: number; edges: number }> {
  const resp = await fetch(`${API_BASE}/graph/seed`, { method: 'POST' });
  if (!resp.ok) {
    throw new Error(`Seed graph request failed: ${resp.status}`);
  }
  return resp.json();
}
