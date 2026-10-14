import { describe, it, expect, vi, beforeEach } from "vitest";
import { solveOptimizer, getOptimizerHistory } from "./optimizer";

describe("Phase 2D Optimizer Service", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("solves portfolio optimization under budget with fallback", async () => {
    const result = await solveOptimizer({
      budget: 200000,
      priorities: { readiness: 0.3, coverage: 0.3, response_time: 0.2, fuel_resilience: 0.1, risk_reduction: 0.1 },
    });

    expect(result).toBeDefined();
    expect(result.budget).toBe(200000);
    expect(result.total_spent).toBeLessThanOrEqual(200000);
    expect(result.recommended_investments.length).toBeGreaterThan(0);
    expect(result.tradeoffs.frontier_curve.length).toBeGreaterThan(0);
    expect(result.kpi_deltas.readiness_pct).toBeGreaterThan(0);
  });

  it("fetches optimizer history gracefully", async () => {
    const history = await getOptimizerHistory(5);
    expect(Array.isArray(history)).toBe(true);
  });
});
