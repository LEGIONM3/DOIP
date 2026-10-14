/**
 * Persistent Long-Term Memory Service (Phase 5B)
 */

export interface AgentMemory {
  id: string;
  agent_id?: string;
  memory_type: 'semantic' | 'episodic' | 'operational';
  content: string;
  tags?: string[];
  importance: number;
  created_at: string;
}

export interface MemoryConsolidationResult {
  status: string;
  episodes_reviewed: number;
  consolidated_into_semantic: number;
  timestamp: string;
}

const API_BASE = '/api';

export async function rememberMemory(
  content: string,
  memoryType: 'semantic' | 'episodic' | 'operational' = 'semantic',
  tags: string[] = [],
  importance: number = 1.0,
  agentId?: string
): Promise<AgentMemory> {
  const resp = await fetch(`${API_BASE}/memory/remember`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      memory_type: memoryType,
      tags,
      importance,
      agent_id: agentId,
    }),
  });
  if (!resp.ok) throw new Error(`Failed to store memory: ${resp.statusText}`);
  return resp.json();
}

export async function retrieveMemories(
  query: string = '*',
  agentId?: string,
  memoryType?: string
): Promise<AgentMemory[]> {
  const params = new URLSearchParams();
  params.set('q', query);
  if (agentId) params.set('agent_id', agentId);
  if (memoryType) params.set('memory_type', memoryType);
  const resp = await fetch(`${API_BASE}/memory/retrieve?${params.toString()}`);
  if (!resp.ok) throw new Error(`Failed to retrieve memories: ${resp.statusText}`);
  return resp.json();
}

export async function consolidateMemories(): Promise<MemoryConsolidationResult> {
  const resp = await fetch(`${API_BASE}/memory/consolidate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!resp.ok) throw new Error(`Failed to consolidate memories: ${resp.statusText}`);
  return resp.json();
}

export async function getMemorySummary(agentId?: string, memoryType?: string): Promise<{ summary: string }> {
  const params = new URLSearchParams();
  if (agentId) params.set('agent_id', agentId);
  if (memoryType) params.set('memory_type', memoryType);
  const resp = await fetch(`${API_BASE}/memory/summary?${params.toString()}`);
  if (!resp.ok) throw new Error(`Failed to get memory summary: ${resp.statusText}`);
  return resp.json();
}
