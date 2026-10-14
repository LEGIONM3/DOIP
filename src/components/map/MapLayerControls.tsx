import React, { useState, useMemo } from "react";
import { simStore, useSim } from "@/sim/store";
import { WEATHER_FOOTPRINT_DISCLAIMER, classifyWeatherCondition, type WeatherCategory } from "./weatherLayers";
import {
  Cloud,
  Wind,
  Navigation,
  Eye,
  Sliders,
  Info,
  Shield,
  Layers,
  X,
  Zap,
  Building2,
  Waypoints,
  Users,
  MapPin,
  Route,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { INDIAN_SECTORS, STRATEGIC_SUPPLY_CORRIDORS } from "@/sim/engine";

export interface MapLayerControlsProps {
  className?: string;
  compact?: boolean;
}

export function MapLayerControls({ className, compact = false }: MapLayerControlsProps) {
  const weatherVisible = useSim((s) => s.weatherLayerVisible);
  const cloudOpacity = useSim((s) => s.cloudOpacity);
  const trailsVisible = useSim((s) => s.movementTrailsVisible);
  const windVectorsVisible = useSim((s) => s.windVectorsVisible);
  const facilitiesVisible = useSim((s) => s.facilitiesVisible);
  const supplyCorridorsVisible = useSim((s) => s.supplyCorridorsVisible);
  const zonesVisible = useSim((s) => s.zonesVisible);
  const unitsVisible = useSim((s) => s.unitsVisible);
  const clusterBadgesVisible = useSim((s) => s.clusterBadgesVisible);
  const envContext = useSim((s) => s.environmentalContext);
  const worldMode = useSim((s) => s.worldMode);
  const activeBranchId = useSim((s) => s.activeBranchId);
  const world = useSim((s) => s.world);
  const personnel = useMemo(() => Object.values(world.personnel ?? {}), [world.personnel]);
  const depots = useMemo(() => Object.values(world.depots ?? {}), [world.depots]);

  const [panelOpen, setPanelOpen] = useState(false);
  const [disclaimerOpen, setDisclaimerOpen] = useState(false);

  const units = useMemo(() => Object.values(world.units ?? {}), [world.units]);
  const movingCount = useMemo(
    () => units.filter((u) => u.status === "active" && (u.speedKph ?? 0) > 0).length,
    [units],
  );

  const stationList = Object.values(envContext?.stations ?? {});
  const conditionCounts = useMemo(() => {
    const counts: Record<WeatherCategory, number> = {
      thunderstorm: 0,
      rainy: 0,
      cloudy: 0,
      windy: 0,
      snow: 0,
      heat: 0,
      fog: 0,
      clear: 0,
    };
    for (const stn of stationList) {
      const c = classifyWeatherCondition(
        stn.temperatureC,
        stn.precipitationMm,
        stn.weatherCode,
        stn.conditionLabel,
        stn.windSpeedKph,
        stn.cloudPct ?? 30,
      );
      counts[c.category] += 1;
    }
    return counts;
  }, [stationList]);

  const sectorBreakdowns = useMemo(() => {
    return Object.entries(INDIAN_SECTORS).map(([secKey, sec]) => {
      const secUnits = units.filter((u) => u.sector === secKey);
      const secPersonnel = personnel.filter((p) => p.sector === secKey);
      const secDepot = depots.find((d) => d.sector === secKey);
      const stn = envContext?.stations?.[sec.weatherStationId];
      return {
        secKey,
        name: sec.name,
        unitsCount: secUnits.length,
        personnelCount: secPersonnel.length,
        depotName: secDepot?.name ?? sec.depotName,
        facilityType: sec.facilityType,
        temperatureC: stn?.temperatureC,
        conditionLabel: stn?.conditionLabel ?? "Clear",
      };
    });
  }, [units, personnel, depots, envContext]);

  return (
    <div className={cn("relative font-mono text-[11px] select-none", className)}>
      {/* Floating Pill Trigger */}
      <div className="flex items-center gap-1 border border-zinc-800 bg-[rgba(10,10,10,0.92)] px-2 py-1 shadow-lg backdrop-blur-md">
        <button
          onClick={() => setPanelOpen((o) => !o)}
          title="Toggle Map Layers & Pan-India Synthetic World Settings"
          className="flex items-center gap-1.5 text-zinc-300 hover:text-white transition-colors"
        >
          <Layers className="size-3.5 text-sky-400" />
          <span className="font-semibold uppercase tracking-wider text-[10px]">LAYERS</span>
        </button>

        <span className="text-zinc-600">|</span>

        {/* Quick Weather Footprint Toggle */}
        <button
          onClick={() => simStore.setWeatherLayerVisible(!weatherVisible)}
          title={weatherVisible ? "Hide Weather Cloud Footprints" : "Show Weather Cloud Footprints"}
          className={cn(
            "flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-semibold border transition-colors",
            weatherVisible
              ? "bg-sky-950/80 text-sky-300 border-sky-700/80"
              : "bg-zinc-900/60 text-zinc-500 border-zinc-800 line-through",
          )}
        >
          <Cloud className="size-3" />
          <span>CLOUDS</span>
        </button>

        {/* Quick Units Toggle */}
        <button
          onClick={() => simStore.toggleUnitsVisible()}
          title={unitsVisible ? "Hide Synthetic Units" : "Show Synthetic Units"}
          className={cn(
            "flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-semibold border transition-colors",
            unitsVisible
              ? "bg-sky-950/80 text-sky-300 border-sky-700/80"
              : "bg-zinc-900/60 text-zinc-500 border-zinc-800 line-through",
          )}
        >
          <Users className="size-3" />
          <span>UNITS</span>
        </button>

        {/* Quick Trails Toggle */}
        <button
          onClick={() => simStore.setMovementTrailsVisible(!trailsVisible)}
          title={trailsVisible ? "Hide Synthetic Movement Trails" : "Show Synthetic Movement Trails"}
          className={cn(
            "flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-semibold border transition-colors",
            trailsVisible
              ? "bg-emerald-950/80 text-emerald-300 border-emerald-700/80"
              : "bg-zinc-900/60 text-zinc-500 border-zinc-800 line-through",
          )}
        >
          <Navigation className="size-3" />
          <span>TRAILS</span>
        </button>

        {/* Quick Bases Toggle */}
        <button
          onClick={() => simStore.toggleFacilitiesVisible()}
          title={facilitiesVisible ? "Hide Bases & Depots" : "Show Bases & Depots"}
          className={cn(
            "flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-semibold border transition-colors",
            facilitiesVisible
              ? "bg-amber-950/80 text-amber-300 border-amber-700/80"
              : "bg-zinc-900/60 text-zinc-500 border-zinc-800 line-through",
          )}
        >
          <Building2 className="size-3" />
          <span>BASES</span>
        </button>

        {/* Quick Corridors Toggle */}
        <button
          onClick={() => simStore.toggleSupplyCorridorsVisible()}
          title={supplyCorridorsVisible ? "Hide Strategic Supply Corridors" : "Show Strategic Supply Corridors"}
          className={cn(
            "flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-semibold border transition-colors",
            supplyCorridorsVisible
              ? "bg-cyan-950/80 text-cyan-300 border-cyan-700/80"
              : "bg-zinc-900/60 text-zinc-500 border-zinc-800 line-through",
          )}
        >
          <Route className="size-3" />
          <span>ROUTES</span>
        </button>

        {/* Quick Zones Toggle */}
        <button
          onClick={() => simStore.toggleZonesVisible()}
          title={zonesVisible ? "Hide Tactical Zones" : "Show Tactical Zones"}
          className={cn(
            "flex items-center gap-1 px-1.5 py-0.5 text-[9px] font-semibold border transition-colors",
            zonesVisible
              ? "bg-purple-950/80 text-purple-300 border-purple-700/80"
              : "bg-zinc-900/60 text-zinc-500 border-zinc-800 line-through",
          )}
        >
          <Shield className="size-3" />
          <span>ZONES</span>
        </button>

        {/* Scientific Disclaimer Pill */}
        <button
          onClick={() => setDisclaimerOpen((o) => !o)}
          title="Surface Observation Scientific Footprint Notice"
          className="flex items-center gap-0.5 text-[9px] text-zinc-400 hover:text-amber-300 border border-zinc-800 bg-zinc-900/70 px-1 py-0.5"
        >
          <Info className="size-3 text-amber-400" />
          <span className="hidden sm:inline">NOTICE</span>
        </button>
      </div>

      {/* Scientific Limitation Disclaimer Flyout */}
      {disclaimerOpen && (
        <div className="absolute right-0 top-9 z-50 w-80 border border-amber-500/60 bg-[rgba(15,12,8,0.96)] p-3 shadow-2xl backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-amber-800/60 pb-1.5 mb-2">
            <div className="flex items-center gap-1.5 text-amber-300 font-bold text-xs uppercase tracking-wider">
              <Info className="size-4 text-amber-400" />
              <span>Scientific Limitation Notice</span>
            </div>
            <button
              onClick={() => setDisclaimerOpen(false)}
              className="text-zinc-400 hover:text-white text-xs px-1"
            >
              <X className="size-3.5" />
            </button>
          </div>
          <p className="text-[10px] text-zinc-300 leading-relaxed">
            {WEATHER_FOOTPRINT_DISCLAIMER}
          </p>
          <div className="mt-2.5 pt-2 border-t border-zinc-800 text-[9px] text-zinc-400 space-y-1">
            <div>• Observations are retrieved from WeatherAPI.com and Open-Meteo monitoring stations.</div>
            <div>• Disks visualize local cloud cover, thermal load, and wind vectors at station coordinates.</div>
            <div>• All operational units, facilities, personnel, and movements are 100% synthetic simulation data.</div>
          </div>
        </div>
      )}

      {/* Expanded Layer Controls Panel */}
      {panelOpen && (
        <div className="absolute right-0 top-9 z-40 w-96 max-h-[82vh] overflow-y-auto border border-zinc-800 bg-[rgba(12,12,12,0.96)] p-3 shadow-2xl backdrop-blur-md space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5">
            <span className="text-xs font-bold text-white tracking-wider uppercase">Unified Map & World Model Layers</span>
            <button
              onClick={() => setPanelOpen(false)}
              className="text-zinc-500 hover:text-white text-xs"
            >
              <X className="size-3.5" />
            </button>
          </div>

          {/* 1. Dedicated Weather Layer Controls */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-sky-300 flex items-center gap-1">
                <Cloud className="size-3.5" /> Weather Footprints
              </span>
              <button
                onClick={() => simStore.setWeatherLayerVisible(!weatherVisible)}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-bold border",
                  weatherVisible
                    ? "bg-sky-500/20 text-sky-200 border-sky-500/50"
                    : "bg-zinc-900 text-zinc-500 border-zinc-800",
                )}
              >
                {weatherVisible ? "VISIBLE" : "HIDDEN"}
              </button>
            </div>

            {weatherVisible && (
              <div className="space-y-2 bg-zinc-950/70 p-2 border border-zinc-900">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-zinc-400">Cloud Disk Opacity:</span>
                  <span className="text-sky-300 font-bold">{Math.round(cloudOpacity * 100)}%</span>
                </div>
                <div className="flex gap-1">
                  {[0.25, 0.5, 0.75, 1.0].map((op) => (
                    <button
                      key={op}
                      onClick={() => simStore.setCloudOpacity(op)}
                      className={cn(
                        "flex-1 py-0.5 text-[9px] border font-mono transition-colors",
                        Math.abs(cloudOpacity - op) < 0.1
                          ? "bg-sky-500/30 text-sky-200 border-sky-400 font-bold"
                          : "bg-zinc-900/60 text-zinc-400 border-zinc-800 hover:text-white",
                      )}
                    >
                      {Math.round(op * 100)}%
                    </button>
                  ))}
                </div>

                {/* Live Regional Condition Breakdown */}
                <div className="pt-1.5 border-t border-zinc-900 space-y-1">
                  <div className="flex items-center justify-between text-[9px] text-zinc-400 font-semibold uppercase">
                    <span>Simulated Conditions:</span>
                    <span className="text-zinc-500">11 REGIONS</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1 text-[9px]">
                    <div className="flex items-center justify-between px-1 py-0.5 rounded bg-purple-950/60 text-purple-300 border border-purple-800/60">
                      <span>⚡ Storms:</span>
                      <span className="font-bold">{conditionCounts.thunderstorm}</span>
                    </div>
                    <div className="flex items-center justify-between px-1 py-0.5 rounded bg-sky-950/60 text-sky-300 border border-sky-800/60">
                      <span>🌧 Rainy:</span>
                      <span className="font-bold">{conditionCounts.rainy}</span>
                    </div>
                    <div className="flex items-center justify-between px-1 py-0.5 rounded bg-zinc-900 text-zinc-300 border border-zinc-700">
                      <span>☁ Cloudy:</span>
                      <span className="font-bold">{conditionCounts.cloudy}</span>
                    </div>
                    <div className="flex items-center justify-between px-1 py-0.5 rounded bg-teal-950/60 text-teal-300 border border-teal-800/60">
                      <span>💨 Windy:</span>
                      <span className="font-bold">{conditionCounts.windy}</span>
                    </div>
                    <div className="flex items-center justify-between px-1 py-0.5 rounded bg-amber-950/60 text-amber-300 border border-amber-800/60">
                      <span>🔥 Thermal:</span>
                      <span className="font-bold">{conditionCounts.heat}</span>
                    </div>
                    <div className="flex items-center justify-between px-1 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-800/60">
                      <span>❄ Blizzard:</span>
                      <span className="font-bold">{conditionCounts.snow}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1 border-t border-zinc-900 text-[10px]">
                  <span className="text-zinc-400 flex items-center gap-1">
                    <Wind className="size-3 text-sky-400" /> Wind Vectors
                  </span>
                  <button
                    onClick={() => simStore.setWindVectorsVisible(!windVectorsVisible)}
                    className={cn(
                      "px-1.5 py-0.2 text-[9px] border font-mono",
                      windVectorsVisible
                        ? "bg-sky-950 text-sky-300 border-sky-700"
                        : "bg-zinc-900 text-zinc-500 border-zinc-800",
                    )}
                  >
                    {windVectorsVisible ? "ON" : "OFF"}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 2. Synthetic Units & Movement Overlays */}
          <div className="space-y-1.5 pt-2 border-t border-zinc-800">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-emerald-300 flex items-center gap-1">
                <Navigation className="size-3.5" /> Units & Movement Overlays
              </span>
              <button
                onClick={() => simStore.toggleUnitsVisible()}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-bold border",
                  unitsVisible
                    ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/50"
                    : "bg-zinc-900 text-zinc-500 border-zinc-800",
                )}
              >
                {unitsVisible ? "SHOWN" : "HIDDEN"}
              </button>
            </div>

            <div className="space-y-1.5 bg-zinc-950/70 p-2 border border-zinc-900 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="text-zinc-400">Movement History Trails:</span>
                <button
                  onClick={() => simStore.setMovementTrailsVisible(!trailsVisible)}
                  className={cn(
                    "px-1.5 py-0.2 text-[9px] border font-mono font-semibold",
                    trailsVisible
                      ? "bg-emerald-950 text-emerald-300 border-emerald-700"
                      : "bg-zinc-900 text-zinc-500 border-zinc-800",
                  )}
                >
                  {trailsVisible ? "ENABLED" : "MUTED"}
                </button>
              </div>

              <div className="flex items-center justify-between pt-1 border-t border-zinc-900">
                <span className="text-zinc-400">National Cluster Badges:</span>
                <button
                  onClick={() => simStore.toggleClusterBadgesVisible()}
                  className={cn(
                    "px-1.5 py-0.2 text-[9px] border font-mono font-semibold",
                    clusterBadgesVisible
                      ? "bg-sky-950 text-sky-300 border-sky-700"
                      : "bg-zinc-900 text-zinc-500 border-zinc-800",
                  )}
                >
                  {clusterBadgesVisible ? "VISIBLE" : "MUTED"}
                </button>
              </div>

              <div className="text-[9px] text-zinc-400 pt-1 flex justify-between">
                <span>Active Formations:</span>
                <span className="text-white font-bold">{units.length} Units ({movingCount} Moving)</span>
              </div>
            </div>
          </div>

          {/* 3. Synthetic Infrastructure & Depots */}
          <div className="space-y-1.5 pt-2 border-t border-zinc-800">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-amber-300 flex items-center gap-1">
                <Building2 className="size-3.5" /> Support Facilities & Depots
              </span>
              <button
                onClick={() => simStore.toggleFacilitiesVisible()}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-bold border",
                  facilitiesVisible
                    ? "bg-amber-500/20 text-amber-200 border-amber-500/50"
                    : "bg-zinc-900 text-zinc-500 border-zinc-800",
                )}
              >
                {facilitiesVisible ? "VISIBLE" : "HIDDEN"}
              </button>
            </div>
            <div className="text-[9px] text-zinc-400 bg-zinc-950/70 p-1.5 border border-zinc-900 flex justify-between">
              <span>Established Facilities:</span>
              <span className="text-amber-300 font-bold">{depots.length} Support Hubs</span>
            </div>
          </div>

          {/* 4. Strategic Inter-Depot Corridors */}
          <div className="space-y-1.5 pt-2 border-t border-zinc-800">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-cyan-300 flex items-center gap-1">
                <Route className="size-3.5" /> Strategic Supply Corridors
              </span>
              <button
                onClick={() => simStore.toggleSupplyCorridorsVisible()}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-bold border",
                  supplyCorridorsVisible
                    ? "bg-cyan-500/20 text-cyan-200 border-cyan-500/50"
                    : "bg-zinc-900 text-zinc-500 border-zinc-800",
                )}
              >
                {supplyCorridorsVisible ? "VISIBLE" : "HIDDEN"}
              </button>
            </div>
            <div className="text-[9px] text-zinc-400 bg-zinc-950/70 p-1.5 border border-zinc-900 flex justify-between">
              <span>Transit Arteries:</span>
              <span className="text-cyan-300 font-bold">{STRATEGIC_SUPPLY_CORRIDORS.length} Trans-Peninsular Arteries</span>
            </div>
          </div>

          {/* 5. Tactical & Threat Zones */}
          <div className="space-y-1.5 pt-2 border-t border-zinc-800">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-purple-300 flex items-center gap-1">
                <Shield className="size-3.5" /> Tactical & Threat Zones
              </span>
              <button
                onClick={() => simStore.toggleZonesVisible()}
                className={cn(
                  "px-2 py-0.5 text-[10px] font-bold border",
                  zonesVisible
                    ? "bg-purple-500/20 text-purple-200 border-purple-500/50"
                    : "bg-zinc-900 text-zinc-500 border-zinc-800",
                )}
              >
                {zonesVisible ? "VISIBLE" : "HIDDEN"}
              </button>
            </div>
          </div>

          {/* 6. Pan-India Regional Population Breakdown Matrix */}
          <div className="space-y-1.5 pt-2 border-t border-zinc-800">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-white uppercase tracking-wider flex items-center gap-1">
                <Users className="size-3.5 text-sky-400" /> Pan-India Population Matrix
              </span>
              <span className="text-[9px] text-emerald-400 font-bold">11 SECTORS</span>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1 bg-zinc-950/90 p-1.5 border border-zinc-900">
              {sectorBreakdowns.map((s) => (
                <div
                  key={s.secKey}
                  className="p-1 border border-zinc-800 bg-zinc-900/60 flex items-center justify-between text-[9px]"
                >
                  <div className="flex flex-col">
                    <span className="font-bold text-sky-300">{s.secKey}</span>
                    <span className="text-[8px] text-zinc-400 truncate max-w-[140px]">{s.name}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-zinc-200">
                      <span className="font-bold text-emerald-400">{s.unitsCount}</span> units •{" "}
                      <span className="font-bold text-white">{s.personnelCount}</span> pers
                    </div>
                    <div className="text-[8px] text-zinc-400">
                      {s.temperatureC !== undefined ? `${s.temperatureC.toFixed(0)}°C ${s.conditionLabel}` : "Nominal"}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer Metadata */}
          <div className="pt-2 border-t border-zinc-800 flex items-center justify-between text-[9px] text-zinc-500">
            <div>
              Mode: <span className="text-zinc-300 font-semibold uppercase">{worldMode}</span>
            </div>
            <div>
              Branch: <span className="text-zinc-300 font-mono">{activeBranchId ?? "BASELINE"}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
