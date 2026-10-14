/**
 * Unified Agent Runtime Service (Phase 5A)
 */

export interface Agent {
  id: string;
  name: string;
  role: string;
  status: 'idle' | 'active' | 'busy' | 'offline';
  capabilities: string[];
  metadata?: Record<string, any>;
  updated_at?: string;
  created_at?: string;
}

export interface AgentTask {
  id: string;
  agent_id?: string;
  task_type: string;
  payload: Record<string, any>;
  result?: any;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  priority?: number;
  created_at: string;
  completed_at?: string;
}

export interface AgentRuntimeStatus {
  status: string;
  runtime_version: string;
  active_agents_count: number;
  agents: Agent[];
  recent_tasks_count: number;
  recent_tasks: AgentTask[];
}

const API_BASE = '/api';

export async function listAgents(status?: string, role?: string): Promise<Agent[]> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (role) params.set('role', role);
  const resp = await fetch(`${API_BASE}/agents?${params.toString()}`);
  if (!resp.ok) throw new Error(`Failed to list agents: ${resp.statusText}`);
  return resp.json();
}

export async function getAgent(agentId: string): Promise<Agent> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}`);
  if (!resp.ok) throw new Error(`Failed to get agent: ${resp.statusText}`);
  return resp.json();
}

export async function registerAgent(agent: Partial<Agent>): Promise<Agent> {
  const resp = await fetch(`${API_BASE}/agents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(agent),
  });
  if (!resp.ok) throw new Error(`Failed to register agent: ${resp.statusText}`);
  return resp.json();
}

export async function submitAgentTask(
  taskType: string,
  payload: Record<string, any> = {},
  agentId?: string
): Promise<AgentTask> {
  const resp = await fetch(`${API_BASE}/agents/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_type: taskType, payload, agent_id: agentId }),
  });
  if (!resp.ok) throw new Error(`Failed to submit task: ${resp.statusText}`);
  return resp.json();
}

export async function listAgentTasks(agentId?: string, status?: string): Promise<AgentTask[]> {
  const params = new URLSearchParams();
  if (agentId) params.set('agent_id', agentId);
  if (status) params.set('status', status);
  const resp = await fetch(`${API_BASE}/agents/tasks?${params.toString()}`);
  if (!resp.ok) throw new Error(`Failed to list agent tasks: ${resp.statusText}`);
  return resp.json();
}

export async function getAgentRuntimeStatus(): Promise<AgentRuntimeStatus> {
  const resp = await fetch(`${API_BASE}/agents/runtime/status`);
  if (!resp.ok) throw new Error(`Failed to get runtime status: ${resp.statusText}`);
  return resp.json();
}
