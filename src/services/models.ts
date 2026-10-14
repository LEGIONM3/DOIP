/**
 * Model Management & Dynamic Routing Service (Phase 5I)
 */

export interface ModelRecord {
  id: string;
  name: string;
  provider: string;
  model_type: 'llm' | 'vision' | 'embedding' | 'classifier';
  endpoint?: string;
  is_active: boolean;
  metadata?: Record<string, any>;
  created_at?: string;
}

export interface ModelRouteResult {
  selected_model: ModelRecord;
  routing_reason: string;
  routed_at: string;
}

export interface ModelHealth {
  model_id: string;
  name?: string;
  provider?: string;
  status: 'ONLINE' | 'OFFLINE' | 'NOT_FOUND';
  latency_ms: number;
  checked_at: string;
}

const API_BASE = '/api';

export async function listModels(provider?: string, modelType?: string): Promise<ModelRecord[]> {
  const params = new URLSearchParams();
  if (provider) params.set('provider', provider);
  if (modelType) params.set('model_type', modelType);
  const resp = await fetch(`${API_BASE}/models?${params.toString()}`);
  if (!resp.ok) throw new Error(`Failed to list models: ${resp.statusText}`);
  return resp.json();
}

export async function registerModel(model: Partial<ModelRecord>): Promise<ModelRecord> {
  const resp = await fetch(`${API_BASE}/models`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(model),
  });
  if (!resp.ok) throw new Error(`Failed to register model: ${resp.statusText}`);
  return resp.json();
}

export async function routeModelTask(
  taskType: string,
  priority: string = 'normal',
  requireLocal: boolean = false
): Promise<ModelRouteResult> {
  const resp = await fetch(`${API_BASE}/models/route`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_type: taskType, priority, require_local: requireLocal }),
  });
  if (!resp.ok) throw new Error(`Failed to route model task: ${resp.statusText}`);
  return resp.json();
}

export async function checkModelHealth(modelId: string): Promise<ModelHealth> {
  const resp = await fetch(`${API_BASE}/models/${modelId}/health`);
  if (!resp.ok) throw new Error(`Failed to check model health: ${resp.statusText}`);
  return resp.json();
}
