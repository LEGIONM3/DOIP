import React, { useState, useMemo } from "react";
import { simStore, useSim } from "@/sim/store";
import { WEATHER_FOOTPRINT_DISCLAIMER, classifyWeatherCondition, type WeatherCategory } from "./weatherLayers";
import { Cloud, Wind, Navigation, Eye, Sliders, Info, Shield, Layers, X, Zap } from "lucide-react";
import { cn } from "@/lib/utils";

export interface MapLayerControlsProps {
  className?: string;
  compact?: boolean;
}

export function MapLayerControls({ className, compact = false }: MapLayerControlsProps) {
  const weatherVisible = useSim((s) => s.weatherLayerVisible);
  const cloudOpacity = useSim((s) => s.cloudOpacity);
  const trailsVisible = useSim((s) => s.movementTrailsVisible);
  const windVectorsVisible = useSim((s) => s.windVectorsVisible);
  const envContext = useSim((s) => s.environmentalContext);
  const worldMode = useSim((s) => s.worldMode);
  const activeBranchId = useSim((s) => s.activeBranchId);
  const world = useSim((s) => s.world);

  const [panelOpen, setPanelOpen] = useState(false);
  const [disclaimerOpen, setDisclaimerOpen] = useState(false);

  const units = Object.values(world.units);
  const movingCount = units.filter((u) => u.status === "active" && (u.speedKph ?? 0) > 0).length;

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

  return (
    <div className={cn("relative font-mono text-[11px] select-none", className)}>
      {/* Floating Pill Trigger */}
      <div className="flex items-center gap-1 border border-zinc-800 bg-[rgba(10,10,10,0.92)] px-2 py-1 shadow-lg backdrop-blur-md">
        <button
          onClick={() => setPanelOpen((o) => !o)}
          title="Toggle Map Layers & Weather Footprint Settings"
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
            <div>• No continuous radar boundary or satellite imagery is implied.</div>
          </div>
        </div>
      )}

      {/* Expanded Layer Controls Panel */}
      {panelOpen && (
        <div className="absolute right-0 top-9 z-40 w-72 border border-zinc-800 bg-[rgba(12,12,12,0.96)] p-3 shadow-2xl backdrop-blur-md space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-1.5">
            <span className="text-xs font-bold text-white tracking-wider uppercase">Unified Map Layers</span>
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

                <div className="text-[9px] text-zinc-500 pt-1">
                  Provenance: <span className="text-emerald-400 font-semibold">{envContext?.globalProvenance ?? "REAL_FORECAST"}</span>
                </div>
              </div>
            )}
          </div>

          {/* 2. Pan-India Synthetic Movement Controls */}
          <div className="space-y-1.5 pt-2 border-t border-zinc-800">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-emerald-300 flex items-center gap-1">
                <Navigation className="size-3.5" /> Synthetic Movement
              </span>
              <span className="text-[9px] bg-emerald-950/80 text-emerald-400 border border-emerald-800/80 px-1 py-0.2">
                {units.length} UNITS ({movingCount} MOVING)
              </span>
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

              <div className="text-[9px] text-zinc-500">
                World Mode: <span className="text-zinc-300 font-semibold uppercase">{worldMode}</span> ({activeBranchId ?? "BASELINE"})
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
