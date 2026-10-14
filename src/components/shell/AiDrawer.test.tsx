import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AiDrawer } from "./AiDrawer";

// Mock TanStack router Link component
vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, className }: any) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

// Mock Sim store
vi.mock("@/sim/store", () => ({
  useSim: (selector: any) => {
    const mockState = {
      world: {
        tick: 42,
        units: {
          "UAV-01": { id: "UAV-01", callsign: "Valkyrie-1", fuel: 65, status: "nominal" },
        },
        incidents: {
          "INC-1": { id: "INC-1", open: true, severity: "high" },
        },
        alerts: {},
        weather: {},
      },
      events: [
        {
          id: 1,
          tick: 40,
          type: "incident_open",
          severity: "high",
          entityId: "INC-1",
        },
      ],
    };
    return selector(mockState);
  },
}));

// Mock AI Service
vi.mock("@/services/ai", () => ({
  queryAi: vi.fn().mockResolvedValue({
    query: "What is fuel minimum?",
    run_id: null,
    tick: 42,
    answer: "Doctrine SOP-02 requires minimum 40% fuel reserve.",
    facts: ["All units report nominal fuel reserves above 40%."],
    projections: ["Resupply recommended within 30 ticks."],
    recommendations: [
      {
        action: "TASK_RESUPPLY_DEPOT",
        rationale: "Adhere to SOP-02 threshold.",
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
    latency_ms: 145,
    mode: "local_llm",
  }),
}));

describe("AiDrawer Component (Phase 1B)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the AI drawer header and SITREPS tab by default", () => {
    render(<AiDrawer onClose={vi.fn()} />);

    expect(screen.getByText("TACTICAL AI")).toBeDefined();
    expect(screen.getByText("SITREPS")).toBeDefined();
    expect(screen.getByText("ASK")).toBeDefined();
    expect(screen.getByText("WHAT-IF")).toBeDefined();
    expect(screen.getByText("Posture")).toBeDefined();
    expect(screen.getByText("Full situation report →")).toBeDefined();
  });

  it("switches to ASK tab and executes an AI query", async () => {
    render(<AiDrawer onClose={vi.fn()} />);

    // Click ASK tab
    const askTab = screen.getByText("ASK");
    fireEvent.click(askTab);

    // Verify quick inquiry pills are visible
    expect(screen.getByText("Quick Inquiries")).toBeDefined();

    // Query input
    const input = screen.getByPlaceholderText("Query tactical doctrine or simulation...");
    fireEvent.change(input, { target: { value: "What is fuel minimum?" } });

    const submitBtn = screen.getByLabelText("Ask");
    fireEvent.click(submitBtn);

    // Wait for response to render
    await waitFor(() => {
      expect(screen.getByText("Doctrine SOP-02 requires minimum 40% fuel reserve.")).toBeDefined();
    });

    // Check FACT, PROJECTION, RECOMMENDATION, and CITATION chips
    expect(screen.getByText("Verified Facts")).toBeDefined();
    expect(screen.getByText("AI Projections")).toBeDefined();
    expect(screen.getByText("Tactical Recommendations")).toBeDefined();
    expect(screen.getByText("TASK_RESUPPLY_DEPOT")).toBeDefined();
    expect(screen.getByText("SOP-02 §3.1")).toBeDefined();
    expect(screen.getByText("DSL Safety Boundary: Human Confirmation Required")).toBeDefined();
  });
});
