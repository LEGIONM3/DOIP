import type { StyleSpecification } from "maplibre-gl";

export type MapProvider = "carto_esri" | "maptiler" | "mapbox" | "custom";

const STORAGE_KEY_API_KEY = "doip.map.apiKey";
const STORAGE_KEY_PROVIDER = "doip.map.provider";
const STORAGE_KEY_CUSTOM_URL = "doip.map.customStyleUrl";

const ESRI_TILES =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const CARTO_LABELS = [
  "https://a.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png".replace("{r}", ""),
  "https://b.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png",
  "https://c.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png",
];

export const CARTO_DARK_STYLE =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

export function getStoredMapApiKey(): string {
  if (typeof window === "undefined") return "";
  const stored = window.localStorage.getItem(STORAGE_KEY_API_KEY);
  if (stored) return stored.trim();

  const envKey =
    (import.meta.env["VITE_MAP_API_KEY"] as string | undefined) ??
    (import.meta.env["VITE_MAPTILER_API_KEY"] as string | undefined) ??
    (import.meta.env["VITE_MAPBOX_TOKEN"] as string | undefined);

  return (envKey ?? "").trim();
}

export function getStoredMapProvider(): MapProvider {
  if (typeof window === "undefined") return "carto_esri";
  const stored = window.localStorage.getItem(STORAGE_KEY_PROVIDER) as MapProvider | null;
  if (stored && ["carto_esri", "maptiler", "mapbox", "custom"].includes(stored)) {
    return stored;
  }

  const key = getStoredMapApiKey();
  if (key) {
    if (key.startsWith("pk.")) return "mapbox";
    if (import.meta.env["VITE_MAPBOX_TOKEN"]) return "mapbox";
    if (import.meta.env["VITE_MAPTILER_API_KEY"]) return "maptiler";
    return "maptiler";
  }

  return "carto_esri";
}

export function getStoredCustomStyleUrl(): string {
  if (typeof window === "undefined") return "";
  return (
    window.localStorage.getItem(STORAGE_KEY_CUSTOM_URL) ??
    (import.meta.env["VITE_MAP_STYLE_URL"] as string | undefined) ??
    ""
  ).trim();
}

export function saveMapConfig(
  apiKey: string,
  provider: MapProvider,
  customStyleUrl?: string,
): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY_API_KEY, apiKey.trim());
  window.localStorage.setItem(STORAGE_KEY_PROVIDER, provider);
  if (customStyleUrl !== undefined) {
    window.localStorage.setItem(STORAGE_KEY_CUSTOM_URL, customStyleUrl.trim());
  }
  window.dispatchEvent(new CustomEvent("doip:map-config-changed"));
}

export function resetMapConfig(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY_API_KEY);
  window.localStorage.removeItem(STORAGE_KEY_PROVIDER);
  window.localStorage.removeItem(STORAGE_KEY_CUSTOM_URL);
  window.dispatchEvent(new CustomEvent("doip:map-config-changed"));
}

export const defaultEsriImageryStyle = (): StyleSpecification => ({
  version: 8,
  sources: {
    "esri-imagery": {
      type: "raster",
      tiles: [ESRI_TILES],
      tileSize: 256,
      maxzoom: 19,
      attribution: "Esri, Maxar, Earthstar Geographics",
    },
    "carto-labels": {
      type: "raster",
      tiles: CARTO_LABELS,
      tileSize: 256,
      maxzoom: 20,
      attribution: "© OpenStreetMap contributors © CARTO",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#0A0A0A" } },
    {
      id: "esri-imagery-layer",
      type: "raster",
      source: "esri-imagery",
      paint: {
        "raster-opacity": 1,
        "raster-brightness-max": 0.55,
        "raster-saturation": -0.4,
        "raster-contrast": 0.05,
      },
    },
    {
      id: "carto-labels-layer",
      type: "raster",
      source: "carto-labels",
      paint: { "raster-opacity": 0.9 },
    },
  ],
});

export function resolveMapStyle(
  basemap: "imagery" | "dark",
  provider?: MapProvider,
  apiKey?: string,
  customUrl?: string,
): string | StyleSpecification {
  const p = provider ?? getStoredMapProvider();
  const key = apiKey ?? getStoredMapApiKey();
  const custom = customUrl ?? getStoredCustomStyleUrl();

  if (p === "custom" && custom) {
    return custom.replace("{key}", key).replace("{token}", key);
  }

  if (p === "mapbox" && key) {
    if (basemap === "imagery") {
      return `https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12?access_token=${key}`;
    }
    return `https://api.mapbox.com/styles/v1/mapbox/dark-v11?access_token=${key}`;
  }

  if (p === "maptiler" && key) {
    if (basemap === "imagery") {
      return `https://api.maptiler.com/maps/satellite/style.json?key=${key}`;
    }
    return `https://api.maptiler.com/maps/dataviz-dark/style.json?key=${key}`;
  }

  // Fallback to zero-cost Carto + Esri
  if (basemap === "imagery") {
    return defaultEsriImageryStyle();
  }
  return CARTO_DARK_STYLE;
}

export function getMapAttribution(provider?: MapProvider): string {
  const p = provider ?? getStoredMapProvider();
  switch (p) {
    case "maptiler":
      return "© MapTiler © OpenStreetMap contributors";
    case "mapbox":
      return "© Mapbox © OpenStreetMap contributors";
    default:
      return "© OpenStreetMap contributors © CARTO";
  }
}
