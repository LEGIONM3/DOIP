import { describe, it, expect } from "vitest";
import {
  circlePolygon,
  buildWindVector,
  getAtmosphericPalette,
  buildWeatherCloudGeoJson,
  WEATHER_FOOTPRINT_DISCLAIMER,
} from "./weatherLayers";
import {
  calculateBearing,
  isUnitMoving,
  getUnitHeading,
  UnitTrailBuffer,
  MAX_TRAIL_LENGTH,
} from "./movementLayers";
import type { EnvironmentalStation, Unit } from "@/sim/types";

describe("Unified Weather Layer Generator", () => {
  it("circlePolygon produces closed organic polygons with steps + 1 points", () => {
    const pts = circlePolygon(22.5, 78.9, 50_000, 32);
    expect(pts.length).toBe(33); // 32 steps + closing vertex
    expect(pts[0]![0]).toBeCloseTo(pts[pts.length - 1]![0], 4);
    expect(pts[0]![1]).toBeCloseTo(pts[pts.length - 1]![1], 4);
  });

  it("buildWindVector calculates opposite pointing arrow (blowing TO)", () => {
    // Wind from North (0 deg) blows SOUTH (180 deg)
    const vec = buildWindVector(20.0, 75.0, 30, 0);
    expect(vec.line.length).toBe(2);
    // End lat should be less than start lat (heading south)
    expect(vec.line[1]![1]).toBeLessThan(vec.line[0]![1]);
    expect(vec.arrowHead.length).toBe(3);
  });

  it("getAtmosphericPalette assigns correct color schemes", () => {
    expect(getAtmosphericPalette(25, 0, 95, "Severe Thunderstorm").category).toBe("storm");
    expect(getAtmosphericPalette(-5, 0, 71, "Light Snow").category).toBe("snow");
    expect(getAtmosphericPalette(28, 4.5, 61, "Moderate Rain").category).toBe("rain");
    expect(getAtmosphericPalette(42, 0, 0, "Clear / High Heat").category).toBe("heat");
    expect(getAtmosphericPalette(18, 0, 45, "Dense Fog").category).toBe("fog");
    expect(getAtmosphericPalette(22, 0, 1, "Partly Cloudy").category).toBe("clear");
  });

  it("buildWeatherCloudGeoJson outputs outer/mid/inner/outline layers with disclaimer", () => {
    const testStations: EnvironmentalStation[] = [
      {
        id: "STN-TEST-1",
        name: "Test Station",
        region: "Northern",
        lat: 34.15,
        lon: 77.57,
        temperatureC: -2,
        feelsLikeC: -6,
        humidityPct: 60,
        cloudPct: 75,
        windSpeedKph: 24,
        windDirectionDeg: 310,
        precipitationMm: 1.2,
        weatherCode: 71,
        conditionLabel: "Snow Showers",
        provenance: "TEST_MOCK",
        freshness: "fresh",
        lastUpdated: "2026-10-14T06:00:00Z",
      },
    ];

    const geo = buildWeatherCloudGeoJson(testStations, null, 0.75);

    expect(geo.cloudsOuter.features.length).toBe(1);
    expect(geo.cloudsMid.features.length).toBe(1);
    expect(geo.cloudsInner.features.length).toBe(1);
    expect(geo.cloudsOutline.features.length).toBe(1);
    // Wind is 24 km/h >= 8 km/h so wind vector generated
    expect(geo.windVectors.features.length).toBeGreaterThanOrEqual(1);

    const outerProp = geo.cloudsOuter.features[0]!.properties as Record<string, unknown>;
    expect(outerProp["disclaimer"]).toBe(WEATHER_FOOTPRINT_DISCLAIMER);
    expect(outerProp["stnId"]).toBe("STN-TEST-1");
  });
});

describe("Pan-India Synthetic Movement Overlays", () => {
  it("calculateBearing computes cardinal directions correctly", () => {
    // East: (0,0) to (0,1)
    expect(calculateBearing([0, 0], [0, 1])).toBe(90);
    // North: (0,0) to (1,0)
    expect(calculateBearing([0, 0], [1, 0])).toBe(0);
    // South: (1,0) to (0,0)
    expect(calculateBearing([1, 0], [0, 0])).toBe(180);
    // West: (0,1) to (0,0)
    expect(calculateBearing([0, 1], [0, 0])).toBe(270);
  });

  it("isUnitMoving differentiates active vs halted units", () => {
    const activeMoving: Unit = {
      id: "U-1",
      kind: "patrol",
      lat: 20,
      lon: 78,
      status: "active",
      speedKph: 45,
    };
    const activeStationary: Unit = {
      id: "U-2",
      kind: "patrol",
      lat: 20,
      lon: 78,
      status: "active",
      speedKph: 0,
    };
    const halted: Unit = {
      id: "U-3",
      kind: "convoy",
      lat: 20,
      lon: 78,
      status: "halted",
      speedKph: 30,
    };

    expect(isUnitMoving(activeMoving)).toBe(true);
    expect(isUnitMoving(activeStationary)).toBe(false);
    expect(isUnitMoving(halted)).toBe(false);
  });

  it("getUnitHeading uses explicit telemetry or calculates from trail history", () => {
    const unitWithHeading: Unit = {
      id: "U-1",
      kind: "patrol",
      lat: 20,
      lon: 78,
      status: "active",
      heading: 135,
    };
    expect(getUnitHeading(unitWithHeading)).toBe(135);

    const unitWithoutHeading: Unit = {
      id: "U-2",
      kind: "patrol",
      lat: 21,
      lon: 78,
      status: "active",
    };
    // Trail moving North: (78, 20) -> (78, 21)
    const trail: Array<[number, number]> = [
      [78, 20],
      [78, 21],
    ];
    expect(getUnitHeading(unitWithoutHeading, trail)).toBe(0);
  });

  it("UnitTrailBuffer bounds history, prunes stale units, and produces GeoJSON", () => {
    const buffer = new UnitTrailBuffer(5);

    // Record 8 points for unit U-A
    for (let i = 0; i < 8; i++) {
      buffer.record("U-A", 78.0 + i * 0.01, 20.0 + i * 0.01);
    }

    const trail = buffer.get("U-A");
    expect(trail).toBeDefined();
    expect(trail!.length).toBe(5); // clamped to maxLen 5

    // Check duplicate suppression
    buffer.record("U-A", 78.07, 20.07); // same as last
    expect(buffer.get("U-A")!.length).toBe(5);

    // Record unit U-B
    buffer.record("U-B", 80.0, 22.0);
    buffer.record("U-B", 80.02, 22.02);

    // Convert to GeoJSON
    const geo = buffer.toGeoJson("U-A");
    expect(geo.features.length).toBe(2);
    const selectedFeature = geo.features.find((f) => f.properties?.["id"] === "U-A");
    expect(selectedFeature?.properties?.["selected"]).toBe(true);
    expect(selectedFeature?.properties?.["color"]).toBe("#38BDF8");

    // Prune U-B
    buffer.prune(new Set(["U-A"]));
    expect(buffer.get("U-B")).toBeUndefined();
    expect(buffer.get("U-A")).toBeDefined();

    // Clear buffer
    buffer.clear();
    expect(buffer.get("U-A")).toBeUndefined();
  });
});
