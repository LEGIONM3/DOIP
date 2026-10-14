import { describe, it, expect, vi, beforeEach } from "vitest";
import { queryAi } from "./ai";

describe("DOIP AI Service Client (Phase 1B)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("handles successful backend responses from /api/ai/query", async () => {
    const mockResponse = {
      query: "What is the policy for fuel reserves?",
      run_id: "test-run",
      tick: 30,
      answer: "According to SOP-02 §3.1, minimum reserve is 40%.",
      facts: ["All units report nominal fuel reserves."],
      projections: ["Resupply required in 45 ticks."],
      recommendations: [
        {
          action: "TASK_RESUPPLY_DEPOT",
          rationale: "Meet 40% fuel doctrine minimum.",
          requires_confirmation: true,
          priority: "HIGH",
        },
      ],
      citations: [
        {
          type: "doctrine",
          source_id: "SOP-02",
          citation: "SOP-02 §3.1",
          title: "Tactical Resupply Protocol",
          verified: true,
        },
      ],
      grounding: {
        grounded: true,
        warning: null,
        valid_citations: ["SOP-02"],
        unverified_citations: [],
      },
      latency_ms: 120.5,
      mode: "local_llm",
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await queryAi({
      query: "What is the policy for fuel reserves?",
      run_id: "test-run",
      tick: 30,
    });

    expect(result.answer).toContain("SOP-02");
    expect(result.facts.length).toBe(1);
    expect(result.recommendations.length).toBe(1);
    expect(result.recommendations[0]?.requires_confirmation).toBe(true);
    expect(result.citations[0]?.verified).toBe(true);
    expect(result.mode).toBe("local_llm");
  });

  it("falls back to structured grounded client heuristic when backend fetch fails", async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network Error"));

    const result = await queryAi({
      query: "What is the fuel resupply protocol?",
      run_id: null,
      tick: 15,
    });

    expect(result.mode).toBe("offline_client_fallback");
    expect(result.answer).toContain("Backend AI unreachable");
    expect(result.facts.length).toBeGreaterThan(0);
    expect(result.recommendations.length).toBeGreaterThan(0);
    expect(result.recommendations[0]?.requires_confirmation).toBe(true);
    expect(result.citations.some((c) => c.source_id === "SOP-02")).toBe(true);
  });
});
