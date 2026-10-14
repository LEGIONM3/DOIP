import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { LngLatLike, StyleSpecification, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { SEVERITY_META, unitDesignator } from "@/lib/doip";
import { simStore, useSim } from "@/sim/store";
import { isStale } from "@/sim/reducer";
import type { Incident, Unit, WeatherCell, Zone } from "@/sim/types";
import { Compass, Box, Square, Key, RotateCcw, Cloud, Radio, ChevronDown, Activity, RefreshCw, X } from "lucide-react";
import type { Feature, FeatureCollection } from "geojson";
import { resolveMapStyle, getMapAttribution } from "@/lib/mapConfig";
import { MapKeyDialog } from "./MapKeyDialog";
import {
  buildWeatherCloudGeoJson,
  setupWeatherMapLibreLayers,
  classifyWeatherCondition,
} from "./weatherLayers";
import {
  UnitTrailBuffer,
  getUnitHeading,
  isUnitMoving,
} from "./movementLayers";
import { MapLayerControls } from "./MapLayerControls";
import { INDIAN_SECTORS, STRATEGIC_SUPPLY_CORRIDORS } from "@/sim/engine";

export const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
export const ATTRIBUTION = "© OpenStreetMap contributors © CARTO";

export type Basemap = "imagery" | "dark";
const BASEMAP_KEY = "doip.basemap";

const ESRI_TILES =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const CARTO_LABELS = [
  "https://a.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png".replace("{r}", ""),
  "https://b.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png",
  "https://c.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png",
];

/** Satellite imagery, darkened + desaturated in-canvas so markers stay full-brightness. */
const imageryStyle = (): StyleSpecification => ({
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
        // equivalent of a rgba(0,0,0,0.45) scrim + saturate(0.6), applied to tiles only
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

const DEFAULT_PITCH = 55;
const DEFAULT_BEARING = -15;
const TRAIL_LEN = 20;

export interface TacticalMapProps {
  units?: Unit[];
  incidents?: Incident[];
  weather?: WeatherCell[];
  zones?: Zone[];
  tick?: number;
  center?: [number, number];
  zoom?: number;
  selectedId?: string | null;
  focus?: [number, number] | null;
  pulseAt?: [number, number] | null;
  waypoints?: Array<[number, number]>;
  routes?: Array<{ points: Array<[number, number]>; color: string; dashed?: boolean }>;
  cursors?: Array<{ id: string; name: string; color: string; lat: number; lon: number }>;
  radar?: boolean;
  onSelectUnit?: (id: string) => void;
  onSelectIncident?: (id: string) => void;
  onMapClick?: (latlng: [number, number]) => void;
  className?: string;
}

const unitColor = (u: Unit) => "#FFFFFF";

/** metres -> approximate degree ring polygon */
function ringPolygon(lat: number, lon: number, radiusM: number, steps = 40): number[][] {
  const dLat = radiusM / 111_320;
  const dLon = radiusM / (111_320 * Math.cos((lat * Math.PI) / 180) || 1);
  const pts: number[][] = [];
  for (let i = 0; i <= steps; i++) {
    const a = (i / steps) * Math.PI * 2;
    pts.push([lon + Math.cos(a) * dLon, lat + Math.sin(a) * dLat]);
  }
  return pts;
}

function fc(features: Feature[]): FeatureCollection {
  return { type: "FeatureCollection", features };
}

export const SECTOR_PRESETS: Array<{
  label: string;
  name: string;
  center: [number, number];
  zoom: number;
}> = [
  { label: "ALL-IN", name: "Pan-India Subcontinent", center: [78.9629, 22.5937], zoom: 4.8 },
  { label: "NORTH", name: "Northern Sector (Ladakh/J&K)", center: [77.5771, 34.1526], zoom: 7.2 },
  { label: "WEST", name: "Western Sector (Thar)", center: [70.9083, 26.9157], zoom: 7.0 },
  { label: "EAST", name: "Eastern Sector (Odisha/Coastal)", center: [86.611, 20.316], zoom: 7.0 },
  { label: "CENTRAL", name: "Central Sector (Nagpur)", center: [79.0882, 21.1458], zoom: 7.0 },
  { label: "SOUTH", name: "Southern Sector (Bengaluru)", center: [77.5946, 12.9716], zoom: 7.5 },
  { label: "NORTHEAST", name: "North-Eastern Sector (Tezpur/Assam)", center: [92.7926, 26.6338], zoom: 7.0 },
  { label: "ISLANDS", name: "Littoral Sector (Andaman)", center: [92.7265, 11.6234], zoom: 7.2 },
];

export const ARTIFICIAL_SCENARIOS = [
  { id: "IN-SC-CASCADE", label: "Cascade (Pan-India)", sector: "ALL-IN", center: [78.9629, 22.5937] as [number, number], zoom: 4.8 },
  { id: "IN-SC-CYCLONE", label: "Cyclone (Eastern)", sector: "EAST", center: [86.611, 20.316] as [number, number], zoom: 7.0 },
  { id: "IN-SC-NORTH-COMMS", label: "Blizzard & Comms (North)", sector: "NORTH", center: [77.5771, 34.1526] as [number, number], zoom: 7.2 },
  { id: "IN-SC-WEST-HEAT", label: "Heatwave (West)", sector: "WEST", center: [70.9083, 26.9157] as [number, number], zoom: 7.0 },
  { id: "IN-SC-LOGISTICS", label: "Chokepoint (Central)", sector: "CENTRAL", center: [79.0882, 21.1458] as [number, number], zoom: 7.0 },
];

export default function TacticalMap({
  units = [],
  incidents = [],
  weather = [],
  zones = [],
  tick = 0,
  center = [12.9716, 77.5946],
  zoom = 12,
  selectedId,
  focus,
  pulseAt,
  waypoints = [],
  routes = [],
  cursors = [],
  radar = false,
  onSelectUnit,
  onSelectIncident,
  onMapClick,
  className,
}: TacticalMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const [is3d, setIs3d] = useState(true);
  const [bearing, setBearing] = useState(DEFAULT_BEARING);
  const [basemap, setBasemap] = useState<Basemap>(() => {
    if (typeof window === "undefined") return "imagery";
    const v = window.localStorage.getItem(BASEMAP_KEY);
    return v === "dark" ? "dark" : "imagery";
  });
  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [mapConfigVer, setMapConfigVer] = useState(0);

  const worldMode = useSim((s) => s.worldMode);
  const activeBranchId = useSim((s) => s.activeBranchId);
  const currentScenarioId = useSim((s) => s.scenarioId);
  const envContext = useSim((s) => s.environmentalContext);
  const selectedWeather = useSim((s) => s.selectedLocationWeather);
  const weatherLoading = useSim((s) => s.weatherLoading);
  const weatherError = useSim((s) => s.weatherError);
  const weatherLayerVisible = useSim((s) => s.weatherLayerVisible);
  const cloudOpacity = useSim((s) => s.cloudOpacity);
  const movementTrailsVisible = useSim((s) => s.movementTrailsVisible);
  const windVectorsVisible = useSim((s) => s.windVectorsVisible);
  const facilitiesVisible = useSim((s) => s.facilitiesVisible);
  const supplyCorridorsVisible = useSim((s) => s.supplyCorridorsVisible);
  const zonesVisible = useSim((s) => s.zonesVisible);
  const unitsVisible = useSim((s) => s.unitsVisible);
  const clusterBadgesVisible = useSim((s) => s.clusterBadgesVisible);
  const depotsMap = useSim((s) => s.world.depots);
  const personnelMap = useSim((s) => s.world.personnel);
  const depots = useMemo(() => Object.values(depotsMap ?? {}), [depotsMap]);
  const personnel = useMemo(() => Object.values(personnelMap ?? {}), [personnelMap]);
  const [currentZoom, setCurrentZoom] = useState(zoom);
  const [metDrawerOpen, setMetDrawerOpen] = useState(false);
  const [activeSector, setActiveSector] = useState("ALL-IN");

  const isPanIndia =
    units.some((u) => u.id.startsWith("U-IN-") || u.lat > 16 || u.lon > 82) ||
    currentScenarioId.startsWith("IN-");

  useEffect(() => {
    void simStore.fetchEnvironmentalContext();
  }, []);

  const jumpToSector = useCallback(
    (preset: (typeof SECTOR_PRESETS)[number]) => {
      setActiveSector(preset.label);
      mapRef.current?.easeTo({
        center: preset.center,
        zoom: preset.zoom,
        pitch: is3d ? DEFAULT_PITCH : 0,
        duration: 900,
      });
    },
    [is3d],
  );

  useEffect(() => {
    const onConfigChange = () => setMapConfigVer((c) => c + 1);
    window.addEventListener("doip:map-config-changed", onConfigChange);
    return () => window.removeEventListener("doip:map-config-changed", onConfigChange);
  }, []);
  const [tilesLoading, setTilesLoading] = useState(true);
  const trailBufferRef = useRef<UnitTrailBuffer>(new UnitTrailBuffer(25));
  const markersRef = useRef<Record<string, maplibregl.Marker>>({});
  const clusterMarkers = useRef<Record<string, maplibregl.Marker>>({});
  const depotMarkers = useRef<Record<string, maplibregl.Marker>>({});
  const unitAnimRef = useRef<
    Record<
      string,
      { start: [number, number]; target: [number, number]; startTime: number; duration: number }
    >
  >({});
  const animRafRef = useRef<number | null>(null);
  const cbRef = useRef({ onSelectUnit, onSelectIncident, onMapClick });
  cbRef.current = { onSelectUnit, onSelectIncident, onMapClick };
  const radarRef = useRef<HTMLDivElement | null>(null);
  const viewRef = useRef<{ center: [number, number]; zoom: number } | null>(null);

  /* ---------- init (rebuilds when the basemap or map configuration changes) ---------- */
  useEffect(() => {
    if (!containerRef.current) return;
    setReady(false);
    setTilesLoading(true);
    const saved = viewRef.current;
    const resolvedStyle = resolveMapStyle(basemap);
    const effectiveCenter = (
      saved
        ? saved.center
        : isPanIndia && center[0] === 12.9716 && center[1] === 77.5946
          ? [78.9629, 22.5937]
          : [center[1], center[0]]
    ) as LngLatLike;
    const effectiveZoom = saved ? saved.zoom : isPanIndia && zoom >= 10 ? 4.8 : zoom;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: resolvedStyle as unknown as StyleSpecification,
      center: effectiveCenter,
      zoom: effectiveZoom,
      pitch: DEFAULT_PITCH,
      bearing: DEFAULT_BEARING,
      // attribution comes from each source/style — never duplicated here
      attributionControl: { compact: false },
      dragRotate: true,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

    map.on("error", (e: { error?: { message?: string } }) =>
      console.warn("[map]", e?.error?.message ?? e),
    );
    const doneLoading = () => setTilesLoading(false);
    map.on("load", doneLoading);
    map.on("idle", doneLoading);
    const loadFallback = window.setTimeout(doneLoading, 4000);

    const initLayers = () => {
      // Basemap kept just off pure black so moving markers do not smear
      try {
        for (const l of map.getStyle().layers ?? []) {
          if (l.type === "background") map.setPaintProperty(l.id, "background-color", "#0A0A0A");
        }
      } catch {
        /* style not ready */
      }

      // 3D building extrusions (vector dark basemap only)
      if (basemap === "dark") {
        try {
          map.addLayer({
            id: "doip-buildings",
            type: "fill-extrusion",
            source: "carto",
            "source-layer": "building",
            minzoom: 12,
            paint: {
              "fill-extrusion-color": "#161616",
              "fill-extrusion-height": ["coalesce", ["get", "render_height"], 12],
              "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
              "fill-extrusion-opacity": 0.9,
            },
          });
        } catch {
          /* style may not expose a building source-layer */
        }
      }

      const empty = fc([]);
      const src = (id: string, lineMetrics = false) =>
        map.addSource(id, { type: "geojson", data: empty, lineMetrics });

      src("zones");
      src("zone-lines");
      src("weather");
      src("incidents");
      src("routes");
      src("waypoints");
      src("trails", true);

      // Restricted / patrol zones -> extruded translucent walls
      map.addLayer({
        id: "zones-fill",
        type: "fill-extrusion",
        source: "zones",
        paint: {
          "fill-extrusion-color": ["get", "color"],
          "fill-extrusion-height": ["get", "height"],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.22,
        },
      });
      map.addLayer({
        id: "zones-outline",
        type: "line",
        source: "zone-lines",
        paint: {
          "line-color": ["get", "color"],
          "line-width": 1.2,
          "line-opacity": 0.85,
          "line-dasharray": [2, 3],
        },
      });

      // Weather domes
      map.addLayer({
        id: "weather-dome",
        type: "fill-extrusion",
        source: "weather",
        paint: {
          "fill-extrusion-color": ["get", "rgba"],
          "fill-extrusion-height": ["get", "height"],
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 1,
        },
      });

      // Motion trails
      map.addLayer({
        id: "unit-trails",
        type: "line",
        source: "trails",
        layout: { "line-cap": "round" },
        paint: {
          "line-width": 1.6,
          "line-color": ["get", "color"],
          "line-opacity": 0.55,
          "line-gradient": [
            "interpolate",
            ["linear"],
            ["line-progress"],
            0,
            "rgba(255,255,255,0)",
            1,
            "rgba(255,255,255,0.7)",
          ],
        },
      });

      // Planned routes
      map.addLayer({
        id: "routes-line",
        type: "line",
        source: "routes",
        paint: {
          "line-color": ["get", "color"],
          "line-width": 2,
          "line-opacity": 0.9,
          "line-dasharray": [2, 2],
        },
      });

      // Incident ground rings
      map.addLayer({
        id: "incident-rings",
        type: "circle",
        source: "incidents",
        paint: {
          "circle-radius": ["get", "r"],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.06,
          "circle-stroke-color": ["get", "color"],
          "circle-stroke-width": 1.4,
          "circle-stroke-opacity": ["get", "op"],
        },
      });
      map.addLayer({
        id: "incident-core",
        type: "circle",
        source: "incidents",
        paint: {
          "circle-radius": 3.5,
          "circle-color": ["get", "color"],
          "circle-opacity": 0.95,
        },
      });

      map.addLayer({
        id: "waypoint-dots",
        type: "circle",
        source: "waypoints",
        paint: {
          "circle-radius": 4,
          "circle-color": "#0A0A0A",
          "circle-stroke-color": "#FFFFFF",
          "circle-stroke-width": 2,
        },
      });

      map.on("click", "incident-core", (e: MapMouseEvent & { features?: Feature[] }) => {
        const id = e.features?.[0]?.properties?.["id"];
        if (id) cbRef.current.onSelectIncident?.(String(id));
      });
      map.on("mouseenter", "incident-core", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "incident-core", () => (map.getCanvas().style.cursor = ""));

      // Strategic supply corridors
      map.addSource("corridors", { type: "geojson", data: fc([]) });
      map.addLayer({
        id: "corridors-glow",
        type: "line",
        source: "corridors",
        paint: {
          "line-color": ["get", "color"],
          "line-width": 4,
          "line-opacity": 0.35,
          "line-blur": 2,
        },
      });
      map.addLayer({
        id: "corridors-line",
        type: "line",
        source: "corridors",
        paint: {
          "line-color": ["get", "color"],
          "line-width": 2,
          "line-opacity": 0.85,
        },
      });

      // Setup dedicated weather observation cloud & wind layers
      setupWeatherMapLibreLayers(map);

      setCurrentZoom(map.getZoom());
      setReady(true);
    };
    map.on("style.load", initLayers);

    map.on("click", (e: MapMouseEvent) => {
      void simStore.fetchWeatherForLocation(e.lngLat.lat, e.lngLat.lng);
      cbRef.current.onMapClick?.([e.lngLat.lat, e.lngLat.lng]);
    });
    map.on("rotate", () => setBearing(map.getBearing()));
    map.on("zoom", () => setCurrentZoom(map.getZoom()));
    map.on("moveend", () => {
      const c = map.getCenter();
      viewRef.current = { center: [c.lng, c.lat], zoom: map.getZoom() };
      setCurrentZoom(map.getZoom());
    });

    return () => {
      if (animRafRef.current) cancelAnimationFrame(animRafRef.current);
      animRafRef.current = null;
      unitAnimRef.current = {};
      Object.values(markersRef.current).forEach((m) => m.remove());
      markersRef.current = {};
      Object.values(clusterMarkers.current).forEach((m) => m.remove());
      clusterMarkers.current = {};
      Object.values(depotMarkers.current).forEach((m) => m.remove());
      depotMarkers.current = {};
      Object.values(cursorMarkers.current).forEach((m) => m.remove());
      cursorMarkers.current = {};
      Object.values(stationMarkers.current).forEach((m) => m.remove());
      stationMarkers.current = {};
      trailBufferRef.current.clear();
      window.clearTimeout(loadFallback);
      map.remove();

      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [basemap, mapConfigVer]);

  /* ---------- zones ---------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    if (!zonesVisible) {
      (map.getSource("zones") as maplibregl.GeoJSONSource | undefined)?.setData(fc([]));
      (map.getSource("zone-lines") as maplibregl.GeoJSONSource | undefined)?.setData(fc([]));
      return;
    }
    const color = (k: Zone["kind"]) =>
      k === "restricted" ? "#F87171" : k === "threat" ? "#FB923C" : "#8A8A8A";
    const polys = zones.map((z) => ({
      type: "Feature" as const,
      properties: { color: color(z.kind), height: z.kind === "restricted" ? 50 : 8, name: z.name },
      geometry: {
        type: "Polygon" as const,
        coordinates: [
          [...z.points.map(([la, lo]) => [lo, la]), [z.points[0]![1], z.points[0]![0]]],
        ],
      },
    }));
    (map.getSource("zones") as maplibregl.GeoJSONSource | undefined)?.setData(fc(polys));
    (map.getSource("zone-lines") as maplibregl.GeoJSONSource | undefined)?.setData(
      fc(
        zones.map((z) => ({
          type: "Feature",
          properties: { color: color(z.kind) },
          geometry: {
            type: "LineString",
            coordinates: [
              ...z.points.map(([la, lo]) => [lo, la]),
              [z.points[0]![1], z.points[0]![0]],
            ],
          },
        })),
      ),
    );
  }, [zones, zonesVisible, ready]);

  /* ---------- strategic supply corridors ---------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const src = map.getSource("corridors") as maplibregl.GeoJSONSource | undefined;
    if (!src) return;
    if (!supplyCorridorsVisible || !isPanIndia) {
      src.setData(fc([]));
      return;
    }
    const features: Feature[] = STRATEGIC_SUPPLY_CORRIDORS.map((c) => ({
      type: "Feature",
      properties: {
        id: c.id,
        name: c.name,
        color: c.color,
        category: c.category,
      },
      geometry: {
        type: "LineString",
        coordinates: c.points.map(([la, lo]) => [lo, la]),
      },
    }));
    src.setData(fc(features));
  }, [supplyCorridorsVisible, isPanIndia, ready]);

  /* ---------- weather domes ---------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("weather") as maplibregl.GeoJSONSource | undefined)?.setData(
      fc(
        weather.map((w) => ({
          type: "Feature",
          properties: {
            height: 150 + w.intensity * 650,
            rgba: `rgba(100,116,139,${(0.25 + w.intensity * 0.15).toFixed(2)})`,
          },
          geometry: { type: "Polygon", coordinates: [ringPolygon(w.lat, w.lon, w.radiusM)] },
        })),
      ),
    );
  }, [weather, ready]);

  /* ---------- Clear movement trails on world / scenario change ---------- */
  useEffect(() => {
    trailBufferRef.current.clear();
    const map = mapRef.current;
    if (map && ready) {
      (map.getSource("trails") as maplibregl.GeoJSONSource | undefined)?.setData(fc([]));
    }
  }, [worldMode, activeBranchId, currentScenarioId, ready]);

  /* ---------- Dedicated Weather Cloud & Wind Vector Layers ---------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const cloudsOuterSrc = map.getSource("weather-clouds-outer") as maplibregl.GeoJSONSource | undefined;
    const cloudsMidSrc = map.getSource("weather-clouds-mid") as maplibregl.GeoJSONSource | undefined;
    const cloudsInnerSrc = map.getSource("weather-clouds-inner") as maplibregl.GeoJSONSource | undefined;
    const cloudsOutlineSrc = map.getSource("weather-clouds-outline") as maplibregl.GeoJSONSource | undefined;
    const rainBandsSrc = map.getSource("weather-rain-bands") as maplibregl.GeoJSONSource | undefined;
    const windVectorsSrc = map.getSource("weather-wind-vectors") as maplibregl.GeoJSONSource | undefined;

    if (!cloudsOuterSrc) return;

    // Remove weather clouds in live map (baseline) while showing simulated weather clouds in simulation world model!
    // Operators can also manually toggle weather clouds via the CLOUDS button in MapLayerControls in either mode.
    const showSimulatedClouds =
      worldMode === "simulation"
        ? weatherLayerVisible !== false
        : weatherLayerVisible === true;

    if (!showSimulatedClouds || !envContext?.stations) {
      cloudsOuterSrc.setData(fc([]));
      cloudsMidSrc?.setData(fc([]));
      cloudsInnerSrc?.setData(fc([]));
      cloudsOutlineSrc?.setData(fc([]));
      rainBandsSrc?.setData(fc([]));
      windVectorsSrc?.setData(fc([]));
      return;
    }

    const stationsList = Object.values(envContext.stations);
    const geo = buildWeatherCloudGeoJson(stationsList, selectedWeather, cloudOpacity);

    cloudsOuterSrc.setData(geo.cloudsOuter);
    cloudsMidSrc?.setData(geo.cloudsMid);
    cloudsInnerSrc?.setData(geo.cloudsInner);
    cloudsOutlineSrc?.setData(geo.cloudsOutline);
    rainBandsSrc?.setData(geo.rainBands);

    if (windVectorsVisible || (worldMode === "simulation" && windVectorsVisible !== false)) {
      windVectorsSrc?.setData(geo.windVectors);
    } else {
      windVectorsSrc?.setData(fc([]));
    }
  }, [envContext, selectedWeather, weatherLayerVisible, worldMode, cloudOpacity, windVectorsVisible, ready]);

  /* ---------- routes + waypoints ---------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    (map.getSource("routes") as maplibregl.GeoJSONSource | undefined)?.setData(
      fc(
        routes.map((r) => ({
          type: "Feature",
          properties: { color: r.color },
          geometry: { type: "LineString", coordinates: r.points.map(([la, lo]) => [lo, la]) },
        })),
      ),
    );
    (map.getSource("waypoints") as maplibregl.GeoJSONSource | undefined)?.setData(
      fc(
        waypoints.map((w, i) => ({
          type: "Feature",
          properties: { i: i + 1 },
          geometry: { type: "Point", coordinates: [w[1], w[0]] },
        })),
      ),
    );
  }, [routes, waypoints, ready]);

  /* ---------- incidents (animated rings) ---------- */
  const incidentsRef = useRef(incidents);
  incidentsRef.current = incidents;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    let raf = 0;
    const start = performance.now();
    const frame = (t: number) => {
      const phase = ((t - start) / 2400) % 1;
      const src = map.getSource("incidents") as maplibregl.GeoJSONSource | undefined;
      src?.setData(
        fc(
          incidentsRef.current.map((inc) => {
            const critical = inc.severity === "critical";
            const p = critical ? phase : Math.min(1, (t - start) / 2400);
            return {
              type: "Feature",
              properties: {
                id: inc.id,
                color: SEVERITY_META[inc.severity].color,
                r: 8 + p * 26,
                op: Math.max(0, 0.75 * (1 - p)),
              },
              geometry: { type: "Point", coordinates: [inc.lon, inc.lat] },
            };
          }),
        ),
      );
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [ready]);

  /* ---------- units: DOM markers + movement trails ---------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const seen = new Set<string>();
    const personnel = simStore.getState().world.personnel;

    for (const u of units) {
      seen.add(u.id);
      const stale = isStale(u, tick);
      const color = unitColor(u);

      trailBufferRef.current.record(u.id, u.lon, u.lat);
      const trail = trailBufferRef.current.get(u.id);
      const moving = isUnitMoving(u);
      const heading = getUnitHeading(u, trail);

      let marker = markersRef.current[u.id];
      if (!marker) {
        const el = document.createElement("div");
        el.className = "doip-unit-marker";
        el.innerHTML = `<span class="doip-unit-heading"></span><span class="doip-unit-stem"></span><span class="doip-unit-shadow"></span><span class="doip-unit-dot"></span><span class="doip-unit-label"></span>`;
        el.addEventListener("click", (ev) => {
          ev.stopPropagation();
          cbRef.current.onSelectUnit?.(u.id);
        });
        marker = new maplibregl.Marker({ element: el, anchor: "bottom" })
          .setLngLat([u.lon, u.lat])
          .addTo(map);
        markersRef.current[u.id] = marker;
      } else {
        const cur = marker.getLngLat();
        const dLon = Math.abs(cur.lng - u.lon);
        const dLat = Math.abs(cur.lat - u.lat);
        if (dLon > 0.00001 || dLat > 0.00001) {
          unitAnimRef.current[u.id] = {
            start: [cur.lng, cur.lat],
            target: [u.lon, u.lat],
            startTime: performance.now(),
            duration: 350,
          };
        }
      }
      const el = marker.getElement();
      if (!el.querySelector(".doip-unit-heading")) {
        const hSpan = document.createElement("span");
        hSpan.className = "doip-unit-heading";
        el.prepend(hSpan);
      }
      const elevated = u.kind === "uav";
      el.classList.toggle("is-elevated", elevated);
      el.classList.toggle("is-stale", stale);
      el.classList.toggle("is-moving", moving);
      el.classList.toggle("is-halted", !moving && !stale);
      el.classList.toggle("is-selected", selectedId === u.id);
      el.style.setProperty("--unit-color", color);
      el.style.setProperty("--unit-heading", `${heading}deg`);

      const isNational = currentZoom < 5.8;
      const isLocal = currentZoom >= 9.5;
      if (!unitsVisible || (isNational && isPanIndia)) {
        el.style.display = "none";
      } else {
        el.style.display = "block";
      }

      const label = el.querySelector(".doip-unit-label");
      if (label) {
        const baseName = unitDesignator(u, personnel);
        const countSuffix = u.personnelCount ? ` [${u.personnelCount}p]` : "";
        label.textContent = isLocal ? `${baseName}${countSuffix}` : baseName;
      }
    }

    const animLoop = (time: number) => {
      let hasActive = false;
      for (const [id, anim] of Object.entries(unitAnimRef.current)) {
        const m = markersRef.current[id];
        if (!m) continue;
        const progress = Math.min(1, (time - anim.startTime) / anim.duration);
        const ease = 1 - Math.pow(1 - progress, 2);
        const lng = anim.start[0] + (anim.target[0] - anim.start[0]) * ease;
        const lat = anim.start[1] + (anim.target[1] - anim.start[1]) * ease;
        m.setLngLat([lng, lat]);
        if (progress < 1) {
          hasActive = true;
        } else {
          delete unitAnimRef.current[id];
        }
      }
      if (hasActive) {
        animRafRef.current = requestAnimationFrame(animLoop);
      } else {
        animRafRef.current = null;
      }
    };
    if (Object.keys(unitAnimRef.current).length > 0 && !animRafRef.current) {
      animRafRef.current = requestAnimationFrame(animLoop);
    }

    trailBufferRef.current.prune(seen);
    for (const id of Object.keys(markersRef.current)) {
      if (!seen.has(id)) {
        markersRef.current[id]?.remove();
        delete markersRef.current[id];
      }
    }

    if (movementTrailsVisible) {
      (map.getSource("trails") as maplibregl.GeoJSONSource | undefined)?.setData(
        trailBufferRef.current.toGeoJson(selectedId),
      );
    } else {
      (map.getSource("trails") as maplibregl.GeoJSONSource | undefined)?.setData(fc([]));
    }
  }, [units, tick, selectedId, movementTrailsVisible, unitsVisible, currentZoom, isPanIndia, personnel, ready]);

  /* ---------- National Overview: Regional Cluster Badges ---------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const isNationalZoom = currentZoom < 5.8;

    if (!isNationalZoom || !clusterBadgesVisible || !isPanIndia) {
      Object.values(clusterMarkers.current).forEach((m) => m.remove());
      clusterMarkers.current = {};
      return;
    }

    const seen = new Set<string>();
    const sectorKeys = Object.keys(INDIAN_SECTORS);

    for (const secKey of sectorKeys) {
      seen.add(secKey);
      const sec = INDIAN_SECTORS[secKey];
      if (!sec) continue;

      const sectorUnits = units.filter((u) => u.sector === secKey);
      const sectorPersonnel = personnel.filter((p) => p.sector === secKey);
      const stn = envContext?.stations?.[sec.weatherStationId];

      const patrolsCount = sectorUnits.filter((u) => u.kind === "patrol").length;
      const uavCount = sectorUnits.filter((u) => u.kind === "uav").length;
      const convoyCount = sectorUnits.filter((u) => u.kind === "convoy").length;

      let marker = clusterMarkers.current[secKey];
      if (!marker) {
        const el = document.createElement("div");
        el.className = "doip-sector-cluster-badge";
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          map.flyTo({
            center: [sec.lon, sec.lat],
            zoom: 7.2,
            duration: 1000,
            pitch: is3d ? DEFAULT_PITCH : 0,
          });
          setActiveSector(secKey);
        });

        marker = new maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat([sec.lon, sec.lat])
          .addTo(map);
        clusterMarkers.current[secKey] = marker;
      }

      const el = marker.getElement();
      const facilityTypeName = (sec.facilityType || "DEPOT").toUpperCase().replace("_", " ");
      const tempStr = stn ? `${stn.temperatureC.toFixed(0)}°C` : "--°C";
      const conditionStr = stn ? stn.conditionLabel : "Clear";

      el.innerHTML = `
        <div class="doip-cluster-header">
          <span>${secKey} SECTOR</span>
          <span class="text-[8px] px-1 py-0.2 bg-sky-950 text-sky-300 border border-sky-800">CLICK TO ZOOM</span>
        </div>
        <div class="doip-cluster-stats">
          <div class="doip-cluster-stat-row">
            <span>UNITS:</span>
            <span class="doip-cluster-stat-val text-sky-300">${sectorUnits.length} (${patrolsCount}P • ${uavCount}U • ${convoyCount}C)</span>
          </div>
          <div class="doip-cluster-stat-row">
            <span>PERSONNEL:</span>
            <span class="doip-cluster-stat-val text-emerald-300">${sectorPersonnel.length} active</span>
          </div>
          <div class="doip-cluster-stat-row">
            <span>FACILITY:</span>
            <span class="doip-cluster-stat-val text-amber-300 truncate max-w-[90px]" title="${sec.depotName}">${facilityTypeName}</span>
          </div>
        </div>
        <div class="doip-cluster-weather-pill">
          <span>☁ ${tempStr} • ${conditionStr}</span>
        </div>
      `;
    }

    for (const key of Object.keys(clusterMarkers.current)) {
      if (!seen.has(key)) {
        clusterMarkers.current[key]?.remove();
        delete clusterMarkers.current[key];
      }
    }
  }, [currentZoom, clusterBadgesVisible, isPanIndia, units, personnel, depots, envContext, is3d, ready]);

  /* ---------- Strategic Facilities & Depots on Map ---------- */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const isNationalZoom = currentZoom < 5.8;

    if (!facilitiesVisible || (isNationalZoom && isPanIndia)) {
      Object.values(depotMarkers.current).forEach((m) => m.remove());
      depotMarkers.current = {};
      return;
    }

    const seen = new Set<string>();
    const facilityIcon = (ft?: string) => {
      switch (ft) {
        case "airbase": return "✈";
        case "naval_anchorage": return "⚓";
        case "forward_operating_base": return "🛡";
        default: return "📦";
      }
    };

    for (const d of depots) {
      seen.add(d.id);
      let marker = depotMarkers.current[d.id];
      if (!marker) {
        const el = document.createElement("div");
        el.className = "doip-facility-marker";
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          map.flyTo({ center: [d.lon, d.lat], zoom: Math.max(currentZoom, 8.5), duration: 800 });
        });
        marker = new maplibregl.Marker({ element: el, anchor: "bottom" })
          .setLngLat([d.lon, d.lat])
          .addTo(map);
        depotMarkers.current[d.id] = marker;
      }

      const el = marker.getElement();
      const icon = facilityIcon(d.facilityType);
      const fuelPct = d.capacity?.fuel ? Math.round((d.stock.fuel / d.capacity.fuel) * 100) : 100;
      const fType = (d.facilityType || "depot").toUpperCase().replace("_", " ");

      el.innerHTML = `
        <span class="doip-facility-icon text-emerald-400 font-bold">${icon}</span>
        <div class="flex flex-col">
          <span class="doip-facility-tag">${d.name.split(" ")[0]} ${fType}</span>
          <span class="doip-facility-stock">⛽ ${fuelPct}% | 🩺 ${d.stock.medkit || 0} | ⚡ ${d.stock.battery || 0}</span>
        </div>
      `;
    }

    for (const key of Object.keys(depotMarkers.current)) {
      if (!seen.has(key)) {
        depotMarkers.current[key]?.remove();
        delete depotMarkers.current[key];
      }
    }
  }, [depots, facilitiesVisible, currentZoom, isPanIndia, ready]);


  /* ---------- collaborator cursors ---------- */
  const cursorMarkers = useRef<Record<string, maplibregl.Marker>>({});
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    const seen = new Set<string>();
    for (const c of cursors) {
      seen.add(c.id);
      let m = cursorMarkers.current[c.id];
      if (!m) {
        const el = document.createElement("div");
        el.className = "doip-cursor";
        el.innerHTML = `<span class="doip-cursor-dot"></span><span class="doip-cursor-name"></span>`;
        m = new maplibregl.Marker({ element: el }).setLngLat([c.lon, c.lat]).addTo(map);
        cursorMarkers.current[c.id] = m;
      }
      m.setLngLat([c.lon, c.lat]);
      const el = m.getElement();
      el.style.setProperty("--cursor-color", c.color);
      const n = el.querySelector(".doip-cursor-name");
      if (n) n.textContent = c.name;
    }
    for (const id of Object.keys(cursorMarkers.current)) {
      if (!seen.has(id)) {
        cursorMarkers.current[id]?.remove();
        delete cursorMarkers.current[id];
      }
    }
  }, [cursors, ready]);

  /* ---------- Pan-India Meteorological Observation Stations on Map ---------- */
  const stationMarkers = useRef<Record<string, maplibregl.Marker>>({});
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !envContext?.stations) return;
    const seen = new Set<string>();

    for (const stn of Object.values(envContext.stations)) {
      seen.add(stn.id);
      let m = stationMarkers.current[stn.id];
      const isSevere = Boolean(stn.severeAlert);
      const tempColor =
        stn.temperatureC <= 0
          ? "text-cyan-300"
          : stn.temperatureC >= 35
            ? "text-amber-400"
            : "text-sky-400";

      const classification = classifyWeatherCondition(
        stn.temperatureC,
        stn.precipitationMm,
        stn.weatherCode,
        stn.conditionLabel,
        stn.windSpeedKph,
        stn.cloudPct ?? 30,
      );

      const borderColor =
        classification.category === "thunderstorm"
          ? "border-purple-500/90 bg-[rgba(26,12,38,0.92)] shadow-[0_0_12px_rgba(168,85,247,0.4)]"
          : classification.category === "rainy"
            ? "border-sky-500/80 bg-[rgba(6,24,44,0.92)] shadow-[0_0_10px_rgba(14,165,233,0.35)]"
            : classification.category === "windy"
              ? "border-teal-500/80 bg-[rgba(6,36,32,0.92)] shadow-[0_0_10px_rgba(20,184,166,0.35)]"
              : classification.category === "snow"
                ? "border-cyan-400/90 bg-[rgba(8,30,44,0.92)] shadow-[0_0_10px_rgba(56,189,248,0.35)]"
                : classification.category === "heat"
                  ? "border-amber-500/90 bg-[rgba(38,20,6,0.92)] shadow-[0_0_10px_rgba(245,158,11,0.35)]"
                  : classification.category === "cloudy"
                    ? "border-zinc-500/70 bg-[rgba(18,18,18,0.92)]"
                    : "border-zinc-700/60 bg-[rgba(12,12,12,0.88)]";

      const badgeText = `${classification.icon} ${classification.categoryLabel.toUpperCase()}`;

      if (!m) {
        const el = document.createElement("div");
        el.className = "doip-station-marker group cursor-pointer pointer-events-auto select-none";
        el.innerHTML = `
          <div class="flex items-center gap-1.5 border ${borderColor} hover:border-white px-1.5 py-0.5 shadow-lg backdrop-blur-sm transition-all rounded-sm">
            <span class="size-1.5 rounded-full ${classification.category === 'thunderstorm' || isSevere ? 'bg-purple-400 animate-ping' : classification.category === 'rainy' ? 'bg-sky-400 animate-pulse' : classification.category === 'windy' ? 'bg-teal-400 animate-pulse' : 'bg-emerald-400'}"></span>
            <span class="font-mono text-[9px] font-bold text-zinc-200 group-hover:text-white uppercase tracking-wider">${stn.name.split(" ")[0]}</span>
            <span class="font-mono text-[9px] font-extrabold ${tempColor}">${stn.temperatureC.toFixed(0)}°</span>
            <span class="font-mono text-[8px] font-semibold text-zinc-300 border-l border-zinc-700/80 pl-1">${badgeText}</span>
          </div>
        `;
        el.onclick = (e) => {
          e.stopPropagation();
          map.easeTo({ center: [stn.lon, stn.lat], zoom: 7.5, duration: 600 });
          void simStore.fetchWeatherForLocation(stn.lat, stn.lon);
        };
        m = new maplibregl.Marker({ element: el }).setLngLat([stn.lon, stn.lat]).addTo(map);
        stationMarkers.current[stn.id] = m;
      } else {
        m.setLngLat([stn.lon, stn.lat]);
      }
    }

    for (const id of Object.keys(stationMarkers.current)) {
      if (!seen.has(id)) {
        stationMarkers.current[id]?.remove();
        delete stationMarkers.current[id];
      }
    }
  }, [envContext, ready]);

  /* ---------- focus / pulse flyTo ---------- */
  useEffect(() => {
    const map = mapRef.current;
    const target = focus ?? pulseAt;
    if (!map || !ready || !target) return;
    map.flyTo({
      center: [target[1], target[0]],
      zoom: Math.max(map.getZoom(), 13.5),
      pitch: is3d ? DEFAULT_PITCH : 0,
      duration: 1200,
      essential: true,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, pulseAt, ready]);

  /* ---------- radar sweep anchor (imperative: avoids render loops) ---------- */
  const [clat, clon] = [center[0], center[1]];
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready || !radar) return;
    const update = () => {
      const el = radarRef.current;
      if (!el) return;
      const p = map.project([clon, clat]);
      el.style.left = `${p.x}px`;
      el.style.top = `${p.y}px`;
    };
    update();
    map.on("move", update);
    map.on("resize", update);
    return () => {
      map.off("move", update);
      map.off("resize", update);
    };
  }, [ready, radar, clat, clon]);

  const toggle3d = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;
    const next = !is3d;
    setIs3d(next);
    map.easeTo({
      pitch: next ? DEFAULT_PITCH : 0,
      bearing: next ? DEFAULT_BEARING : 0,
      duration: 700,
    });
  }, [is3d]);

  const resetNorth = useCallback(() => {
    mapRef.current?.easeTo({ bearing: 0, duration: 500 });
  }, []);

  const pickBasemap = useCallback((b: Basemap) => {
    setBasemap((prev) => {
      if (prev === b) return prev;
      try {
        window.localStorage.setItem(BASEMAP_KEY, b);
      } catch {
        /* storage unavailable */
      }
      return b;
    });
  }, []);

  return (
    <div className={`relative h-full w-full ${className ?? ""}`} style={{ background: "#0A0A0A" }}>
      <div ref={containerRef} className="h-full w-full" />
      {radar && <div ref={radarRef} className="doip-radar-sweep" aria-hidden />}
      {tilesLoading && (
        <div className="pointer-events-none absolute left-3 bottom-3 z-10 font-mono text-[11px] uppercase tracking-[0.1em] text-[#8A8A8A]">
          Loading tiles
        </div>
      )}
      <div className="absolute right-2 top-16 z-10 flex flex-col items-end gap-1">
        <div className="flex border border-[#2A2A2A] bg-[rgba(13,13,13,0.82)] backdrop-blur-[16px]">
          {(["imagery", "dark"] as Basemap[]).map((b) => (
            <button
              key={b}
              onClick={() => pickBasemap(b)}
              className={`px-1.5 py-1 font-mono text-[10px] uppercase tracking-[0.1em] ${
                basemap === b ? "bg-white text-black" : "text-[#8A8A8A]"
              }`}
            >
              {b === "imagery" ? "IMAGERY" : "DARK"}
            </button>
          ))}
        </div>
        <button
          onClick={resetNorth}
          title="Reset north"
          className="doip-map-btn"
          style={{ ["--compass-rot" as string]: `${-bearing}deg` }}
        >
          <Compass className="size-3.5" style={{ transform: `rotate(${-bearing}deg)` }} />
        </button>
        <button
          onClick={toggle3d}
          title={is3d ? "Switch to 2D" : "Switch to 3D"}
          className="doip-map-btn"
        >
          {is3d ? <Square className="size-3.5" /> : <Box className="size-3.5" />}
          <span className="font-mono text-[10px]">{is3d ? "2D" : "3D"}</span>
        </button>
        <button
          onClick={() => setKeyDialogOpen(true)}
          title="Map API Key & Provider Settings"
          className="doip-map-btn"
        >
          <Key className="size-3.5" />
        </button>
      </div>

      {/* Pan-India World Model & Sector Navigation Header Bar */}
      <div className="absolute left-2 top-2 z-10 flex max-w-[calc(100%-120px)] flex-wrap items-center gap-1.5 font-mono text-[11px]">
        {/* World Mode Indicator */}
        {worldMode === "simulation" ? (
          <div className="flex items-center gap-1.5 border border-amber-500/70 bg-[rgba(22,12,6,0.94)] px-2.5 py-1 text-amber-300 shadow-xl backdrop-blur-md">
            <span className="size-2 rounded-full bg-rose-500 animate-pulse" />
            <span className="font-bold tracking-wider text-rose-300">ARTIFICIAL IMPACT SIMULATION WORLD</span>
            <span className="text-[10px] text-amber-400/90 border-l border-amber-800/80 pl-1.5 font-semibold">
              {activeBranchId ?? "BRANCH-ISOLATED"}
            </span>

            {/* Inline Scenario Switcher Dropdown */}
            <div className="flex items-center gap-1 border-l border-amber-700/60 pl-1.5">
              <span className="text-[9px] uppercase tracking-wider text-amber-400 font-semibold">SCENARIO:</span>
              <select
                value={currentScenarioId}
                onChange={(e) => {
                  const chosenId = e.target.value;
                  const match = ARTIFICIAL_SCENARIOS.find((s) => s.id === chosenId);
                  simStore.forkSimulation(chosenId);
                  if (match) {
                    setActiveSector(match.sector);
                    mapRef.current?.easeTo({
                      center: match.center,
                      zoom: match.zoom,
                      pitch: is3d ? DEFAULT_PITCH : 0,
                      duration: 1000,
                    });
                  }
                }}
                className="bg-black/85 border border-amber-500/60 px-1.5 py-0.5 text-[10px] text-amber-200 font-mono outline-none cursor-pointer hover:border-amber-400 transition-colors"
                title="Switch Artificial Impact Scenario"
              >
                {ARTIFICIAL_SCENARIOS.map((sc) => (
                  <option key={sc.id} value={sc.id} className="bg-zinc-950 text-amber-200">
                    {sc.label}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => {
                simStore.resetToBaseline();
                setActiveSector("ALL-IN");
                mapRef.current?.easeTo({
                  center: [78.9629, 22.5937],
                  zoom: 4.8,
                  pitch: is3d ? DEFAULT_PITCH : 0,
                  duration: 1000,
                });
              }}
              title="Instant Reset to Pan-India Real World Baseline"
              className="ml-1 flex items-center gap-1 bg-rose-500/20 px-2 py-0.5 text-[10px] font-semibold text-rose-200 hover:bg-rose-500/40 border border-rose-500/50 transition-colors"
            >
              <RotateCcw className="size-3" /> RESET BASELINE
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 border border-emerald-500/60 bg-[rgba(8,18,12,0.94)] px-2.5 py-1 text-emerald-300 shadow-xl backdrop-blur-md">
            <span className="size-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="font-bold tracking-wider text-emerald-300">REAL WORLD MODEL: PAN-INDIA LIVE CONTEXT</span>
            <span className="text-[10px] text-emerald-400/90 border-l border-emerald-800/80 pl-1.5 font-semibold">
              BASELINE
            </span>
            <span className="bg-emerald-950/90 text-emerald-300 border border-emerald-700/80 px-1.5 py-0.2 text-[9px] font-medium">
              {envContext?.stationsCount ?? 11} STATIONS LIVE
            </span>
            <span className="bg-emerald-950/90 text-emerald-400 border border-emerald-800/80 px-1 py-0.2 text-[9px]">
              {envContext?.globalProvenance ?? "REAL_FORECAST"}
            </span>
            <button
              onClick={() => {
                simStore.forkSimulation("IN-SC-CASCADE");
                setActiveSector("ALL-IN");
                mapRef.current?.easeTo({
                  center: [78.9629, 22.5937],
                  zoom: 4.8,
                  pitch: is3d ? DEFAULT_PITCH : 0,
                  duration: 1000,
                });
              }}
              title="Fork Isolated Artificial Impact Simulation World"
              className="ml-1 flex items-center gap-1 bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-200 hover:bg-emerald-500/40 border border-emerald-500/50 transition-colors"
            >
              ⚡ FORK SIMULATION WORLD
            </button>
          </div>
        )}

        {/* Sector Quick-Jump Toolbar */}
        <div className="hidden sm:flex items-center border border-[#2A2A2A] bg-[rgba(10,10,10,0.88)] px-1 py-0.5 shadow-lg backdrop-blur-md">
          <span className="px-1 text-[9px] uppercase tracking-wider text-zinc-500">SECTORS:</span>
          {SECTOR_PRESETS.map((sec) => (
            <button
              key={sec.label}
              onClick={() => jumpToSector(sec)}
              className={`px-1.5 py-0.5 text-[10px] uppercase tracking-wide transition-colors ${
                activeSector === sec.label
                  ? "bg-white text-black font-semibold"
                  : "text-zinc-400 hover:text-white"
              }`}
              title={sec.name}
            >
              {sec.label}
            </button>
          ))}
        </div>

        {/* Unified Map Layer & Weather Footprint Controls */}
        <MapLayerControls />

        {/* Live Weather / Met Context Trigger */}
        <button
          onClick={() => setMetDrawerOpen((o) => !o)}
          title="Toggle Pan-India Real Meteorological Observations"
          className="flex items-center gap-1 border border-zinc-700 bg-[rgba(10,10,10,0.88)] px-2 py-1 text-zinc-300 hover:text-white shadow-lg backdrop-blur-md"
        >
          <Cloud className="size-3.5 text-sky-400" />
          <span className="text-[10px] font-semibold">MET CONTEXT</span>
          <span className="rounded bg-sky-950 px-1 py-0.2 text-[9px] text-sky-300 border border-sky-800">
            {envContext?.stationsCount ?? 11} STNS
          </span>
        </button>
      </div>

      {/* Floating Meteorological Context Flyout */}
      {metDrawerOpen && envContext && (
        <div className="absolute left-2 top-11 z-20 max-h-[75vh] w-80 overflow-y-auto border border-[#2A2A2A] bg-[rgba(10,10,10,0.96)] p-2.5 font-mono text-zinc-300 shadow-2xl backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5 mb-2">
            <div>
              <span className="text-xs font-bold text-white tracking-wider">PAN-INDIA MET CONTEXT</span>
              <div className="text-[9px] text-zinc-400">
                PROVENANCE: <span className="text-emerald-400">{envContext.globalProvenance}</span>
              </div>
            </div>
            <button
              onClick={() => setMetDrawerOpen(false)}
              className="text-zinc-500 hover:text-white text-xs px-1"
            >
              ✕
            </button>
          </div>
          <div className="space-y-1.5 text-[11px]">
            {Object.values(envContext.stations).map((stn) => (
              <div
                key={stn.id}
                onClick={() => {
                  mapRef.current?.easeTo({ center: [stn.lon, stn.lat], zoom: 7.5, duration: 800 });
                  void simStore.fetchWeatherForLocation(stn.lat, stn.lon);
                }}
                className="border border-zinc-900 bg-zinc-950/60 p-1.5 flex flex-col gap-0.5 hover:border-sky-500/60 transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-zinc-200 group-hover:text-sky-300 transition-colors">{stn.name}</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] font-bold text-sky-400">{stn.temperatureC}°C</span>
                    <span className="text-[9px] bg-sky-950/90 text-sky-300 border border-sky-800/80 px-1 py-0.2 group-hover:bg-sky-900">
                      LIVE
                    </span>
                  </div>
                </div>
                <div className="flex items-center justify-between text-[10px] text-zinc-400">
                  <span>{stn.region}</span>
                  <span>{stn.conditionLabel}</span>
                </div>
                <div className="flex items-center justify-between text-[9px] text-zinc-500 pt-0.5">
                  <span>Wind: {stn.windSpeedKph} km/h</span>
                  <span>Clouds: {stn.cloudPct !== undefined ? `${stn.cloudPct}%` : "--"}</span>
                  <span className="text-emerald-500/80">{stn.provenance}</span>
                </div>
                {stn.severeAlert && (
                  <div className="mt-1 text-[9px] text-amber-300 bg-amber-950/50 border border-amber-800/60 px-1 py-0.5">
                    ⚠ {stn.severeAlert}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Floating Tactical Weather Inspection Card */}
      {(selectedWeather || weatherLoading || weatherError) && (
        <div className="absolute bottom-3 right-3 z-20 w-80 max-w-[calc(100vw-24px)] border border-sky-500/40 bg-[rgba(10,10,10,0.95)] p-3 font-mono text-zinc-300 shadow-2xl backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5 mb-2">
            <div className="flex items-center gap-1.5">
              <Cloud className="size-4 text-sky-400 shrink-0" />
              <div className="min-w-0">
                <div className="text-[11px] font-bold tracking-wider text-white truncate">
                  {selectedWeather?.resolved_name || (selectedWeather ? `${selectedWeather.lat.toFixed(2)}°, ${selectedWeather.lon.toFixed(2)}°` : "WEATHER OBSERVATION")}
                </div>
                <div className="text-[9px] text-zinc-400 truncate">
                  {selectedWeather?.region ? `${selectedWeather.region}, ` : ""}{selectedWeather?.country ?? "Subcontinent"}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {selectedWeather && (
                <button
                  onClick={() => simStore.fetchWeatherForLocation(selectedWeather.lat, selectedWeather.lon, true)}
                  title="Force refresh live observation from WeatherAPI.com"
                  disabled={weatherLoading}
                  className="p-1 text-zinc-400 hover:text-sky-300 hover:bg-zinc-800 transition-colors disabled:opacity-50"
                >
                  <RefreshCw className={`size-3.5 ${weatherLoading ? "animate-spin text-sky-400" : ""}`} />
                </button>
              )}
              <button
                onClick={() => simStore.clearSelectedLocationWeather()}
                title="Dismiss observation"
                className="p-1 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
              >
                <X className="size-3.5" />
              </button>
            </div>
          </div>

          {weatherLoading && !selectedWeather && (
            <div className="py-4 text-center text-xs text-sky-400 animate-pulse">
              Querying WeatherAPI.com live observation...
            </div>
          )}

          {weatherError && (
            <div className="mb-2 border border-amber-800/60 bg-amber-950/40 p-1.5 text-[10px] text-amber-300">
              ⚠ {weatherError}
            </div>
          )}

          {selectedWeather && (
            <div className="space-y-2">
              {/* Badges Row */}
              <div className="flex flex-wrap items-center gap-1 text-[9px]">
                <span className="border border-sky-800 bg-sky-950/80 px-1 py-0.5 font-semibold text-sky-300">
                  {selectedWeather.provider}
                </span>
                <span
                  className={`border px-1 py-0.5 font-semibold ${
                    selectedWeather.freshness === "fresh"
                      ? "border-emerald-800 bg-emerald-950/80 text-emerald-300"
                      : selectedWeather.freshness === "stale"
                        ? "border-amber-800 bg-amber-950/80 text-amber-300"
                        : "border-zinc-800 bg-zinc-900 text-zinc-300"
                  }`}
                >
                  {selectedWeather.freshness.toUpperCase()}
                  {selectedWeather.is_cached ? ` (${Math.round(selectedWeather.cache_age_seconds)}s)` : ""}
                </span>
                <span className="border border-zinc-700 bg-zinc-900 px-1 py-0.5 text-zinc-400">
                  {selectedWeather.provenance}
                </span>
              </div>

              {/* Temperature & Condition Highlight */}
              <div className="flex items-center justify-between bg-zinc-950/80 border border-zinc-900 p-2">
                <div>
                  <div className="text-2xl font-bold tracking-tight text-white">
                    {selectedWeather.temp_c !== null && selectedWeather.temp_c !== undefined
                      ? `${selectedWeather.temp_c.toFixed(1)}°C`
                      : "--"}
                    {selectedWeather.temp_f !== null && selectedWeather.temp_f !== undefined && (
                      <span className="ml-1.5 text-xs text-zinc-400 font-normal">
                        ({selectedWeather.temp_f.toFixed(1)}°F)
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-zinc-400">
                    Feels like: {selectedWeather.feelslike_c !== null && selectedWeather.feelslike_c !== undefined
                      ? `${selectedWeather.feelslike_c.toFixed(1)}°C`
                      : "--"}
                  </div>
                </div>

                <div className="flex flex-col items-end">
                  {selectedWeather.condition_icon && (
                    <img
                      src={selectedWeather.condition_icon.startsWith("//") ? `https:${selectedWeather.condition_icon}` : selectedWeather.condition_icon}
                      alt={selectedWeather.condition_text ?? "Condition"}
                      className="size-8 object-contain"
                    />
                  )}
                  <span className="text-[11px] font-semibold text-sky-300 text-right">
                    {selectedWeather.condition_text ?? "N/A"}
                  </span>
                </div>
              </div>

              {/* Multi-Parameter Environmental Grid */}
              <div className="grid grid-cols-2 gap-1.5 text-[10px]">
                <div className="border border-zinc-900 bg-zinc-950/40 p-1">
                  <span className="text-zinc-500">WIND:</span>{" "}
                  <span className="font-semibold text-zinc-200">
                    {selectedWeather.wind_kph ?? "--"} km/h {selectedWeather.wind_dir ?? ""}
                  </span>
                </div>
                <div className="border border-zinc-900 bg-zinc-950/40 p-1">
                  <span className="text-zinc-500">HUMIDITY:</span>{" "}
                  <span className="font-semibold text-zinc-200">
                    {selectedWeather.humidity_pct ?? "--"}%
                  </span>
                </div>
                <div className="border border-zinc-900 bg-zinc-950/40 p-1">
                  <span className="text-zinc-500">PRECIP:</span>{" "}
                  <span className="font-semibold text-zinc-200">
                    {selectedWeather.precip_mm ?? "0"} mm
                  </span>
                </div>
                <div className="border border-zinc-900 bg-zinc-950/40 p-1">
                  <span className="text-zinc-500">PRESSURE:</span>{" "}
                  <span className="font-semibold text-zinc-200">
                    {selectedWeather.pressure_mb ?? "--"} mb
                  </span>
                </div>
                <div className="border border-zinc-900 bg-zinc-950/40 p-1">
                  <span className="text-zinc-500">UV INDEX:</span>{" "}
                  <span className="font-semibold text-zinc-200">
                    {selectedWeather.uv_index ?? "--"}
                  </span>
                </div>
                <div className="border border-zinc-900 bg-zinc-950/40 p-1">
                  <span className="text-zinc-500">VISIBILITY:</span>{" "}
                  <span className="font-semibold text-zinc-200">
                    {selectedWeather.visibility_km ?? "--"} km
                  </span>
                </div>
              </div>

              {selectedWeather.stale_warning && (
                <div className="border border-amber-900/60 bg-amber-950/40 p-1 text-[9px] text-amber-300">
                  ⚠ {selectedWeather.stale_warning}
                </div>
              )}

              {/* Coordinates and Timestamp Footer */}
              <div className="flex items-center justify-between border-t border-zinc-900 pt-1 text-[9px] text-zinc-500">
                <span>
                  {selectedWeather.lat.toFixed(4)}°N, {selectedWeather.lon.toFixed(4)}°E
                </span>
                <span>
                  {selectedWeather.provider_localtime
                    ? `Local: ${selectedWeather.provider_localtime}`
                    : `UTC: ${selectedWeather.fetch_timestamp_utc.slice(11, 16)}`}
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      <MapKeyDialog open={keyDialogOpen} onOpenChange={setKeyDialogOpen} />
    </div>
  );
}
