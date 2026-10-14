/**
 * Strategic Campaign & Swarm Planning Service (Phases 4C, 4D, 4H)
 */

export interface Campaign {
  id: string;
  title: string;
  theater_ids: string[];
  status: 'draft' | 'staged_for_approval' | 'active' | 'completed';
  objectives: string[];
  created_at?: string;
}

export interface CampaignBrief {
  campaign_id: string;
  title: string;
  brief_text: string;
  theaters: string[];
  objectives: string[];
  status: 'staged_for_approval' | 'approved';
  requires_human_confirmation: boolean;
  timestamp: string;
}

export interface StrategicReadinessReport {
  campaign_id: string;
  readiness_score: number;
  active_theaters: number;
  total_deployed_assets: number;
  reserve_fuel_liters: number;
  sustainment_posture: 'SUFFICIENT' | 'CONSTRAINED';
  theaters_status: any[];
  timestamp: string;
}

export interface StrategicRiskAssessment {
  campaign_id: string;
  composite_risk_level: 'LOW' | 'MODERATE' | 'ELEVATED' | 'HIGH' | 'CRITICAL';
  delay_probability: number;
  projected_pnr_breaches: number;
  rf_shadow_windows: number;
  cascading_failures: any[];
  strategic_summary: string;
  timestamp: string;
}

export interface StrategicInvestmentOutlook {
  campaign_id: string;
  recommended_investments: Array<{
    domain: string;
    item: string;
    impact: string;
    cost_index: number;
    roi_score: number;
  }>;
  capital_efficiency_score: number;
  readiness_delta_projected: string;
  requires_human_confirmation: boolean;
  timestamp: string;
}

export interface SwarmPlan {
  plan_id: string;
  theater_id: string;
  prompt: string;
  status: 'proposed' | 'approved';
  requires_human_confirmation: boolean;
  swarm_consensus: {
    commander: any;
    logistics: any;
    threat: any;
    weather: any;
    optimization: any;
    confidence_score: number;
  };
  tasks: Array<{
    task_id: string;
    name: string;
    assigned_units: string[];
    start_tick: number;
    end_tick: number;
  }>;
  executive_brief: string;
  created_at: string;
}

export interface CampaignComparison {
  comparison_id: string;
  campaign_a: any;
  campaign_b: any;
  kpi_deltas: {
    mission_completion_rate_delta_pct: number;
    fuel_consumption_delta_liters: number;
    incident_reduction_pct: number;
  };
  strategic_lessons_learned: string[];
  systemic_weaknesses: string[];
  resource_bottlenecks: Array<{
    asset: string;
    severity: string;
    detail: string;
  }>;
  executive_summary: string;
  timestamp: string;
}

const API_BASE = '/api';

export async function listCampaigns(): Promise<Campaign[]> {
  const resp = await fetch(`${API_BASE}/strategic/campaigns`);
  if (!resp.ok) {
    throw new Error(`Failed to list campaigns: ${resp.status}`);
  }
  return resp.json();
}

export async function createCampaign(campaign: {
  title: string;
  theater_ids: string[];
  objectives: string[];
}): Promise<Campaign> {
  const resp = await fetch(`${API_BASE}/strategic/campaigns`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(campaign),
  });
  if (!resp.ok) {
    throw new Error(`Failed to create campaign: ${resp.status}`);
  }
  return resp.json();
}

export async function generateCampaignBrief(campaignId: string): Promise<CampaignBrief> {
  const resp = await fetch(`${API_BASE}/strategic/campaigns/${encodeURIComponent(campaignId)}/brief`, {
    method: 'POST',
  });
  if (!resp.ok) {
    throw new Error(`Failed to generate brief: ${resp.status}`);
  }
  return resp.json();
}

export async function getCampaignReadiness(campaignId: string): Promise<StrategicReadinessReport> {
  const resp = await fetch(`${API_BASE}/strategic/campaigns/${encodeURIComponent(campaignId)}/readiness`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch readiness: ${resp.status}`);
  }
  return resp.json();
}

export async function getCampaignRisks(campaignId: string): Promise<StrategicRiskAssessment> {
  const resp = await fetch(`${API_BASE}/strategic/campaigns/${encodeURIComponent(campaignId)}/risks`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch risks: ${resp.status}`);
  }
  return resp.json();
}

export async function getCampaignInvestments(campaignId: string): Promise<StrategicInvestmentOutlook> {
  const resp = await fetch(`${API_BASE}/strategic/campaigns/${encodeURIComponent(campaignId)}/investments`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch investments: ${resp.status}`);
  }
  return resp.json();
}

export async function generateSwarmPlan(prompt: string, theaterId: string = 'THEATER-NORTH'): Promise<SwarmPlan> {
  const resp = await fetch(`${API_BASE}/swarm/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, theater_id: theaterId }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to generate swarm plan: ${resp.status}`);
  }
  return resp.json();
}

export async function compareCampaigns(campaignIdA: string, campaignIdB: string): Promise<CampaignComparison> {
  const resp = await fetch(`${API_BASE}/campaigns/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ campaign_id_a: campaignIdA, campaign_id_b: campaignIdB }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to compare campaigns: ${resp.status}`);
  }
  return resp.json();
}
