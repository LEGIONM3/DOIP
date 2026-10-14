import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  getAnalyticsDashboard,
  generateForecastMatrix,
  runMassiveWhatIf,
  type AnalyticsDashboard,
  type ForecastMatrix,
  type WhatIfBatchResult,
} from "@/services/analyticsPlatform";
import { generateReport, type OperationalReport } from "@/services/reports";
import {
  BarChart3,
  TrendingUp,
  Activity,
  Shield,
  FileText,
  Zap,
  RefreshCw,
  Fuel,
  Compass,
  CheckCircle,
  Copy,
  Sliders,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/analytics-center")({
  head: () => ({
    meta: [
      { title: "Operational Analytics & Reporting Center — DOIP" },
      {
        name: "description",
        content: "Enterprise operational intelligence, KPI tracking, automated SITREPs, and large-scale forecasting.",
      },
    ],
  }),
  component: AnalyticsDashboardView,
});

function AnalyticsDashboardView() {
  const [dashboard, setDashboard] = useState<AnalyticsDashboard | null>(null);
  const [forecast, setForecast] = useState<ForecastMatrix | null>(null);
  const [whatif, setWhatif] = useState<WhatIfBatchResult | null>(null);
  const [sitrep, setSitrep] = useState<OperationalReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const data = await getAnalyticsDashboard();
      setDashboard(data);
    } catch (err: any) {
      toast.error(`Error loading analytics dashboard: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  const handleGenerateSitrep = async () => {
    setGeneratingReport(true);
    try {
      const rep = await generateReport("sitrep", "THEATER-NORTH");
      setSitrep(rep);
      toast.success("Commander's Daily SITREP generated successfully.");
    } catch (err: any) {
      toast.error(`Failed to generate SITREP: ${err.message}`);
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleRunForecast = async () => {
    try {
      const f = await generateForecastMatrix(["THEATER-NORTH", "THEATER-CENTRAL", "THEATER-SOUTH"]);
      setForecast(f);
      toast.success(`Generated ${f.horizon_hours}h predictive matrix across 3 theaters.`);
    } catch (err: any) {
      toast.error(`Forecast generation failed: ${err.message}`);
    }
  };

  const handleRunWhatIf = async () => {
    try {
      const res = await runMassiveWhatIf(100);
      setWhatif(res);
      toast.success(`Executed 100 deterministic scenarios. Mean score: ${res.comparison["mean_score"]}`);
    } catch (err: any) {
      toast.error(`What-If batch failed: ${err.message}`);
    }
  };

  const kpis = dashboard?.kpis || {};
  const resources = dashboard?.resources || {};
  const readiness = dashboard?.readiness || {};

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto text-zinc-100">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-emerald-400" />
            <h1 className="text-xl font-bold tracking-wider uppercase text-zinc-100">
              Operational Analytics & Reporting Center
            </h1>
          </div>
          <p className="text-xs text-zinc-400 font-mono mt-1">
            Phase 5F & 5K Enterprise Operational KPI Monitoring, SITREP Synthesis, and Large-Scale Risk Matrices
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleGenerateSitrep}
            disabled={generatingReport}
            className="flex items-center gap-2 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 text-zinc-950 font-semibold text-xs tracking-wider uppercase rounded transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            {generatingReport ? "Generating..." : "Generate Daily SITREP"}
          </button>
          <button
            onClick={fetchDashboard}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-xs font-mono rounded text-zinc-200 transition-colors"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
            Sync KPIs
          </button>
        </div>
      </div>

      {/* Top Level KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Mission Success Rate"
            value={`${((kpis["mission_success_rate"] ?? 0.942) * 100).toFixed(1)}%`}
            sub="Historical 24h Window"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Fleet Readiness"
            value={`${kpis["fleet_readiness_pct"] ?? 88.5}%`}
            sub="Composite Operational"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Resource Utilization"
            value={`${kpis["resource_utilization_pct"] ?? 76.2}%`}
            sub="Stockpile Burn Rate"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Forecast Accuracy"
            value={`${kpis["forecast_accuracy_pct"] ?? 91.8}%`}
            sub="Prediction Alignment"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Route Efficiency"
            value={`${kpis["route_efficiency_index"] ?? 1.18}x`}
            sub="Geodesic Detour Ratio"
          />
        </Panel>
      </div>

      {/* Analytics Main Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Resources, Readiness, What-If & Forecast */}
        <div className="lg:col-span-2 space-y-6">
          {/* Resource & Readiness Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Logistics & Fuel */}
            <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
              <div className="flex items-center gap-2 mb-3 border-b border-zinc-800/80 pb-2">
                <Fuel className="w-4 h-4 text-amber-400" />
                <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                  Logistics & Stockpiles
                </h2>
              </div>
              <div className="space-y-3 text-xs font-mono">
                <div className="p-3 bg-zinc-950/60 rounded border border-zinc-900">
                  <div className="flex justify-between text-zinc-400 mb-1">
                    <span>Class III (Fuel Reserves):</span>
                    <span className="text-amber-400 font-bold">
                      {resources["class_iii_fuel"]?.["current_stock_liters"]?.toLocaleString() || "342,000"} L
                    </span>
                  </div>
                  <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                    <div className="bg-amber-500 h-full w-[76%]" />
                  </div>
                  <span className="text-[10px] text-zinc-500 mt-1 block">
                    Days of Supply: {resources["class_iii_fuel"]?.["days_of_supply"] || "7.7"} days
                  </span>
                </div>

                <div className="p-3 bg-zinc-950/60 rounded border border-zinc-900">
                  <div className="flex justify-between text-zinc-400 mb-1">
                    <span>Class V (Ammunition):</span>
                    <span className="text-emerald-400 font-bold">92.4% Optimal</span>
                  </div>
                  <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden">
                    <div className="bg-emerald-500 h-full w-[92%]" />
                  </div>
                </div>
              </div>
            </Panel>

            {/* Asset Readiness */}
            <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
              <div className="flex items-center gap-2 mb-3 border-b border-zinc-800/80 pb-2">
                <Shield className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                  Hardware Readiness
                </h2>
              </div>
              <div className="space-y-2.5 text-xs font-mono">
                <div className="flex justify-between items-center p-2 bg-zinc-950/60 rounded border border-zinc-900">
                  <span>Armored Vehicles (AFVs):</span>
                  <span className="text-emerald-400">58 / 64 (90.6%)</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-zinc-950/60 rounded border border-zinc-900">
                  <span>Tactical UAV Swarm:</span>
                  <span className="text-emerald-400">16 / 18 (88.9%)</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-zinc-950/60 rounded border border-zinc-900">
                  <span>C4ISR Relay Masts:</span>
                  <span className="text-emerald-400">12 / 12 (100.0%)</span>
                </div>
              </div>
            </Panel>
          </div>

          {/* Interactive Simulation Engines: Massive What-If & Forecast Matrix */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Large-Scale Forecast Matrix */}
            <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
              <div className="flex items-center justify-between mb-3 border-b border-zinc-800/80 pb-2">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                  <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                    Forecast Risk Tensors
                  </h2>
                </div>
                <button
                  onClick={handleRunForecast}
                  className="px-2.5 py-1 bg-cyan-950/60 border border-cyan-800 hover:border-cyan-600 text-[10px] font-mono rounded text-cyan-300"
                >
                  Generate 4h Matrix
                </button>
              </div>

              {forecast ? (
                <div className="space-y-2 text-xs font-mono">
                  {Object.entries(forecast.risk_tensor).map(([theater, metrics]: [string, any]) => (
                    <div key={theater} className="p-2.5 bg-zinc-950/70 rounded border border-zinc-900">
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-semibold text-zinc-200">{theater}</span>
                        <span className="text-amber-400">Risk: {metrics.composite_risk_score}</span>
                      </div>
                      <div className="text-[10px] text-zinc-400 flex justify-between">
                        <span>P50: {metrics.timelines.p50_completion_ticks} ticks</span>
                        <span>Rating: {metrics.risk_rating}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-6 text-center text-zinc-500 text-xs font-mono">
                  Click 'Generate 4h Matrix' to compute multi-theater risk tensors.
                </div>
              )}
            </Panel>

            {/* Massive What-If Engine */}
            <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
              <div className="flex items-center justify-between mb-3 border-b border-zinc-800/80 pb-2">
                <div className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-purple-400" />
                  <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                    Massive What-If Engine
                  </h2>
                </div>
                <button
                  onClick={handleRunWhatIf}
                  className="px-2.5 py-1 bg-purple-950/60 border border-purple-800 hover:border-purple-600 text-[10px] font-mono rounded text-purple-300"
                >
                  Run 100 Scenarios
                </button>
              </div>

              {whatif ? (
                <div className="space-y-2 text-xs font-mono">
                  <div className="p-2.5 bg-zinc-950/70 rounded border border-zinc-900">
                    <div className="flex justify-between mb-1">
                      <span>Total Scenarios:</span>
                      <span className="text-purple-400 font-bold">{whatif.total_scenarios}</span>
                    </div>
                    <div className="flex justify-between mb-1">
                      <span>Mean Score:</span>
                      <span className="text-emerald-400 font-bold">{whatif.comparison["mean_score"]} / 100</span>
                    </div>
                    <div className="flex justify-between text-zinc-400 text-[10px]">
                      <span>Best: {whatif.comparison["best_score"]}</span>
                      <span>Worst: {whatif.comparison["worst_score"]}</span>
                    </div>
                  </div>
                  <div className="text-[10px] text-zinc-500">
                    Rank 1 Seed: {whatif.ranked_top_10[0]?.scenario_seed} (Score: {whatif.ranked_top_10[0]?.score})
                  </div>
                </div>
              ) : (
                <div className="py-6 text-center text-zinc-500 text-xs font-mono">
                  Click 'Run 100 Scenarios' to execute Monte-Carlo parameter variations.
                </div>
              )}
            </Panel>
          </div>
        </div>

        {/* Right Col: SITREP Markdown Preview */}
        <div className="space-y-4">
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800 h-full flex flex-col">
            <div className="flex items-center justify-between mb-3 border-b border-zinc-800/80 pb-2">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                  Daily SITREP Output
                </h2>
              </div>
              {sitrep && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(sitrep.content_md);
                    toast.success("SITREP copied to clipboard.");
                  }}
                  className="p-1 hover:bg-zinc-800 rounded text-zinc-400 hover:text-zinc-200"
                  title="Copy Markdown"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {sitrep ? (
              <div className="flex-1 bg-zinc-950/80 p-3 rounded border border-zinc-900 overflow-y-auto max-h-[550px]">
                <pre className="text-xs font-mono text-zinc-300 whitespace-pre-wrap leading-relaxed">
                  {sitrep.content_md}
                </pre>
              </div>
            ) : (
              <div className="flex-1 bg-zinc-950/40 p-6 rounded border border-zinc-900/60 flex flex-col items-center justify-center text-zinc-500 text-xs font-mono">
                <FileText className="w-8 h-8 mb-2 opacity-30" />
                <span>No SITREP generated yet.</span>
                <span className="text-[10px]">Click &apos;Generate Daily SITREP&apos; above.</span>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
