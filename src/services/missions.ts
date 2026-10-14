/**
 * Mission Planning Engine Client (Phase 2B).
 *
 * Provides typed interface for Mission lifecycle management:
 * Draft -> Review -> Approved -> Executing -> Completed / Cancelled.
 *
 * Safety Boundary:
 *  - AI can propose drafts, but CANNOT approve or execute missions.
 *  - Transition to approved or executing strictly requires human operator identity.
 */

export type MissionStatus =
  | "draft"
  | "review"
  | "approved"
  | "executing"
  | "completed"
  | "cancelled";

export interface MissionTask {
  id?: number;
  sequence: number;
  title: string;
  task_type: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  duration_s: number;
  start_tick?: number;
  end_tick?: number;
}

export interface MissionWaypoint {
  id?: number;
  sequence: number;
  name: string;
  lat: number;
  lon: number;
  alt_m: number;
}

export interface Mission {
  id: string;
  name: string;
  description: string;
  status: MissionStatus;
  priority: string;
  author: string;
  assigned_unit_ids: string[];
  waypoints: MissionWaypoint[];
  tasks: MissionTask[];
  estimated_duration_s: number;
  fuel_required_l: number;
  risk_score: number;
  is_ai_generated?: boolean;
  created_at: string;
  updated_at: string;
}

export interface MissionCreateRequest {
  name: string;
  description?: string;
  waypoints?: MissionWaypoint[];
  tasks?: Partial<MissionTask>[];
  assigned_assets?: string[];
  priority?: "routine" | "medium" | "high" | "critical";
  constraints?: Record<string, any>;
}

const BASE_URL = (
  (import.meta.env?.["VITE_DOIP_API_URL"] as string | undefined) ?? "http://localhost:8000"
).replace(/\/$/, "");

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("doip.token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function createMission(req: MissionCreateRequest): Promise<Mission> {
  const res = await fetch(`${BASE_URL}/api/missions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(req),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Create mission failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return (await res.json()) as Mission;
}

export async function listMissions(limit = 50, status?: string): Promise<Mission[]> {
  try {
    const url = new URL(`${BASE_URL}/api/missions`);
    url.searchParams.set("limit", String(limit));
    if (status) url.searchParams.set("status", status);

    const res = await fetch(url.toString(), { headers: getAuthHeader() });
    if (res.ok) {
      const data = await res.json();
      return data.missions || [];
    }
  } catch {
    // Fail-soft
  }
  return [];
}

export async function getMission(missionId: string): Promise<Mission | null> {
  try {
    const res = await fetch(`${BASE_URL}/api/missions/${missionId}`, {
      headers: getAuthHeader(),
    });
    if (res.ok) {
      return (await res.json()) as Mission;
    }
  } catch {
    // Fail-soft
  }
  return null;
}

export async function transitionMission(
  missionId: string,
  targetStatus: MissionStatus,
  notes = "",
): Promise<Mission> {
  const res = await fetch(`${BASE_URL}/api/missions/${missionId}/transition`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify({ target_status: targetStatus, notes }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Transition failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return (await res.json()) as Mission;
}

export async function generateAiMissionDraft(
  prompt: string,
  constraints?: Record<string, any>,
): Promise<Mission> {
  const res = await fetch(`${BASE_URL}/api/missions/ai-draft`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify({ prompt, constraints }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "AI draft generation failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return (await res.json()) as Mission;
}
