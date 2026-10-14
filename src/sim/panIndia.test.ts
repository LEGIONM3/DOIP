import { describe, expect, it } from "vitest";
import { buildInitialWorld, MockSimSource, INDIAN_SECTORS } from "./engine";
import { simStore } from "./store";

describe("Pan-India Live World Model & Simulation", () => {
  it("preserves legacy SC-1..SC-4 world bounds", () => {
    const world = buildInitialWorld(8841, "SC-2");
    expect(world.units.length).toBe(15);
    expect(world.depots.length).toBe(3);
    for (const u of world.units) {
      expect(u.lat).toBeGreaterThan(12.8);
      expect(u.lat).toBeLessThan(13.1);
      expect(u.lon).toBeGreaterThan(77.4);
      expect(u.lon).toBeLessThan(77.8);
    }
  });

  it("generates Pan-India live baseline units across strategic Indian sectors", () => {
    const world = buildInitialWorld(20261014, "IN-BASE-LIVE");
    expect(world.units.length).toBeGreaterThanOrEqual(20);
    expect(world.depots.length).toBe(7); // 7 strategic depots across subcontinent

    const sectors = new Set(world.units.map((u) => u.sector));
    expect(sectors.has("NORTH")).toBe(true);
    expect(sectors.has("WEST")).toBe(true);
    expect(sectors.has("EAST")).toBe(true);
    expect(sectors.has("CENTRAL")).toBe(true);
    expect(sectors.has("SOUTH")).toBe(true);
    expect(sectors.has("NORTHEAST")).toBe(true);

    const lats = world.units.map((u) => u.lat);
    const lons = world.units.map((u) => u.lon);
    expect(Math.max(...lats)).toBeGreaterThan(30.0); // Northern Ladakh
    expect(Math.min(...lats)).toBeLessThan(15.0); // Southern / Littoral
    expect(Math.min(...lons)).toBeLessThan(73.0); // Western Rajasthan
    expect(Math.max(...lons)).toBeGreaterThan(85.0); // Eastern / Coastal
  });

  it("initializes scenario-specific weather in artificial impact simulation", () => {
    const cycloneWorld = buildInitialWorld(20261014, "IN-SC-CYCLONE");
    expect(cycloneWorld.weather).toBeDefined();
    expect(cycloneWorld.weather!.length).toBe(1);
    expect(cycloneWorld.weather![0]!.id).toBe("W-CYCLONE-BOB");
    expect(cycloneWorld.weather![0]!.kind).toBe("storm");
  });

  it("initializes pan-india multi-sector cascade scenario with 4 simultaneous hazard cells", () => {
    const cascadeWorld = buildInitialWorld(20261014, "IN-SC-CASCADE");
    expect(cascadeWorld.weather).toBeDefined();
    expect(cascadeWorld.weather!.length).toBe(4);
    const weatherIds = cascadeWorld.weather!.map((w) => w.id);
    expect(weatherIds).toContain("W-CYCLONE-BOB");
    expect(weatherIds).toContain("W-BLIZZARD-LEH");
    expect(weatherIds).toContain("W-HEATWAVE-THAR");
    expect(weatherIds).toContain("W-SQUALL-ANDAMAN");
  });

  it("steps Pan-India simulation source and emits movement events", () => {
    const source = new MockSimSource();
    const emitted: any[] = [];
    source.subscribe((events) => emitted.push(...events));

    source.start({ seed: 20261014, scenarioId: "IN-SC-CYCLONE" });
    expect(emitted.length).toBeGreaterThan(0);
    expect(emitted[0].type).toBe("world_init");
    expect(emitted[0].payload.scenarioId).toBe("IN-SC-CYCLONE");

    const preCount = emitted.length;
    source.step();
    expect(emitted.length).toBeGreaterThan(preCount);

    source.stop();
  });

  it("switches world mode and isolates simulation branch in simStore", () => {
    simStore.resetToBaseline();
    expect(simStore.getState().worldMode).toBe("baseline");
    expect(simStore.getState().activeBranchId).toBeNull();

    // Fork simulation
    simStore.forkSimulation("IN-SC-CASCADE", 20261014);
    expect(simStore.getState().worldMode).toBe("simulation");
    expect(simStore.getState().activeBranchId).toBeTruthy();
    expect(simStore.getState().scenarioId).toBe("IN-SC-CASCADE");

    // Instant Reset to Baseline
    simStore.resetToBaseline();
    expect(simStore.getState().worldMode).toBe("baseline");
    expect(simStore.getState().activeBranchId).toBeNull();
    expect(simStore.getState().scenarioId).toBe("IN-BASE-LIVE");
  });
});
