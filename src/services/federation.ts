/**
 * Federated Command Architecture Service (Phase 4A)
 * Connects UI to multi-tier command hierarchy and cross-node synchronization.
 */

export interface FederationNode {
  id: string;
  name: string;
  tier: 'regional' | 'operational' | 'tactical';
  region: string;
  endpoint?: string;
  parent_id?: string | null;
  status: 'online' | 'degraded' | 'offline';
  heartbeat_at?: string;
  metadata?: Record<string, any>;
  directives_count?: number;
  intelligence_count?: number;
}

export interface Directive {
  id: string;
  origin_node_id: string;
  target_tier: string;
  title: string;
  content: string;
  requires_human_confirmation: boolean;
  status: 'staged' | 'confirmed' | 'executed' | 'cancelled';
  received_at?: string;
}

export interface IntelligenceItem {
  id: string;
  source_node: string;
  kind: string;
  payload: Record<string, any>;
  timestamp: string;
}

const API_BASE = '/api';

export async function listFederationNodes(tier?: string): Promise<FederationNode[]> {
  const url = tier ? `${API_BASE}/federation/nodes?tier=${encodeURIComponent(tier)}` : `${API_BASE}/federation/nodes`;
  const resp = await fetch(url);
  if (!resp.ok) {
    throw new Error(`Failed to list federation nodes: ${resp.status}`);
  }
  return resp.json();
}

export async function registerFederationNode(node: Partial<FederationNode>): Promise<FederationNode> {
  const resp = await fetch(`${API_BASE}/federation/nodes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(node),
  });
  if (!resp.ok) {
    throw new Error(`Failed to register federation node: ${resp.status}`);
  }
  return resp.json();
}

export async function broadcastDirective(
  originId: string,
  title: string,
  content: string,
  targetTier: string = 'operational'
): Promise<any[]> {
  const resp = await fetch(`${API_BASE}/federation/directives`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      origin_id: originId,
      title,
      content,
      target_tier: targetTier,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Directive broadcast failed: ${resp.status}`);
  }
  return resp.json();
}

export async function synchronizeIntelligence(
  sourceNodeId: string,
  kind: string,
  payload: Record<string, any>
): Promise<{ status: string; synced_nodes_count: number }> {
  const resp = await fetch(`${API_BASE}/federation/intelligence`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      source_node_id: sourceNodeId,
      kind,
      payload,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Intelligence sync failed: ${resp.status}`);
  }
  return resp.json();
}
