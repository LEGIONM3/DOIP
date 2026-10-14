/**
 * Tactical Route Planning Service Client (Phase 2A).
 *
 * Provides typed integration with /api/routes endpoints.
 * Supports multi-layer cost routing strategies: shortest, safest, fuel_efficient, fastest.
 */

export type RouteStrategy = "shortest" | "safest" | "fuel_efficient" | "fastest";

export interface RouteWaypoint {
  lat: number;
  lon: number;
}

export interface RouteSegment {
  from_coord: [number, number];
  to_coord: [number, number];
  distance_km: number;
  threat_cost: number;
  weather_cost: number;
  terrain_cost: number;
  step_cost: number;
}

export interface RouteCalculateRequest {
  start: [number, number];
  destination: [number, number];
  strategy?: RouteStrategy;
  world_state?: Record<string, any>;
  constraints?: Record<string, any>;
  persist?: boolean;
}

export interface RouteResponse {
  id: string;
  mission_id?: string | null;
  unit_id?: string;
  strategy: RouteStrategy;
  distance_km: number;
  estimated_duration_s: number;
  fuel_l: number;
  risk_score: number;
  waypoints: [number, number][];
  explanation: string;
  segments: RouteSegment[];
}

const BASE_URL = (
  (import.meta.env?.["VITE_DOIP_API_URL"] as string | undefined) ?? "http://localhost:8000"
).replace(/\/$/, "");

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("doip.token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/**
 * Calculate an optimal tactical route given start, destination, and strategy.
 */
export async function calculateRoute(
  req: RouteCalculateRequest,
  timeoutMs = 3000,
): Promise<RouteResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE_URL}/api/routes/calculate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeader(),
      },
      body: JSON.stringify({
        start: req.start,
        destination: req.destination,
        strategy: req.strategy ?? "shortest",
        world_state: req.world_state ?? null,
        constraints: req.constraints ?? null,
        persist: req.persist ?? true,
      }),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Routing error" }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    return (await res.json()) as RouteResponse;
  } catch (error) {
    clearTimeout(timer);
    // Offline deterministic fallback
    return buildFallbackRoute(req);
  }
}

/**
 * List persisted tactical routes.
 */
export async function listRoutes(limit = 20): Promise<RouteResponse[]> {
  try {
    const res = await fetch(`${BASE_URL}/api/routes?limit=${limit}`, {
      headers: getAuthHeader(),
    });
    if (res.ok) {
      const data = await res.json();
      return data.routes || [];
    }
  } catch {
    // Fail-soft
  }
  return [];
}

/**
 * Get route by ID.
 */
export async function getRoute(routeId: string): Promise<RouteResponse | null> {
  try {
    const res = await fetch(`${BASE_URL}/api/routes/${routeId}`, {
      headers: getAuthHeader(),
    });
    if (res.ok) {
      return (await res.json()) as RouteResponse;
    }
  } catch {
    // Fail-soft
  }
  return null;
}

function buildFallbackRoute(req: RouteCalculateRequest): RouteResponse {
  const [sLat, sLon] = req.start;
  const [dLat, dLon] = req.destination;
  const dist = Math.sqrt((dLat - sLat) ** 2 + (dLon - sLon) ** 2) * 111.0;
  return {
    id: `RT-OFFLINE-${Date.now() % 10000}`,
    strategy: req.strategy ?? "shortest",
    distance_km: Math.round(dist * 10) / 10,
    estimated_duration_s: Math.round((dist / 60) * 3600),
    fuel_l: Math.round(dist * 0.3 * 10) / 10,
    risk_score: 0.15,
    waypoints: [
      [sLat, sLon],
      [(sLat + dLat) / 2, (sLon + dLon) / 2],
      [dLat, dLon],
    ],
    explanation: "Offline direct trajectory calculated via client fallback.",
    segments: [],
  };
}
