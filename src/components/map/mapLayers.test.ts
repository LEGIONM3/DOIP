import { describe, it, expect } from "vitest";
import {
  circlePolygon,
  buildWindVector,
  getAtmosphericPalette,
  buildWeatherCloudGeoJson,
  classifyWeatherCondition,
  organicCloudPolygon,
  buildRainBands,
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
    const first = pts[0] as [number, number];
    const last = pts[pts.length - 1] as [number, number];
    expect(first[0]).toBeCloseTo(last[0], 4);
    expect(first[1]).toBeCloseTo(last[1], 4);
  });

  it("buildWindVector calculates opposite pointing arrow (blowing TO)", () => {
    // Wind from North (0 deg) blows SOUTH (180 deg)
    const vec = buildWindVector(20.0, 75.0, 30, 0);
    expect(vec.line.length).toBe(2);
    const startPt = vec.line[0] as [number, number];
    const endPt = vec.line[1] as [number, number];
    // End lat should be less than start lat (heading south)
    expect(endPt[1]).toBeLessThan(startPt[1]);
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

  it("classifyWeatherCondition differentiates all 8 meteorological categories with rich styling", () => {
    // 1. Thunderstorm
    const storm = classifyWeatherCondition(26, 8.5, 95, "Violent Thunderstorm & Squall", 45, 90);
    expect(storm.category).toBe("thunderstorm");
    expect(storm.hasRainBands).toBe(true);
    expect(storm.badge).toContain("THUNDERSTORM");
    expect(storm.severity).toBe("critical");

    // 2. Snow / Glacial
    const snow = classifyWeatherCondition(-4, 0, 71, "Light Snow Flurries", 20, 70);
    expect(snow.category).toBe("snow");
    expect(snow.hasRainBands).toBe(false);
    expect(snow.badge).toMatch(/BLIZZARD|SNOW/);

    // 3. Rainy / Precipitation
    const rain = classifyWeatherCondition(22, 6.2, 61, "Moderate Rain Showers", 14, 85);
    expect(rain.category).toBe("rainy");
    expect(rain.hasRainBands).toBe(true);
    expect(rain.badge).toContain("RAIN");

    // 4. Windy / Gale
    const windy = classifyWeatherCondition(25, 0, 1, "Strong Winds / Gale", 32, 20);
    expect(windy.category).toBe("windy");
    expect(windy.elongation).toBeGreaterThan(0.3);
    expect(windy.badge).toContain("WINDY");

    // 5. Extreme Heat
    const heat = classifyWeatherCondition(44, 0, 0, "Extreme Heatwave", 10, 5);
    expect(heat.category).toBe("heat");
    expect(heat.badge).toMatch(/HEAT|THERMAL/);

    // 6. Fog / Mist
    const fog = classifyWeatherCondition(15, 0, 45, "Dense Radiation Fog", 4, 30);
    expect(fog.category).toBe("fog");
    expect(fog.badge).toContain("FOG");

    // 7. Cloudy / Overcast
    const cloudy = classifyWeatherCondition(24, 0, 3, "Overcast Cumulus Layer", 12, 85);
    expect(cloudy.category).toBe("cloudy");
    expect(cloudy.badge).toContain("OVERCAST");

    // 8. Clear / Sunny
    const clear = classifyWeatherCondition(22, 0, 0, "Sunny Clear Skies", 6, 5);
    expect(clear.category).toBe("clear");
    expect(clear.badge).toContain("CLEAR");
  });

  it("organicCloudPolygon generates wind-elongated footprints for gale regions", () => {
    const windPoly = organicCloudPolygon(20.0, 75.0, 40_000, "windy", 90, 32, 1);
    expect(windPoly.length).toBe(33); // 32 steps + closed vertex
    const firstW = windPoly[0] as [number, number];
    const lastW = windPoly[windPoly.length - 1] as [number, number];
    expect(firstW[0]).toBeCloseTo(lastW[0], 4);
    expect(firstW[1]).toBeCloseTo(lastW[1], 4);

    const stormPoly = organicCloudPolygon(20.0, 75.0, 40_000, "thunderstorm", 0, 32, 2);
    expect(stormPoly.length).toBe(33);
  });

  it("buildRainBands generates concentric isohyet LineString features for rain/storm", () => {
    const rainBands = buildRainBands(20.3, 86.6, 50_000, "rainy", "rgba(56, 189, 248, 0.75)", 10);
    expect(rainBands.length).toBe(2); // 2 concentric bands for rainy
    expect(rainBands[0]?.geometry.type).toBe("LineString");
    const rainProp = (rainBands[0]?.properties ?? {}) as Record<string, unknown>;
    expect(rainProp["category"]).toBe("rainy");

    const stormBands = buildRainBands(20.3, 86.6, 50_000, "thunderstorm", "rgba(192, 132, 252, 0.8)", 11);
    expect(stormBands.length).toBe(3); // 3 concentric bands for violent thunderstorm
    const stormProp = (stormBands[0]?.properties ?? {}) as Record<string, unknown>;
    expect(stormProp["category"]).toBe("thunderstorm");
  });

  it("buildWeatherCloudGeoJson outputs outer/mid/inner/outline layers with disclaimer", () => {
    const testStations: EnvironmentalStation[] = [
      {
        id: "STN-TEST-1",
        name: "Test Station",
        region: "Northern",
        lat: 34.15,
        lon: 77.57,
        elevationM: 3500,
        temperatureC: -2,
        humidityPct: 60,
        cloudPct: 75,
        windSpeedKph: 24,
        windDirectionDeg: 310,
        precipitationMm: 1.2,
        weatherCode: 71,
        conditionLabel: "Snow Showers",
        provenance: "SYNTHETIC_ENVIRONMENT",
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
    const activeMoving = {
      id: "U-1",
      kind: "patrol",
      lat: 20,
      lon: 78,
      status: "active",
      speedKph: 45,
    } as unknown as Unit;
    const activeStationary = {
      id: "U-2",
      kind: "patrol",
      lat: 20,
      lon: 78,
      status: "active",
      speedKph: 0,
    } as unknown as Unit;
    const halted = {
      id: "U-3",
      kind: "convoy",
      lat: 20,
      lon: 78,
      status: "halted",
      speedKph: 30,
    } as unknown as Unit;

    expect(isUnitMoving(activeMoving)).toBe(true);
    expect(isUnitMoving(activeStationary)).toBe(false);
    expect(isUnitMoving(halted)).toBe(false);
  });

  it("getUnitHeading uses explicit telemetry or calculates from trail history", () => {
    const unitWithHeading = {
      id: "U-1",
      kind: "patrol",
      lat: 20,
      lon: 78,
      status: "active",
      heading: 135,
    } as unknown as Unit;
    expect(getUnitHeading(unitWithHeading)).toBe(135);

    const unitWithoutHeading = {
      id: "U-2",
      kind: "patrol",
      lat: 21,
      lon: 78,
      status: "active",
    } as unknown as Unit;
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
