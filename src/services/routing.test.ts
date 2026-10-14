import { describe, it, expect, vi, beforeEach } from "vitest";
import { calculateRoute, listRoutes, getRoute } from "./routing";

describe("Phase 2A Routing Service", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calculates tactical route with offline fallback when network is absent", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network Error"));
    const route = await calculateRoute({
      start: [34.0, 71.0],
      destination: [34.2, 71.2],
      strategy: "safest",
    });

    expect(route).toBeDefined();
    expect(route.strategy).toBe("safest");
    expect(route.distance_km).toBeGreaterThan(0);
    expect(route.waypoints.length).toBeGreaterThanOrEqual(2);
    expect(route.fuel_l).toBeGreaterThan(0);
  });

  it("fetches list of routes gracefully", async () => {
    const routes = await listRoutes(5);
    expect(Array.isArray(routes)).toBe(true);
  });

  it("fetches single route gracefully", async () => {
    const route = await getRoute("non-existent-id");
    expect(route).toBeNull();
  });
});
