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

export type WeatherCategory =
  | "thunderstorm"
  | "rainy"
  | "cloudy"
  | "windy"
  | "snow"
  | "heat"
  | "fog"
  | "clear";

export interface WeatherConditionClassification {
  category: WeatherCategory;
  categoryLabel: string;
  badge: string;
  icon: string;
  primaryColor: (alpha: number) => string;
  outlineColor: string;
  bandColor?: string;
  hasRainBands: boolean;
  elongation: number;
  severity: "critical" | "high" | "medium" | "low";
}

/** Determines cohesive atmospheric classification and color palette based on API observations */
export function classifyWeatherCondition(
  tempC: number,
  precipMm: number,
  weatherCode: number,
  conditionLabel: string,
  windSpeedKph: number,
  cloudPct: number,
): WeatherConditionClassification {
  const text = conditionLabel.toLowerCase();

  // 1. Severe Convective Thunderstorm / Cyclone / Lightning
  if (
    text.includes("cyclone") ||
    text.includes("thunder") ||
    text.includes("storm") ||
    text.includes("lightning") ||
    weatherCode >= 95 ||
    (weatherCode >= 1273 && weatherCode <= 1282)
  ) {
    return {
      category: "thunderstorm",
      categoryLabel: "Thunderstorm",
      badge: "⚡ THUNDERSTORM",
      icon: "⚡",
      primaryColor: (a) => `rgba(76, 29, 149, ${a.toFixed(3)})`, // Deep storm indigo/violet
      outlineColor: "rgba(192, 132, 252, 0.9)", // Vivid lightning violet
      bandColor: "rgba(216, 180, 254, 0.8)", // Convective squall bands
      hasRainBands: true,
      elongation: 0.15,
      severity: "critical",
    };
  }

  // 2. Freezing / Snow / Himalayan Blizzard
  if (
    tempC <= 0 ||
    text.includes("snow") ||
    text.includes("blizzard") ||
    text.includes("sleet") ||
    text.includes("ice") ||
    (weatherCode >= 71 && weatherCode <= 77) ||
    (weatherCode >= 1210 && weatherCode <= 1225)
  ) {
    return {
      category: "snow",
      categoryLabel: "Snow / Blizzard",
      badge: `❄ BLIZZARD (${tempC.toFixed(0)}°C)`,
      icon: "❄",
      primaryColor: (a) => `rgba(186, 230, 253, ${a.toFixed(3)})`, // Glacial ice cyan
      outlineColor: "rgba(56, 189, 248, 0.85)",
      bandColor: "rgba(125, 211, 252, 0.7)",
      hasRainBands: false,
      elongation: 0.1,
      severity: "high",
    };
  }

  // 3. Rain / Coastal Showers / Monsoonal Drizzle
  if (
    precipMm >= 0.1 ||
    text.includes("rain") ||
    text.includes("drizzle") ||
    text.includes("shower") ||
    (weatherCode >= 50 && weatherCode <= 69) ||
    (weatherCode >= 1150 && weatherCode <= 1201) ||
    (weatherCode >= 1240 && weatherCode <= 1246)
  ) {
    return {
      category: "rainy",
      categoryLabel: "Rainy",
      badge: `🌧 RAIN (${precipMm > 0 ? `${precipMm.toFixed(1)}mm` : "SHOWERS"})`,
      icon: "🌧",
      primaryColor: (a) => `rgba(2, 132, 199, ${a.toFixed(3)})`, // Atmospheric precipitation azure
      outlineColor: "rgba(14, 165, 233, 0.85)",
      bandColor: "rgba(56, 189, 248, 0.75)", // Concentric isohyet rain bands
      hasRainBands: true,
      elongation: 0.2,
      severity: precipMm >= 2 ? "high" : "medium",
    };
  }

  // 4. Windy / Gale / High Velocity Wind
  if (windSpeedKph >= 16 || text.includes("gale") || text.includes("gust")) {
    return {
      category: "windy",
      categoryLabel: "High Wind / Gale",
      badge: `💨 WINDY (${windSpeedKph.toFixed(0)} km/h)`,
      icon: "💨",
      primaryColor: (a) => `rgba(13, 148, 136, ${a.toFixed(3)})`, // Dynamic gale teal
      outlineColor: "rgba(45, 212, 191, 0.85)",
      hasRainBands: false,
      elongation: 0.65, // Aerodynamically elongated along wind vector
      severity: windSpeedKph >= 30 ? "high" : "medium",
    };
  }

  // 5. Desert Heatwave / Thermal Load (Thar/Western Sector)
  if (tempC >= 35 || text.includes("thermal") || text.includes("heat") || text.includes("dust")) {
    return {
      category: "heat",
      categoryLabel: "Extreme Heatwave",
      badge: `🔥 THERMAL (${tempC.toFixed(0)}°C)`,
      icon: "🔥",
      primaryColor: (a) => `rgba(217, 119, 6, ${a.toFixed(3)})`, // Desert warm amber haze
      outlineColor: "rgba(251, 191, 36, 0.85)",
      hasRainBands: false,
      elongation: 0.1,
      severity: tempC >= 40 ? "critical" : "medium",
    };
  }

  // 6. Fog / Valley Mist / Low Visibility
  if (
    text.includes("fog") ||
    text.includes("mist") ||
    text.includes("haze") ||
    weatherCode === 45 ||
    weatherCode === 48 ||
    weatherCode === 1135
  ) {
    return {
      category: "fog",
      categoryLabel: "Fog / Valley Mist",
      badge: "🌫 MIST / FOG",
      icon: "🌫",
      primaryColor: (a) => `rgba(148, 163, 184, ${a.toFixed(3)})`, // Silver-gray haze
      outlineColor: "rgba(203, 213, 225, 0.7)",
      hasRainBands: false,
      elongation: 0.15,
      severity: "low",
    };
  }

  // 7. Cloudy / Overcast (Cloud coverage >= 15% or label contains cloud)
  if (
    cloudPct >= 15 ||
    text.includes("cloud") ||
    text.includes("overcast") ||
    weatherCode === 2 ||
    weatherCode === 3 ||
    weatherCode === 1003 ||
    weatherCode === 1006 ||
    weatherCode === 1009
  ) {
    const isOvercast = cloudPct >= 70 || text.includes("overcast");
    return {
      category: "cloudy",
      categoryLabel: isOvercast ? "Overcast" : "Cloudy",
      badge: `☁ ${isOvercast ? "OVERCAST" : "CLOUDY"} (${cloudPct.toFixed(0)}%)`,
      icon: "☁",
      primaryColor: (a) => `rgba(226, 232, 240, ${a.toFixed(3)})`, // Soft billowing pearl cumulus white
      outlineColor: "rgba(203, 213, 225, 0.75)",
      hasRainBands: false,
      elongation: 0.2,
      severity: "low",
    };
  }

  // 8. Clear / Sunny Baseline
  return {
    category: "clear",
    categoryLabel: "Clear / Sunny",
    badge: `☀ CLEAR (${tempC.toFixed(0)}°C)`,
    icon: "☀",
    primaryColor: (a) => `rgba(248, 250, 252, ${a.toFixed(3)})`, // Very soft ambient white
    outlineColor: "rgba(226, 232, 240, 0.45)",
    hasRainBands: false,
    elongation: 0.1,
    severity: "low",
  };
}

export interface WeatherCloudPalette {
  primaryRgba: (alpha: number) => string;
  outlineColor: string;
  category: WeatherCategory | "storm" | "rain";
}

/** Backward compatible wrapper for palette callers */
export function getAtmosphericPalette(
  tempC: number,
  precipMm: number,
  weatherCode: number,
  conditionLabel: string,
): WeatherCloudPalette {
  const c = classifyWeatherCondition(tempC, precipMm, weatherCode, conditionLabel, 10, 0);
  const legacyCategory =
    c.category === "thunderstorm"
      ? "storm"
      : c.category === "rainy"
        ? "rain"
        : c.category === "cloudy" && (weatherCode <= 1 || conditionLabel.toLowerCase().includes("partly"))
          ? "clear"
          : c.category;

  return {
    primaryRgba: c.primaryColor,
    outlineColor: c.outlineColor,
    category: legacyCategory as WeatherCategory | "storm" | "rain",
  };
}

/** Produces closed organic circular/elliptical polygon rings (steps + 1 points) */
export function circlePolygon(
  lat: number,
  lon: number,
  radiusM: number,
  steps = 32,
  perturbation = 0.08,
  seed = 1,
): number[][] {
  const dLat = radiusM / 111_320;
  const dLon = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180) || 1);
  const pts: number[][] = [];
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    const wave = 1 + Math.sin(a * 5 + seed) * perturbation;
    pts.push([lon + Math.cos(a) * dLon * wave, lat + Math.sin(a) * dLat * wave]);
  }
  return pts;
}

/** Generate organic, condition-differentiated cloud polygons */
export function organicCloudPolygon(
  lat: number,
  lon: number,
  radiusM: number,
  category: WeatherCategory,
  windDirectionDeg = 0,
  steps = 48,
  seed = 1,
): number[][] {
  const dLat = radiusM / 111_320;
  const dLon = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180) || 1);
  const pts: number[][] = [];
  const windToRad = (((windDirectionDeg + 180) % 360) * Math.PI) / 180;

  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    let lobe = 1;

    if (category === "thunderstorm") {
      // Violent cumulonimbus with towering harmonic lobes
      lobe = 1 + Math.sin(a * 4 + seed) * 0.18 + Math.cos(a * 7 + seed * 2) * 0.11 + Math.sin(a * 11) * 0.05;
    } else if (category === "windy") {
      // Aerodynamic elongation downwind along the wind vector
      const angleDiff = a - windToRad;
      const stretch = 0.55 * Math.cos(angleDiff);
      lobe = 1 + stretch + Math.sin(a * 3 + seed) * 0.08;
    } else if (category === "rainy") {
      // Extensive nimbostratus rain shield
      lobe = 1 + Math.sin(a * 3 + seed) * 0.11 + Math.cos(a * 5 + seed) * 0.06;
    } else if (category === "snow") {
      // Hexagonal crystalline cold air lobes
      lobe = 1 + Math.cos(a * 6 + seed) * 0.12 + Math.sin(a * 3) * 0.06;
    } else if (category === "heat") {
      // Thermal ripple lobes
      lobe = 1 + Math.sin(a * 5 + seed) * 0.09 + Math.cos(a * 9) * 0.04;
    } else {
      // Billowing cumulus lobes
      lobe = 1 + Math.sin(a * 3 + seed) * 0.09 + Math.cos(a * 5 + seed * 2) * 0.05;
    }

    const rLon = dLon * Math.max(0.35, lobe);
    const rLat = dLat * Math.max(0.35, lobe);
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
  const lengthM = Math.max(14_000, Math.min(58_000, windSpeedKph * 1200));
  // Wind direction in meteorology is direction wind blows FROM.
  // Vector points in direction wind blows TO: (dir + 180) deg
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

/** Generate concentric rain / storm ripple bands */
export function buildRainBands(
  lat: number,
  lon: number,
  radiusM: number,
  category: WeatherCategory,
  bandColor: string,
  seed = 1,
): Feature[] {
  const bands: Feature[] = [];
  const fractions = category === "thunderstorm" ? [0.45, 0.75, 0.92] : [0.55, 0.82];

  for (let b = 0; b < fractions.length; b++) {
    const r = radiusM * fractions[b]!;
    const ring = organicCloudPolygon(lat, lon, r, category, 0, 36, seed + b * 2);
    bands.push({
      type: "Feature",
      properties: {
        id: `band-${b}-${seed}`,
        category,
        color: bandColor,
        width: b === 0 ? 1.8 : 1.2,
      },
      geometry: { type: "LineString", coordinates: ring },
    });
  }
  return bands;
}

/**
 * Builds multi-depth GeoJSON feature collections for condition-differentiated simulated weather clouds.
 * Distinguishes rainy, thunderstorm, cloudy, windy, snow, heat, and fog across all regions.
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
  rainBands: FeatureCollection;
  windVectors: FeatureCollection;
  conditionBadges: FeatureCollection;
  summaryCounts: Record<WeatherCategory, number>;
} {
  const outerFeatures: Feature[] = [];
  const midFeatures: Feature[] = [];
  const innerFeatures: Feature[] = [];
  const outlineFeatures: Feature[] = [];
  const rainBandFeatures: Feature[] = [];
  const vectorFeatures: Feature[] = [];
  const badgeFeatures: Feature[] = [];

  const summaryCounts: Record<WeatherCategory, number> = {
    thunderstorm: 0,
    rainy: 0,
    cloudy: 0,
    windy: 0,
    snow: 0,
    heat: 0,
    fog: 0,
    clear: 0,
  };

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
  if (
    selectedWeather &&
    !items.some(
      (i) => Math.abs(i.lat - selectedWeather.lat) < 0.05 && Math.abs(i.lon - selectedWeather.lon) < 0.05,
    )
  ) {
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
    const classification = classifyWeatherCondition(
      item.tempC,
      item.precip,
      item.code,
      item.label,
      item.windSpeed,
      item.cloudPct,
    );

    summaryCounts[classification.category] += 1;

    // Scaling factors based on condition category & cloud coverage
    const cloudNorm = Math.max(0.20, Math.min(1.0, item.cloudPct / 100));
    
    // Dynamic footprint radius scaled by condition severity
    let baseRadiusM = 48_000 + cloudNorm * 45_000;
    if (classification.category === "thunderstorm") baseRadiusM = 95_000 + item.windSpeed * 400;
    if (classification.category === "rainy") baseRadiusM = 65_000 + item.precip * 3500;
    if (classification.category === "windy") baseRadiusM = 55_000 + item.windSpeed * 650;
    if (classification.category === "heat") baseRadiusM = 58_000;

    // 1. Outer feather layer (soft edge boundary)
    const outerAlpha =
      Math.min(
        0.30,
        classification.category === "thunderstorm"
          ? 0.22 * opacityMultiplier
          : (0.09 + cloudNorm * 0.15) * opacityMultiplier,
      );
    const outerRing = organicCloudPolygon(
      item.lat,
      item.lon,
      baseRadiusM,
      classification.category,
      item.windDir,
      40,
      item.seed,
    );

    outerFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-outer`,
        stnId: item.id,
        name: item.name,
        category: classification.category,
        color: classification.primaryColor(outerAlpha),
        disclaimer: WEATHER_FOOTPRINT_DISCLAIMER,
      },
      geometry: { type: "Polygon", coordinates: [outerRing] },
    });

    // 2. Mid layer (graduated density build)
    const midRadius = baseRadiusM * 0.65;
    const midAlpha =
      Math.min(
        0.45,
        classification.category === "thunderstorm"
          ? 0.35 * opacityMultiplier
          : (0.15 + cloudNorm * 0.22) * opacityMultiplier,
      );
    const midRing = organicCloudPolygon(
      item.lat,
      item.lon,
      midRadius,
      classification.category,
      item.windDir,
      36,
      item.seed + 3,
    );

    midFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-mid`,
        stnId: item.id,
        category: classification.category,
        color: classification.primaryColor(midAlpha),
      },
      geometry: { type: "Polygon", coordinates: [midRing] },
    });

    // 3. Inner core layer (most concentrated observation center)
    const innerRadius = baseRadiusM * 0.35;
    const innerAlpha =
      Math.min(
        0.65,
        classification.category === "thunderstorm"
          ? 0.55 * opacityMultiplier
          : (0.22 + cloudNorm * 0.30) * opacityMultiplier,
      );
    const innerRing = organicCloudPolygon(
      item.lat,
      item.lon,
      innerRadius,
      classification.category,
      item.windDir,
      32,
      item.seed + 7,
    );

    innerFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-inner`,
        stnId: item.id,
        category: classification.category,
        color: classification.primaryColor(innerAlpha),
      },
      geometry: { type: "Polygon", coordinates: [innerRing] },
    });

    // 4. Subtle feathered outline boundary
    outlineFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-line`,
        category: classification.category,
        color: classification.outlineColor,
        opacity: 0.45 * opacityMultiplier,
      },
      geometry: { type: "LineString", coordinates: outerRing },
    });

    // 5. Concentric rain & storm isohyet bands (for rainy and thunderstorm regions)
    if (classification.hasRainBands && classification.bandColor) {
      const bands = buildRainBands(
        item.lat,
        item.lon,
        baseRadiusM,
        classification.category,
        classification.bandColor,
        item.seed,
      );
      rainBandFeatures.push(...bands);
    }

    // 6. Wind vector arrows (rendered if wind >= 8 km/h or classified as windy/storm)
    if (item.windSpeed >= 8 || classification.category === "windy") {
      const vector = buildWindVector(item.lat, item.lon, item.windSpeed, item.windDir);
      const vecColor =
        classification.category === "windy"
          ? "rgba(45, 212, 191, 0.9)"
          : classification.category === "thunderstorm"
            ? "rgba(192, 132, 252, 0.9)"
            : "rgba(56, 189, 248, 0.75)";

      vectorFeatures.push({
        type: "Feature",
        properties: {
          id: `${item.id}-wind`,
          speed: item.windSpeed,
          dir: item.windDir,
          color: vecColor,
        },
        geometry: { type: "LineString", coordinates: vector.line },
      });
      vectorFeatures.push({
        type: "Feature",
        properties: {
          id: `${item.id}-wind-head`,
          color: vecColor,
        },
        geometry: { type: "LineString", coordinates: vector.arrowHead },
      });
    }

    // 7. Condition Badge metadata feature
    badgeFeatures.push({
      type: "Feature",
      properties: {
        id: `${item.id}-badge`,
        stnId: item.id,
        name: item.name,
        category: classification.category,
        categoryLabel: classification.categoryLabel,
        badge: classification.badge,
        icon: classification.icon,
        color: classification.outlineColor,
        tempC: item.tempC,
        windSpeed: item.windSpeed,
        precip: item.precip,
        cloudPct: item.cloudPct,
      },
      geometry: { type: "Point", coordinates: [item.lon, item.lat] },
    });
  }

  return {
    cloudsOuter: { type: "FeatureCollection", features: outerFeatures },
    cloudsMid: { type: "FeatureCollection", features: midFeatures },
    cloudsInner: { type: "FeatureCollection", features: innerFeatures },
    cloudsOutline: { type: "FeatureCollection", features: outlineFeatures },
    rainBands: { type: "FeatureCollection", features: rainBandFeatures },
    windVectors: { type: "FeatureCollection", features: vectorFeatures },
    conditionBadges: { type: "FeatureCollection", features: badgeFeatures },
    summaryCounts,
  };
}

/** Initialize MapLibre sources and layers for simulated weather visualization */
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
  if (!map.getSource("weather-rain-bands")) {
    map.addSource("weather-rain-bands", { type: "geojson", data: empty });
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
      domeBefore,
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
          "line-width": 1.4,
          "line-opacity": ["get", "opacity"],
          "line-dasharray": [3, 2],
        },
      },
      domeBefore,
    );
  }

  // 5. Rain & Storm Isohyet Bands (concentric precipitation ripple lines)
  if (!map.getLayer("layer-weather-rain-bands")) {
    map.addLayer(
      {
        id: "layer-weather-rain-bands",
        type: "line",
        source: "weather-rain-bands",
        paint: {
          "line-color": ["get", "color"],
          "line-width": ["coalesce", ["get", "width"], 1.4],
          "line-opacity": 0.85,
          "line-dasharray": [2, 3],
        },
      },
      domeBefore,
    );
  }

  // 6. Wind Vectors (arrows indicating speed and direction)
  if (!map.getLayer("layer-weather-wind-vectors")) {
    map.addLayer(
      {
        id: "layer-weather-wind-vectors",
        type: "line",
        source: "weather-wind-vectors",
        minzoom: 5.5,
        paint: {
          "line-color": ["get", "color"],
          "line-width": 1.8,
          "line-opacity": 0.85,
        },
      },
      trailsBefore,
    );
  }
}
