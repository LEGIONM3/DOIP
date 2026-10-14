/**
 * Red Team Adversarial Planner Service Client (Phase 2E).
 *
 * Implements:
 * - Automated tactical vulnerability discovery across routes, postures, and weather.
 * - Synthesis of stress-testing adversarial injects strictly mapped to whitelisted DSL actions.
 * - Human-in-the-loop approval gate preventing autonomous inject activation.
 */

export interface ProposedInject {
  id: string;
  scenario_id: string;
  title: string;
  action: "spawn_weather" | "create_incident" | "modify_speed" | "unit_report" | "raise_alert";
  params: Record<string, any>;
  trigger_tick: number;
  risk_rating: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  vulnerability_targeted: string;
  vulnerability_description: string;
  status: "staged" | "approved" | "executed" | "rejected";
  approved_by: string | null;
  dsl_valid: boolean;
  dsl_validation_message: string;
  created_at: string;
}

export interface RedTeamScenario {
  id: string;
  mission_id?: string | null;
  title: string;
  risk_rating: "CRITICAL" | "HIGH" | "MEDIUM";
  vulnerability_summary: string;
  injects: ProposedInject[];
  status: "staged" | "approved" | "executed" | "rejected";
  approved_by: string | null;
  created_at: string;
}

export interface RedTeamGenerateRequest {
  mission_id?: string | null | undefined;
  mission_data?: Record<string, any>;
  route_data?: Record<string, any>;
  world_state?: Record<string, any>;
}

const BASE_URL = (
  (import.meta.env?.["VITE_DOIP_API_URL"] as string | undefined) ?? "http://localhost:8000"
).replace(/\/$/, "");

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("doip.token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function generateRedTeamScenario(
  req: RedTeamGenerateRequest = {},
  timeoutMs = 12000,
): Promise<RedTeamScenario> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE_URL}/api/redteam/generate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
      body: JSON.stringify(req),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (res.ok) {
      return (await res.json()) as RedTeamScenario;
    }
  } catch {
    clearTimeout(timer);
  }

  // Deterministic client fallback
  return buildOfflineRedTeamFallback(req);
}

export async function validateRedTeamInject(
  action: string,
  params: Record<string, any>,
  triggerTick = 10,
): Promise<{ valid: boolean; message: string }> {
  try {
    const res = await fetch(`${BASE_URL}/api/redteam/validate-inject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
      body: JSON.stringify({ action, params, trigger_tick: triggerTick }),
    });

    if (res.ok) {
      return await res.json();
    }
  } catch {}

  const WHITELIST = ["spawn_weather", "create_incident", "unit_report", "modify_speed", "raise_alert"];
  const valid = WHITELIST.includes(action);
  return {
    valid,
    message: valid ? "Valid DSL action" : `Action '${action}' not in whitelist`,
  };
}

export async function approveRedTeamInject(
  scenarioId: string,
  injectId: string,
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/redteam/injects/${injectId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify({ scenario_id: scenarioId }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Approval failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return await res.json();
}

export async function listRedTeamScenarios(): Promise<RedTeamScenario[]> {
  try {
    const res = await fetch(`${BASE_URL}/api/redteam/scenarios`, {
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      return data.scenarios || [];
    }
  } catch {}
  return [];
}

function buildOfflineRedTeamFallback(req: RedTeamGenerateRequest): RedTeamScenario {
  const id = `RED-OFFLINE-${Date.now() % 10000}`;
  return {
    id,
    mission_id: req.mission_id ?? null,
    title: "Offline Stress Plan: Chokepoint & Jamming Injects",
    risk_rating: "HIGH",
    vulnerability_summary: "Detected 2 vulnerabilities: Mid-route chokepoint exposure and degraded sensor coverage.",
    injects: [
      {
        id: `INJ-${id}-01`,
        scenario_id: id,
        title: "Adversarial Stress: Corridor Chokepoint Exposure",
        action: "create_incident",
        params: {
          incident_id: "INC-RED-01",
          type: "simulated_hostile_ambush",
          lat: 34.05,
          lon: 71.55,
          severity: "HIGH",
          description: "Simulated adversarial obstacle exploiting narrow valley route.",
        },
        trigger_tick: 20,
        risk_rating: "HIGH",
        vulnerability_targeted: "VULN-ROUTE-CHOKE",
        vulnerability_description: "Narrow corridor with low lateral maneuverability.",
        status: "staged",
        approved_by: null,
        dsl_valid: true,
        dsl_validation_message: "Valid DSL action",
        created_at: new Date().toISOString(),
      },
      {
        id: `INJ-${id}-02`,
        scenario_id: id,
        title: "Adversarial Stress: Severe Environmental Impedance",
        action: "spawn_weather",
        params: {
          type: "STORM",
          intensity: 0.8,
          duration_ticks: 40,
          description: "High crosswind squall cell degrading UAV optical tracking.",
        },
        trigger_tick: 40,
        risk_rating: "MEDIUM",
        vulnerability_targeted: "VULN-WEATHER-BLIND",
        vulnerability_description: "Cloud cover creating ISR gaps.",
        status: "staged",
        approved_by: null,
        dsl_valid: true,
        dsl_validation_message: "Valid DSL action",
        created_at: new Date().toISOString(),
      },
    ],
    status: "staged",
    approved_by: null,
    created_at: new Date().toISOString(),
  };
}
