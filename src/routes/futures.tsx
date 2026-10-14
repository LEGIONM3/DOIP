import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  generateAlternativeFutures,
  listFutures,
  type FutureBranch,
  type FutureBatchResult,
} from "@/services/futures";
import {
  GitFork,
  Compass,
  Play,
  TrendingUp,
  AlertTriangle,
  ShieldCheck,
  Fuel,
  RefreshCw,
  Hash,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/futures")({
  head: () => ({
    meta: [
      { title: "Autonomous Simulation Futures — DOIP" },
      {
        name: "description",
        content: "Monte Carlo lookahead via deterministic simulation branching into P10, P50, P90, and WORST risk bands.",
      },
    ],
  }),
  component: FuturesDashboard,
});

function FuturesDashboard() {
  const [baselineWorld, setBaselineWorld] = useState("WLD-NORTH-01");
  const [branchCount, setBranchCount] = useState(10);
  const [horizonTicks, setHorizonTicks] = useState(120);
  const [generating, setGenerating] = useState(false);

  const [batchResult, setBatchResult] = useState<FutureBatchResult | null>(null);
  const [branches, setBranches] = useState<FutureBranch[]>([]);
  const [loadingList, setLoadingList] = useState(false);

  const fetchBranches = async (wId: string) => {
    setLoadingList(true);
    try {
      const list = await listFutures(wId, 50);
      setBranches(list);
    } catch (err: any) {
      toast.error(`Failed to load branches: ${err.message}`);
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    fetchBranches(baselineWorld);
  }, [baselineWorld]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await generateAlternativeFutures(baselineWorld, branchCount, horizonTicks);
      setBatchResult(res);
      toast.success(`Generated ${res.branches_count} deterministic future branches`);
      fetchBranches(baselineWorld);
    } catch (err: any) {
      toast.error(`Future generation failed: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const p10 = batchResult?.risk_bands.P10_optimistic;
  const p50 = batchResult?.risk_bands.P50_median;
  const p90 = batchResult?.risk_bands.P90_conservative;
  const worst = batchResult?.risk_bands.WORST_case;

  return (
    <div className="space-y-4 p-4 text-[#F2F2F2] max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#2A2A2A] pb-3 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <GitFork className="h-5 w-5 text-purple-400" />
            <h1 className="text-xl font-bold tracking-wider uppercase">Deterministic Simulation Future Generator</h1>
          </div>
          <p className="text-xs text-[#8A8A8A] mt-0.5">
            Phase 4G · Autonomous Monte Carlo lookahead branching into reproducible P10, P50, P90, and WORST risk bands.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-emerald-400 font-mono flex items-center gap-1 bg-[#141414] px-2.5 py-1 rounded border border-[#2A2A2A]">
            <ShieldCheck className="h-3.5 w-3.5" />
            Live State: Immutable
          </span>
        </div>
      </div>

      {/* Control Panel */}
      <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
          <div>
            <label className="text-xs text-[#8A8A8A] block mb-1">Baseline Simulation World</label>
            <select
              value={baselineWorld}
              onChange={(e) => setBaselineWorld(e.target.value)}
              className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none focus:border-purple-500"
            >
              <option value="WLD-NORTH-01">WLD-NORTH-01 (Northern Mountain)</option>
              <option value="WLD-EAST-01">WLD-EAST-01 (Eastern Littoral)</option>
              <option value="WLD-LITTORAL-01">WLD-LITTORAL-01 (Southern Maritime)</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-[#8A8A8A] block mb-1">Number of Branches (N)</label>
            <select
              value={branchCount}
              onChange={(e) => setBranchCount(Number(e.target.value))}
              className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none focus:border-purple-500"
            >
              <option value={10}>10 Branches (Fast Lookahead)</option>
              <option value={25}>25 Branches (Standard Envelope)</option>
              <option value={50}>50 Branches (Deep Monte Carlo)</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-[#8A8A8A] block mb-1">Horizon Duration</label>
            <select
              value={horizonTicks}
              onChange={(e) => setHorizonTicks(Number(e.target.value))}
              className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none focus:border-purple-500"
            >
              <option value={60}>60 Ticks (~1.0 Hour)</option>
              <option value={120}>120 Ticks (~2.0 Hours)</option>
              <option value={240}>240 Ticks (~4.0 Hours)</option>
            </select>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full py-2 bg-purple-700 hover:bg-purple-600 text-white font-semibold text-xs rounded transition flex items-center justify-center gap-1.5"
          >
            <Play className={cn("h-3.5 w-3.5", generating && "animate-spin")} />
            {generating ? "Branching World..." : "Generate Alternative Futures"}
          </button>
        </div>
      </Panel>

      {/* Risk Band Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel className="bg-[#0D0D0D] border-emerald-900/60 p-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-[#8A8A8A]">
            <span className="text-emerald-400 font-semibold">P10 Optimistic</span>
            <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
          </div>
          <div className="text-2xl font-mono font-bold text-emerald-300">
            {p10 ? `${p10.score}` : "—"}
          </div>
          <div className="text-[11px] text-[#8A8A8A]">
            Incidents: <strong className="text-white">{p10?.incidents ?? 0}</strong>
          </div>
        </Panel>

        <Panel className="bg-[#0D0D0D] border-blue-900/60 p-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-[#8A8A8A]">
            <span className="text-blue-400 font-semibold">P50 Median</span>
            <Compass className="h-3.5 w-3.5 text-blue-400" />
          </div>
          <div className="text-2xl font-mono font-bold text-blue-300">
            {p50 ? `${p50.score}` : "—"}
          </div>
          <div className="text-[11px] text-[#8A8A8A]">
            Incidents: <strong className="text-white">{p50?.incidents ?? 1}</strong>
          </div>
        </Panel>

        <Panel className="bg-[#0D0D0D] border-amber-900/60 p-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-[#8A8A8A]">
            <span className="text-amber-400 font-semibold">P90 Conservative</span>
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
          </div>
          <div className="text-2xl font-mono font-bold text-amber-300">
            {p90 ? `${p90.score}` : "—"}
          </div>
          <div className="text-[11px] text-[#8A8A8A]">
            Incidents: <strong className="text-white">{p90?.incidents ?? 2}</strong>
          </div>
        </Panel>

        <Panel className="bg-[#0D0D0D] border-red-900/60 p-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-[#8A8A8A]">
            <span className="text-red-400 font-semibold">WORST Case</span>
            <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
          </div>
          <div className="text-2xl font-mono font-bold text-red-300">
            {worst ? `${worst.score}` : "—"}
          </div>
          <div className="text-[11px] text-[#8A8A8A]">
            Incidents: <strong className="text-white">{worst?.incidents ?? 3}</strong>
          </div>
        </Panel>
      </div>

      {/* Summary Narrative */}
      {batchResult && (
        <div className="bg-[#141414] border border-[#2A2A2A] rounded p-3 text-xs text-[#C0C0C0] leading-relaxed">
          <strong className="text-white block mb-0.5">Monte Carlo Lookahead Summary:</strong>
          {batchResult.summary}
        </div>
      )}

      {/* Ranked Branches Table */}
      <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2">
          <div className="flex items-center gap-2">
            <Hash className="h-4 w-4 text-purple-400" />
            <span className="text-sm font-semibold uppercase">
              Ranked Alternative Futures ({branches.length} Branches Persisted)
            </span>
          </div>
          <button
            onClick={() => fetchBranches(baselineWorld)}
            className="text-xs text-[#8A8A8A] hover:text-white flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" />
            Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-[#161616] text-[#8A8A8A] uppercase font-mono text-[10px]">
              <tr>
                <th className="py-2 px-3">Rank</th>
                <th className="py-2 px-3">Branch ID</th>
                <th className="py-2 px-3">PRNG Seed</th>
                <th className="py-2 px-3">Risk Band</th>
                <th className="py-2 px-3">Score</th>
                <th className="py-2 px-3">Mission Status</th>
                <th className="py-2 px-3">Fuel Delta</th>
                <th className="py-2 px-3">Incidents</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1F1F1F]">
              {branches.map((b, idx) => {
                const outcome = b.outcome || b;
                const band = b.risk_band || outcome.risk_band || "P50";

                return (
                  <tr key={b.id || idx} className="hover:bg-[#141414] transition">
                    <td className="py-2 px-3 font-mono text-white">#{b.outcome_rank || idx + 1}</td>
                    <td className="py-2 px-3 font-mono text-[#A0A0A0]">{b.id || b.branch_id}</td>
                    <td className="py-2 px-3 font-mono text-cyan-400">{b.branch_seed}</td>
                    <td className="py-2 px-3">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border",
                          band === "P10"
                            ? "bg-emerald-950/60 text-emerald-300 border-emerald-800"
                            : band === "P50"
                            ? "bg-blue-950/60 text-blue-300 border-blue-800"
                            : band === "P90"
                            ? "bg-amber-950/60 text-amber-300 border-amber-800"
                            : "bg-red-950/60 text-red-300 border-red-800"
                        )}
                      >
                        {band}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-mono font-bold text-white">
                      {outcome.score ?? b.score}
                    </td>
                    <td className="py-2 px-3">
                      <span className={cn(
                        "text-[11px] font-mono",
                        outcome.mission_success !== false ? "text-emerald-400" : "text-red-400"
                      )}>
                        {outcome.mission_success !== false ? "SUCCESS" : "ABORTED"}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-mono text-[#A0A0A0]">
                      {outcome.fuel_delta_liters ?? 0}L
                    </td>
                    <td className="py-2 px-3 font-mono text-amber-400">
                      {outcome.incidents_count ?? 0}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
