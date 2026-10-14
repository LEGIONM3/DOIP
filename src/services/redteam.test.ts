import { describe, it, expect, vi, beforeEach } from "vitest";
import { generateRedTeamScenario, validateRedTeamInject, listRedTeamScenarios } from "./redteam";

describe("Phase 2E Red Team Service", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("generates staged adversarial scenario with whitelisted actions", async () => {
    const scenario = await generateRedTeamScenario({
      mission_id: "MSN-TEST",
    });

    expect(scenario).toBeDefined();
    expect(scenario.status).toBe("staged");
    expect(scenario.injects.length).toBeGreaterThan(0);
    const firstInject = scenario.injects[0]!;
    expect(firstInject.status).toBe("staged");
    expect(["spawn_weather", "create_incident", "modify_speed", "unit_report", "raise_alert"]).toContain(
      firstInject.action,
    );
  });

  it("validates whitelisted action correctly", async () => {
    const check1 = await validateRedTeamInject("create_incident", { severity: "HIGH" });
    expect(check1.valid).toBe(true);

    const check2 = await validateRedTeamInject("DROP_DATABASE", {});
    expect(check2.valid).toBe(false);
  });

  it("lists red team scenarios gracefully", async () => {
    const list = await listRedTeamScenarios();
    expect(Array.isArray(list)).toBe(true);
  });
});
