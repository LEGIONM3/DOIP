import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  listTheaters,
  listWorlds,
  getCrossTheaterAnalysis,
  type Theater,
  type SimulationWorld,
  type CrossTheaterAnalysis,
} from "@/services/theaters";
import {
  Globe2,
  MapPin,
  Fuel,
  ShieldAlert,
  Activity,
  Compass,
  RefreshCw,
  Box,
  Layers,
  CheckCircle,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/theaters")({
  head: () => ({
    meta: [
      { title: "Multi-Theater Digital Twin — DOIP" },
      {
        name: "description",
        content: "Multi-Theater operational management and concurrent isolated simulation worlds.",
      },
    ],
  }),
  component: TheatersDashboard,
});

function TheatersDashboard() {
  const [theaters, setTheaters] = useState<Theater[]>([]);
  const [worlds, setWorlds] = useState<SimulationWorld[]>([]);
  const [analysis, setAnalysis] = useState<CrossTheaterAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTheaterId, setActiveTheaterId] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [tList, wList, aData] = await Promise.all([
        listTheaters(),
        listWorlds(),
        getCrossTheaterAnalysis(),
      ]);
      setTheaters(tList);
      setWorlds(wList);
      setAnalysis(aData);
    } catch (err: any) {
      toast.error(`Failed to load multi-theater data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filteredWorlds = activeTheaterId
    ? worlds.filter((w) => w.theater_id === activeTheaterId)
    : worlds;

  return (
    <div className="space-y-4 p-4 text-[#F2F2F2] max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#2A2A2A] pb-3 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <Globe2 className="h-5 w-5 text-blue-400" />
            <h1 className="text-xl font-bold tracking-wider uppercase">Multi-Theater Digital Twin</h1>
          </div>
          <p className="text-xs text-[#8A8A8A] mt-0.5">
            Phase 4B · Multi-theater battle spaces and concurrent isolated simulation worlds.
          </p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#161616] hover:bg-[#202020] border border-[#2A2A2A] rounded transition self-start md:self-auto"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
          Sync Theaters
        </button>
      </div>

      {/* Cross-Theater KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Global Readiness"
            value={`${analysis?.global_readiness_score ?? 88.0}%`}
            sub="Aggregated posture"
          />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Active Theaters"
            value={analysis?.theaters_active ?? theaters.length}
            sub="Isolated battle spaces"
          />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Total Units Deployed"
            value={analysis?.total_units_deployed ?? 12}
            sub="Across all worlds"
          />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Depot Fuel Reserves"
            value={`${analysis?.total_depot_fuel_liters ?? 8400}L`}
            sub="Strategic reserve"
          />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat
            label="Threat Density"
            value={`${analysis?.threat_density_index ?? 37.0}%`}
            sub="Active hostile index"
          />
        </Panel>
      </div>

      {/* Main Theaters Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Theaters List */}
        <div className="lg:col-span-1 space-y-3">
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2 mb-3">
              <div className="flex items-center gap-2">
                <Compass className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-semibold uppercase">Operational Theaters</span>
              </div>
              {activeTheaterId && (
                <button
                  onClick={() => setActiveTheaterId(null)}
                  className="text-[11px] text-amber-400 hover:underline"
                >
                  Clear filter
                </button>
              )}
            </div>

            <div className="space-y-2.5">
              {theaters.map((t) => {
                const isSelected = activeTheaterId === t.id;
                const theaterBreakdown = analysis?.theaters.find((tb) => tb.theater_id === t.id);

                return (
                  <div
                    key={t.id}
                    role="button"
                    tabIndex={0}
                    aria-pressed={isSelected}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setActiveTheaterId(isSelected ? null : t.id);
                      }
                    }}
                    onClick={() => setActiveTheaterId(isSelected ? null : t.id)}
                    className={cn(
                      "bg-[#141414] border rounded p-3 cursor-pointer transition select-none",
                      isSelected
                        ? "border-amber-500 bg-[#1A1812]"
                        : "border-[#242424] hover:border-[#383838]"
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm">{t.name}</span>
                      <span className="text-[10px] font-mono uppercase bg-[#202020] px-1.5 py-0.5 rounded text-[#A0A0A0]">
                        {t.code}
                      </span>
                    </div>

                    <div className="text-xs text-[#8A8A8A] mt-1 space-y-1">
                      <div className="flex items-center justify-between">
                        <Mono className="text-[11px]">{t.id}</Mono>
                        <span className="text-emerald-400 text-[11px] flex items-center gap-1">
                          <CheckCircle className="h-2.5 w-2.5" />
                          {t.status}
                        </span>
                      </div>

                      {theaterBreakdown && (
                        <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-[#222222] text-[11px]">
                          <div>Readiness: <strong className="text-white">{theaterBreakdown.readiness_score}%</strong></div>
                          <div>Units: <strong className="text-white">{theaterBreakdown.units_count}</strong></div>
                          <div>Fuel Res: <strong className="text-white">{theaterBreakdown.depot_fuel_liters}L</strong></div>
                          <div>Incidents: <strong className="text-white">{theaterBreakdown.active_incidents}</strong></div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>

        {/* Isolated Worlds Details */}
        <div className="lg:col-span-2 space-y-3">
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2 mb-3">
              <div className="flex items-center gap-2">
                <Box className="h-4 w-4 text-cyan-400" />
                <span className="text-sm font-semibold uppercase">
                  Isolated Simulation Worlds {activeTheaterId ? `(${activeTheaterId})` : ""}
                </span>
              </div>
              <span className="text-xs text-[#8A8A8A]">
                {filteredWorlds.length} Concurrent Worlds
              </span>
            </div>

            <div className="space-y-3">
              {filteredWorlds.map((w) => {
                const snap = (w.state_snapshot ?? {}) as Record<string, any>;
                const units = snap["units"] ? Object.values(snap["units"]) : [];
                const depots = snap["depots"] ? Object.values(snap["depots"]) : [];
                const incidents = (snap["incidents"] ? Object.values(snap["incidents"]) : []) as any[];
                const firstInc = incidents[0];

                return (
                  <div
                    key={w.id}
                    className="bg-[#141414] border border-[#242424] rounded p-3.5 space-y-2.5"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">{w.name}</span>
                        <Mono className="text-[11px] text-[#A0A0A0]">{w.id}</Mono>
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="font-mono bg-[#1E1E1E] px-2 py-0.5 rounded text-amber-400">
                          Tick: {w.tick}
                        </span>
                        <span className="text-emerald-400 text-xs uppercase font-mono">
                          {w.status}
                        </span>
                      </div>
                    </div>

                    {/* World Subsystem Metrics */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                      <div className="bg-[#181818] p-2 rounded border border-[#222222]">
                        <span className="text-[10px] text-[#8A8A8A] block uppercase">Deployed Units</span>
                        <span className="font-mono font-bold text-white text-sm">{units.length}</span>
                      </div>
                      <div className="bg-[#181818] p-2 rounded border border-[#222222]">
                        <span className="text-[10px] text-[#8A8A8A] block uppercase">Supply Depots</span>
                        <span className="font-mono font-bold text-white text-sm">{depots.length}</span>
                      </div>
                      <div className="bg-[#181818] p-2 rounded border border-[#222222]">
                        <span className="text-[10px] text-[#8A8A8A] block uppercase">Active Threats</span>
                        <span className="font-mono font-bold text-amber-400 text-sm">{incidents.length}</span>
                      </div>
                      <div className="bg-[#181818] p-2 rounded border border-[#222222]">
                        <span className="text-[10px] text-[#8A8A8A] block uppercase">PRNG Seed</span>
                        <span className="font-mono font-bold text-cyan-400 text-sm">{snap["seed"] ?? "N/A"}</span>
                      </div>
                    </div>

                    {/* Threat / Incidents Alert */}
                    {firstInc && (
                      <div className="p-2 bg-amber-950/20 border border-amber-800/40 rounded flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2 text-amber-300">
                          <ShieldAlert className="h-3.5 w-3.5" />
                          <span>Active Incident: {firstInc.id} ({firstInc.type})</span>
                        </div>
                        <span className="font-mono text-[10px] uppercase text-amber-400">
                          Severity: {firstInc.severity}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
