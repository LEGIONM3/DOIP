import { describe, it, expect, vi, beforeEach } from "vitest";
import { listMissions, getMission } from "./missions";

describe("Phase 2B Missions Service", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lists missions gracefully", async () => {
    const missions = await listMissions(5);
    expect(Array.isArray(missions)).toBe(true);
  });

  it("handles non-existent mission safely", async () => {
    const mission = await getMission("MSN-NONEXISTENT");
    expect(mission).toBeNull();
  });
});
