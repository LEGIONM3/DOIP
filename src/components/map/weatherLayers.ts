import type { Feature, FeatureCollection } from "geojson";
import type { EnvironmentalStation, WeatherObservation } from "@/sim/types";
import type * as maplibregl from "maplibre-gl";

/**
 * SCIENTIFIC LIMITATION NOTICE:
 * Surface meteorological observations (WeatherAPI.com / Open-Meteo) are discrete point measurements.
 * The geographic disks rendered here represent illustrative observation footprints and relative cloud cover/thermal footprints,
 * NOT a continuous radar image or satellite-derived cloud boundary.
 */
export const WEATHER_FOOTPRINT_DISCLAIMER =
  "ILLUSTRATIVE POINT-OBSERVATION FOOTPRINT: Surface point observation displayed as approximate footprint; not continuous radar or satellite boundary.";

/** Generate smooth approximate circle coordinates around a lat/lon center */
export function circlePolygon(
  lat: number,
  lon: number,
  radiusM: number,
  steps = 48,
  irregularity = 0.08,
  seed = 1,
): number[][] {
  const dLat = radiusM / 111_320;
  const dLon = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180) || 1);
  const pts: number[][] = [];

  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    // Organic, subtle cloud-like lobing
    const lobe = 1 + Math.sin(a * 3 + seed) * irregularity + Math.cos(a * 5 + seed * 2) * (irregularity * 0.5);
    const rLon = dLon * lobe;
    const rLat = dLat * lobe;
    pts.push([lon + Math.cos(a) * rLon, lat + Math.sin(a) * rLat]);
  }
  return pts;
}

/** Calculate wind vector line string from station coords */
export function buildWindVector(
  lat: number,
  lon: number,
  windSpeedKph: number,
  windDirectionDeg: number,
): { line: number[][]; arrowHead: number[][] } {
  // Arrow length proportional to wind speed (clamped between 15km and 60km length on map)
  const lengthM = Math.max(12_000, Math.min(55_000, windSpeedKph * 1000));
  // Wind direction in meteorology is direction wind blows FROM.
  // Vector vector points in direction wind blows TO: (dir + 180) deg
  const toAngleRad = (((windDirectionDeg + 180) % 360) * Math.PI) / 180;

  const dLat = (lengthM * Math.cos(toAngleRad)) / 111_320;
  const dLon = (lengthM * Math.sin(toAngleRad)) / (111_320 * Math.cos((lat * Math.PI) / 180) || 1);

  const endLon = lon + dLon;
  const endLat = lat + dLat;

  // Arrowhead barb
  const barbLenM = lengthM * 0.28;
  const barbAngle1 = toAngleRad + Math.PI - 0.45;
  const barbAngle2 = toAngleRad + Math.PI + 0.45;

  const b1Lon = endLon + (barbLenM * Math.sin(barbAngle1)) / (111_320 * Math.cos((endLat * Math.PI) / 180) || 1);
  const b1Lat = endLat + (barbLenM * Math.cos(barbAngle1)) / 111_320;
  const b2Lon = endLon + (barbLenM * Math.sin(barbAngle2)) / (111_320 * Math.cos((endLat * Math.PI) / 180) || 1);
  const b2Lat = endLat + (barbLenM * Math.cos(barbAngle2)) / 111_320;

  return {
    line: [
      [lon, lat],
      [endLon, endLat],
    ],
    arrowHead: [
      [b1Lon, b1Lat],
      [endLon, endLat],
      [b2Lon, b2Lat],
    ],
  };
}

export interface WeatherCloudPalette {
  primaryRgba: (alpha: number) => string;
  outlineColor: string;
  category: "storm" | "rain" | "snow" | "heat" | "fog" | "clear";
}

/** Determines cohesive atmospheric color palette based on real observation conditions */
export function getAtmosphericPalette(
  tempC: number,
  precipMm: number,
  weatherCode: number,
  conditionLabel: string,
): WeatherCloudPalette {
  const text = conditionLabel.toLowerCase();

  // Severe Storm / Cyclone
  if (text.includes("cyclone") || text.includes("storm") || weatherCode >= 95) {
    return {
      primaryRgba: (a) => `rgba(71, 85, 105, ${a.toFixed(3)})`, // Dark storm slate
      outlineColor: "rgba(148, 163, 184, 0.7)",
      category: "storm",
    };
  }

  // Freezing / Blizzard / Snow
  if (tempC <= 0 || text.includes("snow") || text.includes("blizzard") || (weatherCode >= 71 && weatherCode <= 77)) {
    return {
      primaryRgba: (a) => `rgba(186, 230, 253, ${a.toFixed(3)})`, // Cool glacial ice
      outlineColor: "rgba(56, 189, 248, 0.65)",
      category: "snow",
    };
  }

  // Rain / Coastal Showers
  if (precipMm >= 0.5 || text.includes("rain") || text.includes("drizzle") || (weatherCode >= 50 && weatherCode <= 69)) {
    return {
      primaryRgba: (a) => `rgba(56, 189, 248, ${a.toFixed(3)})`, // Atmospheric precipitation blue
      outlineColor: "rgba(14, 165, 233, 0.65)",
      category: "rain",
    };
  }

  // Extreme Heatwave / Thermal
  if (tempC >= 36 || text.includes("thermal") || text.includes("heat")) {
    return {
      primaryRgba: (a) => `rgba(251, 191, 36, ${a.toFixed(3)})`, // Desert warm haze
      outlineColor: "rgba(245, 158, 11, 0.65)",
      category: "heat",
    };
  }

  // Fog / Valley Mist
  if (text.includes("fog") || text.includes("mist") || weatherCode === 45 || weatherCode === 48) {
    return {
      primaryRgba: (a) => `rgba(203, 213, 225, ${a.toFixed(3)})`, // Silver-gray haze
      outlineColor: "rgba(148, 163, 184, 0.6)",
      category: "fog",
    };
  }

  // Overcast / Cloudy / Clear Baseline
  return {
    primaryRgba: (a) => `rgba(241, 245, 249, ${a.toFixed(3)})`, // Soft translucent cloud white
    outlineColor: "rgba(203, 213, 225, 0.5)",
    category: "clear",
  };
}

/**
 * Builds multi-depth GeoJSON feature collections for cloud-like geographic disks.
 * Implements feathered edges and layered opacities derived from cloud cover and meteorological metrics.
 */
export function buildWeatherCloudGeoJson(
  stations: EnvironmentalStation[],
  selectedWeather: WeatherObservation | null,
  opacityMultiplier = 0.75,
): {
  cloudsOuter: FeatureCollection;
  cloudsMid: FeatureCollection;
  cloudsInner: FeatureCollection;
  cloudsOutline: FeatureCollection;
  windVectors: FeatureCollection;
} {
  const outerFeatures: Feature[] = [];
  const midFeatures: Feature[] = [];
  const innerFeatures: Feature[] = [];
  const outlineFeatures: Feature[] = [];
  const vectorFeatures: Feature[] = [];

  // Deduplicate observation locations
  const items: Array<{
    id: string;
    name: string;
    lat: number;
    lon: number;
    tempC: number;
    humidity: number;
    cloudPct: number;
    windSpeed: number;
    windDir: number;
    precip: number;
    code: number;
    label: string;
    provenance: string;
    lastUpdated: string;
    seed: number;
  }> = [];

  let idx = 0;
  for (const stn of stations) {
    idx += 1;
    items.push({
      id: stn.id,
      name: stn.name,
      lat: stn.lat,
      lon: stn.lon,
      tempC: stn.temperatureC,
      humidity: stn.humidityPct,
      cloudPct: stn.cloudPct ?? (stn.precipitationMm > 0 ? 80 : 35),
      windSpeed: stn.windSpeedKph,
      windDir: stn.windDirectionDeg,
      precip: stn.precipitationMm,
      code: stn.weatherCode,
      label: stn.conditionLabel,
      provenance: stn.provenance,
      lastUpdated: stn.lastUpdated,
      seed: idx,
    });
  }

  // Include on-demand selected observation point if not already covered
  if (selectedWeather && !items.some((i) => Math.abs(i.lat - selectedWeather.lat) < 0.05 && Math.abs(i.lon - selectedWeather.lon) < 0.05)) {
    items.push({
      id: "SELECTED-LOCATION",
      name: selectedWeather.resolved_name || selectedWeather.location_query || "Queried Location",
      lat: selectedWeather.lat,
      lon: selectedWeather.lon,
      tempC: selectedWeather.temp_c ?? 25,
      humidity: selectedWeather.humidity_pct ?? 50,
      cloudPct: selectedWeather.cloud_pct ?? (selectedWeather.precip_mm ? 80 : 30),
      windSpeed: selectedWeather.wind_kph ?? 15,
      windDir: selectedWeather.wind_degree ?? 180,
      precip: selectedWeather.precip_mm ?? 0,
      code: selectedWeather.condition_code ?? 1,
      label: selectedWeather.condition_text ?? "Live Weather",
      provenance: selectedWeather.provenance,
      lastUpdated: selectedWeather.fetch_timestamp_utc,
      seed: 99,
    });
  }

  for (const item of items) {
    const palette = getAtmosphericPalette(item.tempC, item.precip, item.code, item.label);

    // Scaling factors based on cloud cover & wind
    const cloudNorm = Math.max(0.15, Math.min(1.0, item.cloudPct / 100));
    // Base footprint radius: 45km - 110km
    const maxRadiusM = 45_000 + cloudNorm * 45_000 + Math.min(item.windSpeed, 50) * 350;

    // Outer feather layer (low opacity, soft edge)
    const outerRadius = maxRadiusM;
    const outerAlpha = Math.min(0.24, 0.08 + cloudNorm * 0.16) * opacityMultiplier;
    const outerRing = circlePolygon(item.lat, item.lon, outerRadius, 40, 0.11, item.seed);

    outerFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-outer`,
        stnId: item.id,
        name: item.name,
        color: palette.primaryRgba(outerAlpha),
        disclaimer: WEATHER_FOOTPRINT_DISCLAIMER,
      },
      geometry: { type: "Polygon", coordinates: [outerRing] },
    });

    // Mid layer (density build)
    const midRadius = maxRadiusM * 0.65;
    const midAlpha = Math.min(0.38, 0.14 + cloudNorm * 0.22) * opacityMultiplier;
    const midRing = circlePolygon(item.lat, item.lon, midRadius, 36, 0.09, item.seed + 3);

    midFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-mid`,
        stnId: item.id,
        color: palette.primaryRgba(midAlpha),
      },
      geometry: { type: "Polygon", coordinates: [midRing] },
    });

    // Inner core layer (most concentrated observation center)
    const innerRadius = maxRadiusM * 0.35;
    const innerAlpha = Math.min(0.55, 0.20 + cloudNorm * 0.30) * opacityMultiplier;
    const innerRing = circlePolygon(item.lat, item.lon, innerRadius, 32, 0.06, item.seed + 7);

    innerFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-inner`,
        stnId: item.id,
        color: palette.primaryRgba(innerAlpha),
      },
      geometry: { type: "Polygon", coordinates: [innerRing] },
    });

    // Subtle feathered outline
    outlineFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-line`,
        color: palette.outlineColor,
        opacity: 0.35 * opacityMultiplier,
      },
      geometry: { type: "LineString", coordinates: outerRing },
    });

    // Wind vector arrows (rendered if wind >= 8 km/h)
    if (item.windSpeed >= 8) {
      const vector = buildWindVector(item.lat, item.lon, item.windSpeed, item.windDir);
      vectorFeatures.push({
        type: "Feature",
        properties: {
          id: `${item.id}-wind`,
          speed: item.windSpeed,
          dir: item.windDir,
          color: "rgba(56, 189, 248, 0.75)",
        },
        geometry: { type: "LineString", coordinates: vector.line },
      });
      vectorFeatures.push({
        type: "Feature",
        properties: {
          id: `${item.id}-wind-head`,
          color: "rgba(56, 189, 248, 0.85)",
        },
        geometry: { type: "LineString", coordinates: vector.arrowHead },
      });
    }
  }

  return {
    cloudsOuter: { type: "FeatureCollection", features: outerFeatures },
    cloudsMid: { type: "FeatureCollection", features: midFeatures },
    cloudsInner: { type: "FeatureCollection", features: innerFeatures },
    cloudsOutline: { type: "FeatureCollection", features: outlineFeatures },
    windVectors: { type: "FeatureCollection", features: vectorFeatures },
  };
}

/** Initialize MapLibre sources and layers for the dedicated weather visualization layer */
export function setupWeatherMapLibreLayers(map: maplibregl.Map): void {
  const empty: FeatureCollection = { type: "FeatureCollection", features: [] };

  if (!map.getSource("weather-clouds-outer")) {
    map.addSource("weather-clouds-outer", { type: "geojson", data: empty });
  }
  if (!map.getSource("weather-clouds-mid")) {
    map.addSource("weather-clouds-mid", { type: "geojson", data: empty });
  }
  if (!map.getSource("weather-clouds-inner")) {
    map.addSource("weather-clouds-inner", { type: "geojson", data: empty });
  }
  if (!map.getSource("weather-clouds-outline")) {
    map.addSource("weather-clouds-outline", { type: "geojson", data: empty });
  }
  if (!map.getSource("weather-wind-vectors")) {
    map.addSource("weather-wind-vectors", { type: "geojson", data: empty });
  }

  const domeBefore = map.getLayer("weather-dome") ? "weather-dome" : undefined;
  const trailsBefore = map.getLayer("unit-trails") ? "unit-trails" : undefined;

  // 1. Outer cloud disk (soft translucent feathered boundary)
  if (!map.getLayer("layer-weather-clouds-outer")) {
    map.addLayer(
      {
        id: "layer-weather-clouds-outer",
        type: "fill",
        source: "weather-clouds-outer",
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": 1.0,
        },
      },
      domeBefore, // placed right below synthetic simulation weather dome if present
    );
  }

  // 2. Mid cloud disk (graduated density)
  if (!map.getLayer("layer-weather-clouds-mid")) {
    map.addLayer(
      {
        id: "layer-weather-clouds-mid",
        type: "fill",
        source: "weather-clouds-mid",
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": 1.0,
        },
      },
      domeBefore,
    );
  }

  // 3. Inner observation core
  if (!map.getLayer("layer-weather-clouds-inner")) {
    map.addLayer(
      {
        id: "layer-weather-clouds-inner",
        type: "fill",
        source: "weather-clouds-inner",
        paint: {
          "fill-color": ["get", "color"],
          "fill-opacity": 1.0,
        },
      },
      domeBefore,
    );
  }

  // 4. Subtle outline boundary
  if (!map.getLayer("layer-weather-clouds-outline")) {
    map.addLayer(
      {
        id: "layer-weather-clouds-outline",
        type: "line",
        source: "weather-clouds-outline",
        paint: {
          "line-color": ["get", "color"],
          "line-width": 1.2,
          "line-opacity": ["get", "opacity"],
          "line-dasharray": [3, 2],
        },
      },
      domeBefore,
    );
  }

  // 5. Wind Vectors (arrows indicating speed and direction)
  if (!map.getLayer("layer-weather-wind-vectors")) {
    map.addLayer(
      {
        id: "layer-weather-wind-vectors",
        type: "line",
        source: "weather-wind-vectors",
        minzoom: 5.5, // visible when zooming in to regional/theater view
        paint: {
          "line-color": ["get", "color"],
          "line-width": 1.8,
          "line-opacity": 0.85,
        },
      },
      trailsBefore, // beneath unit movement trails if present
    );
  }
}

