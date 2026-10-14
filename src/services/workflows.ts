/**
 * Operational Workflow Engine Service with Human-in-the-Loop Gate (Phase 5J)
 */

export interface WorkflowStep {
  step_id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'approved' | 'rejected' | 'completed' | 'blocked';
  approved_by?: string;
  rejection_reason?: string;
}

export interface WorkflowInstance {
  id: string;
  workflow_type: string;
  title: string;
  current_step: string;
  steps: WorkflowStep[];
  status: 'staged' | 'running' | 'approved' | 'completed' | 'rejected';
  requires_human_confirmation: boolean;
  approved_by?: string;
  created_at: string;
  updated_at?: string;
}

const API_BASE = '/api';

export async function listWorkflows(status?: string, workflowType?: string): Promise<WorkflowInstance[]> {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (workflowType) params.set('workflow_type', workflowType);
  const resp = await fetch(`${API_BASE}/workflows?${params.toString()}`);
  if (!resp.ok) throw new Error(`Failed to list workflows: ${resp.statusText}`);
  return resp.json();
}

export async function getWorkflow(workflowId: string): Promise<WorkflowInstance> {
  const resp = await fetch(`${API_BASE}/workflows/${workflowId}`);
  if (!resp.ok) throw new Error(`Failed to get workflow: ${resp.statusText}`);
  return resp.json();
}

export async function createWorkflow(
  workflowType: string,
  title: string,
  steps?: WorkflowStep[],
  requiresHumanConfirmation: boolean = true
): Promise<WorkflowInstance> {
  const resp = await fetch(`${API_BASE}/workflows`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      workflow_type: workflowType,
      title,
      steps,
      requires_human_confirmation: requiresHumanConfirmation,
    }),
  });
  if (!resp.ok) throw new Error(`Failed to create workflow: ${resp.statusText}`);
  return resp.json();
}

export async function approveWorkflow(workflowId: string, operatorId: string): Promise<WorkflowInstance> {
  const resp = await fetch(`${API_BASE}/workflows/${workflowId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId }),
  });
  if (!resp.ok) throw new Error(`Failed to approve workflow: ${resp.statusText}`);
  return resp.json();
}

export async function rejectWorkflow(
  workflowId: string,
  operatorId: string,
  reason: string = ''
): Promise<WorkflowInstance> {
  const resp = await fetch(`${API_BASE}/workflows/${workflowId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ operator_id: operatorId, reason }),
  });
  if (!resp.ok) throw new Error(`Failed to reject workflow: ${resp.statusText}`);
  return resp.json();
}

export async function advanceWorkflow(workflowId: string, nextStep: string): Promise<WorkflowInstance> {
  const resp = await fetch(`${API_BASE}/workflows/${workflowId}/advance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ next_step: nextStep }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || `Failed to advance workflow`);
  }
  return resp.json();
}
