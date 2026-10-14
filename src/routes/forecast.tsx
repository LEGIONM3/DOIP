import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { useSim } from "@/sim/store";
import { cn } from "@/lib/utils";
import {
  fetchForecast,
  listForecastHistory,
  type ForecastResult,
} from "@/services/forecasting";
import { MapView } from "@/components/map/MapView";
import type { Incident, Severity, Unit, UnitKind, WeatherCell } from "@/sim/types";
import {
  Activity,
  AlertTriangle,
  BatteryCharging,
  CloudRain,
  Compass,
  Cpu,
  Fuel,
  Layers,
  MapPin,
  Pause,
  Play,
  Radio,
  RefreshCw,
  ShieldAlert,
  SkipBack,
  SkipForward,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/forecast")({
  head: () => ({
    meta: [
      { title: "Digital Twin Forecasting & Lookahead — DOIP" },
      {
        name: "description",
        content: "Operational lookahead forward simulation (60-360 ticks) for fuel exhaustion, RF comms degradation, and threat escalation.",
      },
    ],
  }),
  component: ForecastConsole,
});

function ForecastConsole() {
  const currentScenario = useSim((s) => s.scenarioId);
  const [horizonHours, setHorizonHours] = useState(2.0);
  const [confidence, setConfidence] = useState(0.95);
  const [loading, setLoading] = useState(false);
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [history, setHistory] = useState<ForecastResult[]>([]);
  const [scrubTick, setScrubTick] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  async function loadHistory() {
    try {
      const res = await listForecastHistory(5);
      if (res && res.length > 0) {
        setHistory(res);
        if (!forecast && res[0]) {
          setForecast(res[0]);
          setScrubTick(0);
        }
      }
    } catch {
      // Non-blocking history load
    }
  }

  async function handleRunForecast() {
    setLoading(true);
    try {
      const result = await fetchForecast(horizonHours, confidence, currentScenario || "SC-1");
      setForecast(result);
      setScrubTick(0);
      setIsPlaying(false);
      toast.success(`Lookahead forecast generated (${result.ticks} ticks)`);
      loadHistory();
    } catch (err: any) {
      toast.error(err.message || "Failed to generate digital twin forecast");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadHistory();
    // Run initial projection on mount
    handleRunForecast();
  }, []);

  useEffect(() => {
    if (!isPlaying || !forecast) return;
    const interval = setInterval(() => {
      setScrubTick((prev) => {
        const maxTick = forecast.ticks || 120;
        if (prev >= maxTick) {
          setIsPlaying(false);
          return maxTick;
        }
        return prev + 1;
      });
    }, 150);
    return () => clearInterval(interval);
  }, [isPlaying, forecast]);

  const maxTicks = forecast?.ticks || 120;

  // Authoritative projection state at scrubTick
  const mapUnits: Unit[] = useMemo(() => {
    if (!forecast?.trajectories) return [];
    const list: Unit[] = [];
    for (const [uid, track] of Object.entries(forecast.trajectories)) {
      if (!track || track.length === 0) continue;
      let pt = track[0];
      for (const p of track) {
        if (p.tick <= scrubTick) {
          pt = p;
        } else {
          break;
        }
      }
      if (!pt) continue;
      list.push({
        id: uid,
        callsign: uid,
        kind: (uid.toLowerCase().includes("uav") ? "uav" : "patrol") as UnitKind,
        lat: pt.lat,
        lon: pt.lon,
        heading: pt.heading || 0,
        speedKph: pt.effectiveSpeedKph || 30,
        status: (pt.fuel <= 0 ? "halted" : pt.inWeather ? "slowed" : "active") as Unit["status"],
        fuel: pt.fuel,
        battery: pt.battery,
        lastSeenTick: pt.tick,
        sector: "A",
        route: track.map((p) => [p.lat, p.lon] as [number, number]),
      });
    }
    return list;
  }, [forecast?.trajectories, scrubTick]);

  const mapWeather: WeatherCell[] = useMemo(() => {
    const timeline = forecast?.weather_timeline || forecast?.predictions?.weather_timeline;
    if (!timeline || timeline.length === 0) return [];
    let matchedCells: any[] = [];
    for (const snap of timeline) {
      if (snap.tick <= scrubTick) {
        matchedCells = snap.cells || (snap.cell && Object.keys(snap.cell).length > 0 ? [snap.cell] : []);
      } else {
        break;
      }
    }
    return matchedCells.map((c, i) => ({
      id: c.id || `W-${i}`,
      lat: Number(c.lat) || 12.97,
      lon: Number(c.lon) || 77.59,
      radiusM: Number(c.radiusM) || 2000,
      intensity: Number(c.intensity) || 0.5,
      kind: String(c.kind || "rain"),
    }));
  }, [forecast?.weather_timeline, forecast?.predictions?.weather_timeline, scrubTick]);

  const mapIncidents: Incident[] = useMemo(() => {
    const incs = forecast?.incident_history || forecast?.predictions?.incident_history;
    if (!incs || incs.length === 0) return [];
    return incs
      .filter((inc) => inc.tick <= scrubTick)
      .map((inc) => ({
        id: inc.id,
        tick: inc.tick,
        severity: (inc.severity || "medium") as Severity,
        kind: inc.kind || "threat-contact",
        lat: inc.lat,
        lon: inc.lon,
        entityId: inc.id,
        open: true,
      }));
  }, [forecast?.incident_history, forecast?.predictions?.incident_history, scrubTick]);

  const mapRoutes = useMemo(() => {
    if (!forecast?.trajectories) return [];
    return Object.entries(forecast.trajectories).map(([uid, track]) => {
      const isCritical =
        Boolean(forecast.predictions?.fuel_exhaustion?.units?.[uid]?.pnr_breached) ||
        Boolean(forecast.predictions?.threat_escalation?.predicted_contacts?.some((c) => c.unit_id === uid));
      return {
        points: track.map((p) => [p.lat, p.lon] as [number, number]),
        color: isCritical ? "#ef4444" : "#06b6d4",
        dashed: true,
      };
    });
  }, [forecast?.trajectories, forecast?.predictions]);

  const preds = forecast?.predictions;
  const exec = preds?.executive_summary;
  const fuelExhaustion = preds?.fuel_exhaustion;
  const commsDegradation = preds?.comms_degradation;
  const threatEscalation = preds?.threat_escalation;
  const missionArrival = preds?.mission_arrival;

  return (
    <div className="flex w-full flex-col gap-2 p-2">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border border-border bg-surface p-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center border border-primary/30 bg-primary/10 text-primary">
            <Cpu className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-wider uppercase text-foreground">
              Digital Twin Operational Forecasting Console
            </h1>
            <p className="text-[11px] text-muted-foreground font-mono">
              Forward Lookahead Engine (60 to 360 Ticks) &bull; Read-Only Decoupled Memory Invariant
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground font-mono">Horizon:</span>
            <select
              value={horizonHours}
              onChange={(e) => setHorizonHours(parseFloat(e.target.value))}
              className="border border-border bg-surface-2 px-2 py-1 text-xs font-mono text-foreground outline-none"
            >
              <option value={1.0}>1.0h (60 ticks)</option>
              <option value={2.0}>2.0h (120 ticks)</option>
              <option value={4.0}>4.0h (240 ticks)</option>
              <option value={6.0}>6.0h (360 ticks)</option>
            </select>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground font-mono">Confidence:</span>
            <select
              value={confidence}
              onChange={(e) => setConfidence(parseFloat(e.target.value))}
              className="border border-border bg-surface-2 px-2 py-1 text-xs font-mono text-foreground outline-none"
            >
              <option value={0.80}>80% Standard</option>
              <option value={0.90}>90% High</option>
              <option value={0.95}>95% Critical Buffer</option>
              <option value={0.99}>99% Mission Max</option>
            </select>
          </div>

          <button
            onClick={handleRunForecast}
            disabled={loading}
            className="flex items-center gap-1.5 border border-primary bg-primary/20 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/30 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            {loading ? "Projecting..." : "Run Lookahead"}
          </button>
        </div>
      </div>

      {/* Risk Executive Banner */}
      {exec && (
        <div
          className={cn(
            "flex flex-wrap items-center justify-between gap-4 border p-3",
            exec.risk_level === "CRITICAL"
              ? "border-red-500/50 bg-red-950/20 text-red-300"
              : exec.risk_level === "HIGH"
              ? "border-amber-500/50 bg-amber-950/20 text-amber-300"
              : "border-emerald-500/50 bg-emerald-950/20 text-emerald-300"
          )}
        >
          <div className="flex items-center gap-3">
            <ShieldAlert className="h-6 w-6 shrink-0" />
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold uppercase tracking-widest px-1.5 py-0.5 border border-current">
                  {exec.risk_level} RISK
                </span>
                <span className="font-mono text-xs">Composite Score: {exec.composite_risk_score}/100</span>
              </div>
              <p className="mt-1 text-xs text-foreground/90 font-medium">{exec.headline}</p>
            </div>
          </div>
          {forecast?.id && (
            <div className="font-mono text-[10px] text-muted-foreground">
              Run ID: <Mono>{forecast.id}</Mono>
            </div>
          )}
        </div>
      )}

      {/* Grid of Key Subsystem Projections */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2">
        {/* Metric 1: Fuel & PNR */}
        <Panel title="Fuel Exhaustion & PNR" className="min-h-[140px]">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Fuel className="h-3.5 w-3.5 text-amber-400" /> PNR Breaches
              </span>
              <span
                className={cn(
                  "font-mono text-xs font-bold px-1.5 py-0.5 border",
                  (fuelExhaustion?.pnr_breaches_detected || 0) > 0
                    ? "border-red-500 bg-red-500/20 text-red-400"
                    : "border-emerald-500 bg-emerald-500/20 text-emerald-400"
                )}
              >
                {fuelExhaustion?.pnr_breaches_detected || 0} BREACHES
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">
              Monitors Point-of-No-Return against nearest friendly refuel depot.
            </div>
          </div>
        </Panel>

        {/* Metric 2: Comms Degradation */}
        <Panel title="RF Line-of-Sight & Comms" className="min-h-[140px]">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Radio className="h-3.5 w-3.5 text-blue-400" /> Shadow Windows
              </span>
              <span className="font-mono text-xs font-bold text-foreground">
                {commsDegradation?.degradation_windows?.length || 0} Identified
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">
              Fresnel zone terrain elevation occlusion against HF/VHF masts.
            </div>
          </div>
        </Panel>

        {/* Metric 3: Threat Escalation */}
        <Panel title="Threat Escalation" className="min-h-[140px]">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <AlertTriangle className="h-3.5 w-3.5 text-rose-400" /> Trend Score
              </span>
              <span className="font-mono text-xs font-bold text-rose-400">
                {threatEscalation?.escalation_trend_score || 0}/100
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">
              Predicted trajectory intersections with active hostile sectors.
            </div>
          </div>
        </Panel>

        {/* Metric 4: Mission Timeline */}
        <Panel title="Mission Arrival ETAs" className="min-h-[140px]">
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Compass className="h-3.5 w-3.5 text-emerald-400" /> Units Tracked
              </span>
              <span className="font-mono text-xs font-bold text-foreground">
                {Object.keys(missionArrival?.units || {}).length}
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">
              P10, P50, and P90 percentiles with weather drag & terrain friction.
            </div>
          </div>
        </Panel>
      </div>

      {/* Tactical Lookahead Map & Time Scrubber */}
      <Panel
        title="Projected Operational Geospatial Horizon (Tactical Lookahead Map)"
        actions={
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-muted-foreground">
              Horizon: <Mono>+{((scrubTick || 0) / 60).toFixed(1)}h</Mono> (Tick {scrubTick} / {maxTicks})
            </span>
          </div>
        }
      >
        <div className="flex flex-col gap-2">
          {/* Timeline Scrubber Controls */}
          <div className="flex flex-wrap items-center justify-between gap-3 border border-border bg-surface-2 p-2">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setScrubTick(0)}
                title="Jump to Horizon Start (T+0)"
                className="flex h-7 w-7 items-center justify-center border border-border bg-surface text-muted-foreground hover:text-foreground transition-colors"
              >
                <SkipBack className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setIsPlaying((p) => !p)}
                className={cn(
                  "flex items-center gap-1.5 border px-2.5 py-1 text-xs font-mono font-medium transition-colors",
                  isPlaying
                    ? "border-amber-500 bg-amber-500/20 text-amber-300"
                    : "border-primary bg-primary/20 text-primary hover:bg-primary/30"
                )}
              >
                {isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                {isPlaying ? "PAUSE" : "PLAY"}
              </button>
              <button
                onClick={() => setScrubTick(maxTicks)}
                title="Jump to Horizon Max"
                className="flex h-7 w-7 items-center justify-center border border-border bg-surface text-muted-foreground hover:text-foreground transition-colors"
              >
                <SkipForward className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Range Scrubber */}
            <div className="flex flex-1 items-center gap-3 min-w-[200px]">
              <span className="font-mono text-xs text-muted-foreground">T+0</span>
              <input
                type="range"
                min={0}
                max={maxTicks}
                value={scrubTick}
                onChange={(e) => {
                  setScrubTick(parseInt(e.target.value, 10));
                  setIsPlaying(false);
                }}
                className="h-1.5 flex-1 cursor-pointer accent-primary bg-muted rounded-none"
              />
              <span className="font-mono text-xs text-muted-foreground">T+{maxTicks}</span>
            </div>

            {/* Readout Badges */}
            <div className="flex items-center gap-2 font-mono text-[11px]">
              <span className="flex items-center gap-1 border border-border bg-surface px-2 py-0.5 text-foreground">
                <MapPin className="h-3 w-3 text-primary" /> {mapUnits.length} Units
              </span>
              <span className="flex items-center gap-1 border border-border bg-surface px-2 py-0.5 text-foreground">
                <CloudRain className="h-3 w-3 text-blue-400" /> {mapWeather.length} Weather Cells
              </span>
              <span className="flex items-center gap-1 border border-border bg-surface px-2 py-0.5 text-foreground">
                <AlertTriangle className="h-3 w-3 text-rose-400" /> {mapIncidents.length} Contacts
              </span>
            </div>
          </div>

          {/* Map View */}
          <div className="h-[420px] w-full border border-border">
            <MapView
              units={mapUnits}
              weather={mapWeather}
              incidents={mapIncidents}
              routes={mapRoutes}
              tick={scrubTick}
            />
          </div>
        </div>
      </Panel>

      {/* Detailed Units Status Table */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2 flex-1 min-h-0">
        {/* Left Column: Units Fuel Exhaustion & PNR Matrix */}
        <Panel title="Unit Fuel Exhaustion Timelines & Point-of-No-Return">
          {fuelExhaustion?.units && Object.keys(fuelExhaustion.units).length > 0 ? (
            <div className="flex flex-col gap-2 overflow-y-auto max-h-[360px]">
              {Object.entries(fuelExhaustion.units).map(([uid, u]) => (
                <div
                  key={uid}
                  className="flex flex-col gap-1 border border-border bg-surface-2 p-2 text-xs"
                >
                  <div className="flex items-center justify-between font-mono">
                    <span className="font-semibold text-foreground">{uid}</span>
                    <span
                      className={cn(
                        "px-1.5 py-0.5 text-[10px] font-bold uppercase",
                        u.pnr_breached
                          ? "border border-red-500 bg-red-950/40 text-red-400"
                          : "border border-emerald-500 bg-emerald-950/40 text-emerald-400"
                      )}
                    >
                      {u.pnr_breached ? `PNR BREACH (Tick ${u.pnr_breach_tick})` : "PNR SAFE"}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-1 text-[11px] font-mono text-muted-foreground">
                    <div>
                      Initial: <span className="text-foreground">{u.initial_fuel != null ? u.initial_fuel.toFixed(1) : "—"}%</span>
                    </div>
                    <div>
                      Projected: <span className="text-foreground">{u.final_fuel != null ? u.final_fuel.toFixed(1) : "—"}%</span>
                    </div>
                    <div>
                      Depletion:{" "}
                      <span className="text-foreground">
                        {u.depletion_tick ? `Tick ${u.depletion_tick}` : "None"}
                      </span>
                    </div>
                  </div>
                  <div className="text-[10px] font-mono text-muted-foreground mt-0.5">
                    Nearest Depot: {u.nearest_depot?.name ?? "N/A"} ({u.nearest_depot?.distance_km ?? "—"} km, requires {u.nearest_depot?.fuel_to_reach_pct ?? "—"}% fuel)
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground p-4 text-center">
              No active unit trajectories in current scenario.
            </div>
          )}
        </Panel>

        {/* Right Column: Comms & Threat Escalation Contacts */}
        <Panel title="Predicted Comms Degradation & Threat Interceptions">
          {(commsDegradation?.degradation_windows?.length || threatEscalation?.predicted_contacts?.length) ? (
            <div className="flex flex-col gap-2 overflow-y-auto max-h-[360px]">
              {commsDegradation?.degradation_windows && commsDegradation.degradation_windows.length > 0 && (
                <div className="flex flex-col gap-1">
                  <span className="text-[10px] font-mono uppercase text-muted-foreground font-semibold">
                    RF Blackout Windows
                  </span>
                  {commsDegradation.degradation_windows.map((w, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between border border-amber-500/30 bg-amber-950/10 p-2 text-xs font-mono"
                    >
                      <div>
                        <span className="font-bold text-foreground">{w.unit_id}</span>
                        <span className="text-muted-foreground ml-2">
                          Ticks {w.start_tick}-{w.end_tick} ({w.duration_ticks}m)
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-amber-400 font-bold">{w.severity}</span>
                        <span className="text-muted-foreground ml-2">RSSI: {w.min_rssi_dbm} dBm</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {threatEscalation?.predicted_contacts && threatEscalation.predicted_contacts.length > 0 && (
                <div className="flex flex-col gap-1 mt-2">
                  <span className="text-[10px] font-mono uppercase text-muted-foreground font-semibold">
                    Threat Interception Predictions
                  </span>
                  {threatEscalation.predicted_contacts.map((t, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between border border-rose-500/30 bg-rose-950/10 p-2 text-xs font-mono"
                    >
                      <div>
                        <span className="font-bold text-foreground">{t.unit_id}</span>
                        <span className="text-muted-foreground ml-2">&rarr; {t.incident_id}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-rose-400 font-bold">
                          {(t.intersection_probability != null ? (t.intersection_probability * 100).toFixed(0) : "0")}% Probability
                        </span>
                        <span className="text-muted-foreground ml-2">Closest: {t.closest_approach_km ?? "—"} km</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-muted-foreground p-4 text-center">
              All communications and threat corridors nominal for specified horizon.
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
