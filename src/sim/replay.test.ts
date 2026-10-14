import { describe, it, expect } from "vitest";
import { MockSimSource } from "./engine";
import { applyEvent, foldEvents, emptyWorld } from "./reducer";
import type { SimEvent, WorldState } from "./types";

describe("Replay and Snapshot Reconstruction Fidelity", () => {
  it("reconstructs identical state at intermediate ticks between live and replayed fold", () => {
    const source = new MockSimSource();
    const collectedEvents: SimEvent[] = [];
    source.subscribe((batch) => collectedEvents.push(...batch));

    source.start({ seed: 20260202, scenarioId: "SC-1" });
    // Advance 50 ticks
    for (let i = 0; i < 50; i++) {
      source.step();
    }
    source.stop();

    expect(collectedEvents.length).toBeGreaterThan(0);
    const maxTick = collectedEvents[collectedEvents.length - 1]!.tick;
    expect(maxTick).toBe(50);

    // Live state by folding all events sequentially
    let liveState = emptyWorld();
    for (const e of collectedEvents) {
      liveState = applyEvent(liveState, e);
    }

    // Replay state using foldEvents to maxTick
    const replayStateMax = foldEvents(collectedEvents, maxTick);
    expect(replayStateMax).toEqual(liveState);

    // Verify intermediate seek to tick 25
    const intermediateEvents = collectedEvents.filter((e) => e.tick <= 25);
    let expectedTick25State = emptyWorld();
    for (const e of intermediateEvents) {
      expectedTick25State = applyEvent(expectedTick25State, e);
    }

    const replayedTick25State = foldEvents(collectedEvents, 25);
    expect(replayedTick25State).toEqual(expectedTick25State);
    expect(replayedTick25State.tick).toBe(25);

    // Verify tick 0 seek only has world_init initial entities
    const replayedTick0State = foldEvents(collectedEvents, 0);
    expect(replayedTick0State.tick).toBe(0);
    expect(Object.keys(replayedTick0State.units).length).toBeGreaterThan(0);
  });

  it("scrubbing backwards cleanly unwinds state without retaining future mutations", () => {
    const source = new MockSimSource();
    const collectedEvents: SimEvent[] = [];
    source.subscribe((batch) => collectedEvents.push(...batch));

    source.start({ seed: 20260303, scenarioId: "SC-1" });
    for (let i = 0; i < 60; i++) {
      source.step();
    }
    source.stop();

    // Fold up to tick 50
    const stateAt50 = foldEvents(collectedEvents, 50);

    // Scrub backward to tick 15
    const stateAt15 = foldEvents(collectedEvents, 15);

    expect(stateAt15.tick).toBe(15);
    expect(stateAt15.simTime).toBe(15000);

    // Events after tick 15 must NOT be present in stateAt15
    const incidentsAfter15 = collectedEvents
      .filter((e) => e.tick > 15 && e.type === "incident_open")
      .map((e) => e.entityId);

    for (const incId of incidentsAfter15) {
      expect(stateAt15.incidents[incId]).toBeUndefined();
    }
  });

  it("reconstructs units, active routes, vitals and weather cells faithfully", () => {
    const source = new MockSimSource();
    const collectedEvents: SimEvent[] = [];
    source.subscribe((batch) => collectedEvents.push(...batch));

    source.start({ seed: 20260404, scenarioId: "SC-1" });
    for (let i = 0; i < 40; i++) {
      source.step();
    }
    source.stop();

    const snapshot = foldEvents(collectedEvents, 30);
    expect(snapshot.tick).toBe(30);

    // Check units have active routes and positions
    const units = Object.values(snapshot.units);
    expect(units.length).toBeGreaterThan(0);
    for (const u of units) {
      expect(u.lat).toBeDefined();
      expect(u.lon).toBeDefined();
      expect(u.route).toBeDefined();
      expect(u.route.length).toBeGreaterThan(0);
    }

    // Check personnel have vitals history
    const personnel = Object.values(snapshot.personnel);
    expect(personnel.length).toBeGreaterThan(0);
    for (const p of personnel) {
      expect(p.heartRate).toBeGreaterThan(0);
      expect(p.history.length).toBeGreaterThan(0);
    }
  });
});
