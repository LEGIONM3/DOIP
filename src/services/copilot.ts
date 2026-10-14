/**
 * Multi-Agent Mission Copilot Service (Phase 3E)
 * Interactive pair-planning engine with multi-perspective synthesis and human approval gate.
 */

export interface CopilotMessage {
  id?: string;
  role: 'user' | 'assistant' | 'tactical' | 'logistics' | 'risk' | 'contingency';
  content: string;
  timestamp?: string;
  metadata?: Record<string, any>;
}

export interface CopilotProposal {
  id: string;
  title: string;
  status: 'draft' | 'proposed' | 'approved' | 'rejected';
  requires_human_confirmation: boolean;
  objectives: string[];
  assets_required: string[];
  fuel_pnr_analysis: {
    estimated_fuel_burn: number;
    pnr_margin_pct: number;
    nearest_depot: string;
    safe_to_dispatch: boolean;
  };
  risk_envelope: {
    threat_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    incident_exposure: string[];
    risk_score: number;
  };
  contingencies: {
    weather_abort_corridor: string;
    emergency_rally_point: string;
    alternate_route: string;
  };
  consensus: {
    tactical_score: number;
    logistics_score: number;
    risk_score: number;
    overall_confidence: number;
  };
  created_at?: string;
}

export interface CopilotSession {
  id: string;
  mission_id?: string | null;
  title: string;
  messages: CopilotMessage[];
  proposals: CopilotProposal[];
  status: string;
  approved_by?: string | null;
  created_at?: string;
}

const API_BASE = '/api';

export async function sendCopilotChat(
  sessionId: string | null,
  message: string,
  context?: any
): Promise<{ session_id: string; reply: string; messages: CopilotMessage[]; session: CopilotSession }> {
  const resp = await fetch(`${API_BASE}/copilot/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      context,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Copilot chat request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function proposeMissionPackage(
  sessionId: string,
  prompt: string,
  context?: any
): Promise<{ proposal: CopilotProposal; session: CopilotSession }> {
  const resp = await fetch(`${API_BASE}/copilot/propose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      prompt,
      context,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Copilot propose request failed: ${resp.status}`);
  }
  return resp.json();
}

export async function approveCopilotProposal(
  sessionId: string,
  proposalId: string,
  user: string = 'Commander'
): Promise<{ success: boolean; session: CopilotSession }> {
  const resp = await fetch(`${API_BASE}/copilot/sessions/${encodeURIComponent(sessionId)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      proposal_id: proposalId,
      user,
    }),
  });
  if (!resp.ok) {
    throw new Error(`Copilot proposal approval failed: ${resp.status}`);
  }
  return resp.json();
}

export async function listCopilotSessions(): Promise<CopilotSession[]> {
  const resp = await fetch(`${API_BASE}/copilot/sessions`);
  if (!resp.ok) {
    throw new Error(`List copilot sessions failed: ${resp.status}`);
  }
  return resp.json();
}
