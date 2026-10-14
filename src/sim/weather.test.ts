import { beforeEach, describe, expect, it, vi } from "vitest";
import { simStore } from "./store";
import type { WeatherObservation } from "./types";

const mockObservation: WeatherObservation = {
  provider: "WeatherAPI.com",
  location_query: "28.61,77.20",
  resolved_name: "New Delhi",
  region: "Delhi",
  country: "India",
  lat: 28.6139,
  lon: 77.209,
  fetch_timestamp_utc: new Date().toISOString(),
  temp_c: 32.5,
  feelslike_c: 35.0,
  temp_f: 90.5,
  feelslike_f: 95.0,
  humidity_pct: 55,
  wind_kph: 12.0,
  wind_dir: "NW",
  condition_text: "Sunny",
  provenance: "REAL_OBSERVATION",
  freshness: "fresh",
  is_cached: false,
  cache_age_seconds: 0,
};

describe("Weather Integration in SimStore", () => {
  beforeEach(() => {
    simStore.clearSelectedLocationWeather();
    vi.restoreAllMocks();
  });

  it("initializes with null weather state", () => {
    const state = simStore.getState();
    expect(state.selectedLocationWeather).toBeNull();
    expect(state.weatherLoading).toBe(false);
    expect(state.weatherError).toBeNull();
  });

  it("fetches and sets weather observation successfully", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        source: "WeatherAPI.com",
        observation: mockObservation,
      }),
    } as unknown as Response);

    const obs = await simStore.fetchWeatherForLocation(28.6139, 77.209);
    expect(obs).toEqual(mockObservation);

    const state = simStore.getState();
    expect(state.selectedLocationWeather).toEqual(mockObservation);
    expect(state.weatherLoading).toBe(false);
    expect(state.weatherError).toBeNull();
  });

  it("handles provider failure gracefully with safe error message", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({
        ok: false,
        error: "weather_unavailable",
        detail: "Weather service is currently unavailable",
      }),
    } as unknown as Response);

    const obs = await simStore.fetchWeatherForLocation(28.6139, 77.209);
    expect(obs).toBeNull();

    const state = simStore.getState();
    expect(state.selectedLocationWeather).toBeNull();
    expect(state.weatherLoading).toBe(false);
    expect(state.weatherError).toBe("HTTP 503");
  });

  it("clears selected location weather on demand", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        observation: mockObservation,
      }),
    } as unknown as Response);

    await simStore.fetchWeatherForLocation(28.6139, 77.209);
    expect(simStore.getState().selectedLocationWeather).not.toBeNull();

    simStore.clearSelectedLocationWeather();
    expect(simStore.getState().selectedLocationWeather).toBeNull();
    expect(simStore.getState().weatherError).toBeNull();
  });
});
