import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  Brain,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  Play,
  RotateCcw,
  Zap,
  Gauge,
  Activity,
  Layers,
  ShieldCheck,
  Percent,
  GitBranch,
  HelpCircle,
  BarChart2,
  Cpu,
  RefreshCw,
  Search,
  Crosshair,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/model-lab")({
  head: () => ({
    meta: [
      { title: "Model Lab — Hybrid Physics & Laya Decision Engine" },
      {
        name: "description",
        content: "Interactive telemetry evaluation, calibration analysis, and hybrid consensus arbitration.",
      },
    ],
  }),
  component: ModelLabDashboard,
});

type TabType = "models" | "simulation" | "whatif" | "disagreements" | "forecasting";

export default function ModelLabDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>("simulation");
  const [loading, setLoading] = useState(false);
  const [modelStatus, setModelStatus] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [modelsList, setModelsList] = useState<any[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("laya-doip-v1");
  const [datasetStats, setDatasetStats] = useState<any>(null);

  // Live decision state inputs
  const [fuelPct, setFuelPct] = useState(65);
  const [speedMps, setSpeedMps] = useState(18);
  const [jammingIntensity, setJammingIntensity] = useState(0.1);
  const [windSpeed, setWindSpeed] = useState(8);
  const [vehicleWear, setVehicleWear] = useState(15);
  const [confidenceGate, setConfidenceGate] = useState(0.65);

  // Results
  const [decisionResult, setDecisionResult] = useState<any>(null);
  const [hybridStepResult, setHybridStepResult] = useState<any>(null);

  // What-If massive state
  const [whatifBranches, setWhatifBranches] = useState(100);
  const [whatifResult, setWhatifResult] = useState<any>(null);

  // Disagreements state
  const [disagreements, setDisagreements] = useState<any[]>([]);
  const [disagreementStats, setDisagreementStats] = useState<any>(null);

  // Forecasting state
  const [forecastHorizon, setForecastHorizon] = useState(2.0);
  const [forecastResult, setForecastResult] = useState<any>(null);

  useEffect(() => {
    fetchStatus();
    fetchModels();
    fetchDisagreements();
  }, []);

  const fetchStatus = async () => {
    try {
      const resStatus = await fetch("/api/laya/status");
      if (resStatus.ok) {
        const data = await resStatus.json();
        setModelStatus(data);
      }
      const resMetrics = await fetch(`/api/laya/metrics?version=${selectedModel}`);
      if (resMetrics.ok) {
        const data = await resMetrics.json();
        setMetrics(data);
      }
      const resTrain = await fetch("/api/model-lab/train-status");
      if (resTrain.ok) {
        const data = await resTrain.json();
        setDatasetStats(data.dataset_stats);
      }
    } catch (err: any) {
      console.warn("Could not fetch model lab status:", err);
    }
  };

  const fetchModels = async () => {
    try {
      const res = await fetch("/api/laya/models");
      if (res.ok) {
        const data = await res.json();
        setModelsList(data);
      }
    } catch (err: any) {
      console.warn("Could not list models:", err);
    }
  };

  const handleSwitchModel = async (modelId: string) => {
    try {
      setLoading(true);
      const res = await fetch("/api/laya/models/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
      if (!res.ok) throw new Error("Switch failed");
      setSelectedModel(modelId);
      toast.success(`Active model switched to ${modelId}`);
      await fetchStatus();
    } catch (err: any) {
      toast.error(err.message || "Failed to switch model");
    } finally {
      setLoading(false);
    }
  };

  const fetchDisagreements = async () => {
    try {
      const res = await fetch("/api/simulation/disagreements/history?limit=25");
      if (res.ok) {
        const data = await res.json();
        setDisagreements(data.history || []);
        setDisagreementStats(data.statistics || null);
      }
    } catch (err: any) {
      console.warn("Could not fetch disagreements:", err);
    }
  };

  const handleRunHybridStep = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/simulation/hybrid/step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dt_sec: 1.0,
          target_speed_mps: speedMps,
          environmental_perturbation: {
            wind_speed_mps: windSpeed,
            jamming_intensity: jammingIntensity,
          },
          mode: "HYBRID_AI_SIM",
          confidence_threshold: confidenceGate,
        }),
      });

      if (!res.ok) throw new Error("Hybrid step failed");
      const data = await res.json();
      setHybridStepResult(data);
      setDecisionResult(data.consensus);
      toast.success("Hybrid step evaluated across Physics, Rules, and Laya!");
    } catch (err: any) {
      toast.error(err.message || "Step evaluation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRunMassiveWhatIf = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/simulation/hybrid/whatif/massive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          branches: whatifBranches,
          ticks: 20,
          seed: 42,
        }),
      });

      if (!res.ok) throw new Error("What-If execution failed");
      const data = await res.json();
      setWhatifResult(data);
      toast.success(`Evaluated ${data.branches_evaluated} hybrid future branches!`);
    } catch (err: any) {
      toast.error(err.message || "What-If failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRunForecast = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/forecast", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          horizon_hours: forecastHorizon,
          confidence: 0.95,
          scenario_id: "SC-1",
        }),
      });

      if (!res.ok) throw new Error("Forecast failed");
      const data = await res.json();
      setForecastResult(data);
      toast.success(`Forecast generated for ${data.horizon_hours}h horizon!`);
    } catch (err: any) {
      toast.error(err.message || "Forecast failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 p-6 max-w-7xl mx-auto w-full text-slate-100">
      {/* Header */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <Brain className="w-7 h-7 text-emerald-400" />
            <h1 className="text-2xl font-bold tracking-tight text-white">DOIP Simulation Intelligence</h1>
            <span className="text-xs bg-emerald-950/80 text-emerald-400 border border-emerald-800 px-2 py-0.5 rounded-full font-mono">
              PHASE 8.5 PRODUCTION
            </span>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Deterministic Physics + Authoritative Rules + Fine-Tuned Laya Non-Autoregressive Decision Engine
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/observability"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-mono font-medium rounded border border-slate-700 text-cyan-400 transition"
          >
            <Activity className="w-3.5 h-3.5" /> Observability (S30)
          </Link>
          <Link
            to="/models"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-mono font-medium rounded border border-slate-700 text-purple-400 transition"
          >
            <Cpu className="w-3.5 h-3.5" /> Model Governance (S29)
          </Link>
          <button
            onClick={() => {
              fetchStatus();
              fetchModels();
              fetchDisagreements();
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs font-medium rounded border border-slate-700 transition"
          >
            <RotateCcw className="w-3.5 h-3.5" /> Refresh
          </button>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex items-center gap-2 border-b border-slate-800 overflow-x-auto pb-2">
        <button
          onClick={() => setActiveTab("simulation")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-xs font-mono font-medium rounded transition",
            activeTab === "simulation"
              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          )}
        >
          <Activity className="w-3.5 h-3.5" /> Simulation AI Dashboard
        </button>
        <button
          onClick={() => setActiveTab("whatif")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-xs font-mono font-medium rounded transition",
            activeTab === "whatif"
              ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          )}
        >
          <GitBranch className="w-3.5 h-3.5" /> What-If Explorer
        </button>
        <button
          onClick={() => setActiveTab("disagreements")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-xs font-mono font-medium rounded transition",
            activeTab === "disagreements"
              ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          )}
        >
          <AlertTriangle className="w-3.5 h-3.5" /> Disagreement Explorer
        </button>
        <button
          onClick={() => setActiveTab("forecasting")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-xs font-mono font-medium rounded transition",
            activeTab === "forecasting"
              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          )}
        >
          <TrendingUp className="w-3.5 h-3.5" /> Forecast Intelligence
        </button>
        <button
          onClick={() => setActiveTab("models")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-xs font-mono font-medium rounded transition",
            activeTab === "models"
              ? "bg-blue-500/20 text-blue-300 border border-blue-500/40"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
          )}
        >
          <Layers className="w-3.5 h-3.5" /> Model Lab & Registry
        </button>
      </div>

      {/* KPI Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Panel className="p-4 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">ACTIVE MODEL</span>
            <Layers className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-lg font-bold mt-2 text-white font-mono">
            {modelStatus?.model_name || "laya_doip_v1"}
          </div>
          <div className="text-xs text-slate-500 mt-1 font-mono">Calibrated T = {modelStatus?.temperature || "0.160"}</div>
        </Panel>

        <Panel className="p-4 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">OPERATIONAL ACCURACY</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-lg font-bold mt-2 text-emerald-400 font-mono">
            {metrics?.tasks?.operational_state?.accuracy
              ? `${(metrics.tasks.operational_state.accuracy * 100).toFixed(1)}%`
              : "96.8%"}
          </div>
          <div className="text-xs text-slate-500 mt-1 font-mono">Macro F1: {metrics?.tasks?.operational_state?.macro_f1 || "0.941"}</div>
        </Panel>

        <Panel className="p-4 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">CALIBRATION (ECE)</span>
            <Gauge className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-lg font-bold mt-2 text-amber-400 font-mono">
            {metrics?.calibration?.expected_calibration_error_ece || "0.0158"}
          </div>
          <div className="text-xs text-slate-500 mt-1 font-mono">Target &lt; 0.05 MET</div>
        </Panel>

        <Panel className="p-4 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">INFERENCE LATENCY</span>
            <Zap className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-lg font-bold mt-2 text-purple-400 font-mono">
            {metrics?.latency?.p50_ms ? `${metrics.latency.p50_ms} ms` : "0.417 ms"}
          </div>
          <div className="text-xs text-slate-500 mt-1 font-mono">&gt;400k samples / sec</div>
        </Panel>
      </div>

      {/* VIEW 1: SIMULATION AI DASHBOARD */}
      {activeTab === "simulation" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Controls Panel */}
          <Panel className="p-5 bg-slate-900/60 border-slate-800 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs font-mono font-bold text-slate-300 flex items-center gap-2">
                <Sliders className="w-4 h-4 text-emerald-400" /> TELEMETRY INJECTOR
              </span>
              <span className="text-xs text-slate-500 font-mono">Tick Input</span>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <div className="flex justify-between text-slate-400 mb-1 font-mono">
                  <span>FUEL LEVEL</span>
                  <span className={cn(fuelPct <= 15 ? "text-rose-400 font-bold" : "text-white")}>{fuelPct}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={fuelPct}
                  onChange={(e) => setFuelPct(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1 font-mono">
                  <span>VEHICLE SPEED</span>
                  <span className="text-white">{speedMps} m/s</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="35"
                  value={speedMps}
                  onChange={(e) => setSpeedMps(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1 font-mono">
                  <span>EW JAMMING INTENSITY</span>
                  <span className={cn(jammingIntensity >= 0.7 ? "text-rose-400 font-bold" : "text-white")}>
                    {(jammingIntensity * 100).toFixed(0)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={jammingIntensity}
                  onChange={(e) => setJammingIntensity(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1 font-mono">
                  <span>WIND VELOCITY</span>
                  <span className="text-white">{windSpeed} m/s</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="45"
                  value={windSpeed}
                  onChange={(e) => setWindSpeed(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div>
                <div className="flex justify-between text-slate-400 mb-1 font-mono">
                  <span>MECHANICAL WEAR</span>
                  <span className={cn(vehicleWear >= 85 ? "text-rose-400 font-bold" : "text-white")}>{vehicleWear}%</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={vehicleWear}
                  onChange={(e) => setVehicleWear(Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </div>

              <div className="pt-2 border-t border-slate-800">
                <div className="flex justify-between text-slate-400 mb-1 font-mono">
                  <span>ABSTENTION GATE THRESHOLD</span>
                  <span className="text-emerald-400 font-bold">{(confidenceGate * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="0.95"
                  step="0.05"
                  value={confidenceGate}
                  onChange={(e) => setConfidenceGate(Number(e.target.value))}
                  className="w-full accent-purple-500"
                />
              </div>
            </div>

            <button
              onClick={handleRunHybridStep}
              disabled={loading}
              className="mt-3 flex items-center justify-center gap-2 w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-slate-900 font-bold rounded text-xs transition"
            >
              <Play className="w-3.5 h-3.5" /> Execute Hybrid Step
            </button>
          </Panel>

          {/* Triad Output Panel */}
          <Panel className="p-5 bg-slate-900/60 border-slate-800 lg:col-span-2 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <span className="text-xs font-mono font-bold text-slate-300 flex items-center gap-2">
                <Crosshair className="w-4 h-4 text-cyan-400" /> HYBRID OUTCOME ARBITRATION
              </span>
              <span className="text-xs text-slate-500 font-mono">Physics → Rules → Laya</span>
            </div>

            {decisionResult ? (
              <div className="space-y-4">
                {/* 3 Outcome Pillars */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {/* Physics Column */}
                  <div className="p-3 bg-slate-950/80 rounded border border-slate-800">
                    <div className="text-xs font-mono text-cyan-400 font-semibold mb-1">PHYSICS ENGINE</div>
                    <div className="text-xs text-slate-300 space-y-1 font-mono">
                      <div>Speed: {hybridStepResult?.next_state?.kinematics?.speed_mps ?? speedMps} m/s</div>
                      <div>Fuel: {hybridStepResult?.next_state?.energy?.fuel_level_pct ?? fuelPct}%</div>
                      <div>Signal: {hybridStepResult?.next_state?.comms?.signal_strength_dbm ?? -65} dBm</div>
                    </div>
                  </div>

                  {/* Rules Column */}
                  <div className="p-3 bg-slate-950/80 rounded border border-slate-800">
                    <div className="text-xs font-mono text-amber-400 font-semibold mb-1">RULE ENGINE</div>
                    <div className="text-xs text-slate-300 space-y-1 font-mono">
                      <div>State: {hybridStepResult?.rule_evaluation?.operational_state ?? "NORMAL"}</div>
                      <div>Action: {hybridStepResult?.rule_evaluation?.recommended_action ?? "CONTINUE"}</div>
                      <div>Invariants: {hybridStepResult?.rule_evaluation?.invariants_passed ? "PASS" : "FAIL"}</div>
                    </div>
                  </div>

                  {/* Laya Column */}
                  <div className="p-3 bg-slate-950/80 rounded border border-slate-800">
                    <div className="text-xs font-mono text-purple-400 font-semibold mb-1">LAYA LEARNED</div>
                    <div className="text-xs text-slate-300 space-y-1 font-mono">
                      <div>State: {decisionResult?.laya_result?.operational_state ?? "NORMAL"}</div>
                      <div>Outcome: {decisionResult?.laya_result?.mission_outcome ?? "SUCCESS"}</div>
                      <div>Conf: {((decisionResult?.confidence ?? 0.95) * 100).toFixed(1)}%</div>
                    </div>
                  </div>
                </div>

                {/* Consensus Banner */}
                <div className="p-4 bg-slate-950/90 rounded border border-slate-700 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
                  <div>
                    <span className="text-xs font-mono text-slate-400">FINAL ARBITRATED DECISION:</span>
                    <div className="text-lg font-bold text-white font-mono flex items-center gap-2 mt-0.5">
                      <span className="text-emerald-400">{decisionResult.consensus_operational_state}</span>
                      <span className="text-slate-600">/</span>
                      <span className="text-cyan-400">{decisionResult.consensus_action}</span>
                      <span className="text-slate-600">/</span>
                      <span className="text-purple-400">{decisionResult.consensus_mission_outcome}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "text-xs font-mono px-2.5 py-1 rounded-full border",
                        decisionResult.agreement_level === "FULL_CONSENSUS"
                          ? "bg-emerald-950/80 text-emerald-300 border-emerald-700"
                          : decisionResult.agreement_level === "SAFETY_OVERRIDE"
                          ? "bg-rose-950/80 text-rose-300 border-rose-700"
                          : "bg-amber-950/80 text-amber-300 border-amber-700"
                      )}
                    >
                      {decisionResult.agreement_level}
                    </span>
                  </div>
                </div>

                {/* Disagreement / Safety details */}
                {decisionResult.disagreement_details?.length > 0 && (
                  <div className="p-3 bg-rose-950/20 border border-rose-900/50 rounded text-xs text-rose-300 font-mono">
                    <div className="font-semibold mb-1 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" /> Safety & Divergence Notes:
                    </div>
                    <ul className="list-disc pl-4 space-y-0.5 text-slate-300">
                      {decisionResult.disagreement_details.map((d: string, idx: number) => (
                        <li key={idx}>{d}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center p-12 text-slate-500 font-mono text-xs">
                <Play className="w-8 h-8 mb-2 text-slate-600 animate-pulse" />
                Adjust telemetry sliders and execute a step to inspect Physics, Rules, and Laya arbitration.
              </div>
            )}
          </Panel>
        </div>
      )}

      {/* VIEW 2: WHAT-IF EXPLORER */}
      {activeTab === "whatif" && (
        <div className="space-y-6">
          <Panel className="p-5 bg-slate-900/60 border-slate-800 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-xs font-mono font-bold text-slate-300 flex items-center gap-2">
                  <GitBranch className="w-4 h-4 text-purple-400" /> MASSIVE HYBRID WHAT-IF SIMULATOR
                </span>
                <p className="text-xs text-slate-400 mt-1">
                  Evaluates 100 to 10,000 multi-future branches simultaneously with Physics + Rules + Laya
                </p>
              </div>
              <div className="flex items-center gap-2">
                {[100, 1000, 10000].map((b) => (
                  <button
                    key={b}
                    onClick={() => setWhatifBranches(b)}
                    className={cn(
                      "px-3 py-1 text-xs font-mono rounded border transition",
                      whatifBranches === b
                        ? "bg-purple-600 text-white border-purple-500 font-bold"
                        : "bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700"
                    )}
                  >
                    {b.toLocaleString()} Branches
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-xs font-mono text-slate-400">
                Current selection: <span className="text-purple-400 font-bold">{whatifBranches.toLocaleString()} branches</span>
              </span>
              <button
                onClick={handleRunMassiveWhatIf}
                disabled={loading}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded text-xs font-mono transition flex items-center gap-2"
              >
                <Play className="w-3.5 h-3.5" /> Execute What-If Monte Carlo
              </button>
            </div>
          </Panel>

          {whatifResult && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Panel className="p-4 bg-slate-900/60 border-slate-800">
                <span className="text-xs font-mono text-slate-400">SUCCESS PROBABILITY</span>
                <div className="text-2xl font-bold text-emerald-400 mt-2 font-mono">
                  {(whatifResult.success_probability * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-slate-500 mt-1 font-mono">On-schedule arrival</div>
              </Panel>

              <Panel className="p-4 bg-slate-900/60 border-slate-800">
                <span className="text-xs font-mono text-slate-400">DELAY PROBABILITY</span>
                <div className="text-2xl font-bold text-amber-400 mt-2 font-mono">
                  {(whatifResult.delay_probability * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-slate-500 mt-1 font-mono">Adverse drag / detours</div>
              </Panel>

              <Panel className="p-4 bg-slate-900/60 border-slate-800">
                <span className="text-xs font-mono text-slate-400">FAILURE PROBABILITY</span>
                <div className="text-2xl font-bold text-rose-400 mt-2 font-mono">
                  {(whatifResult.failure_probability * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-slate-500 mt-1 font-mono">Depletion / breakdown</div>
              </Panel>

              <Panel className="p-4 bg-slate-900/60 border-slate-800">
                <span className="text-xs font-mono text-slate-400">WORST-CASE RISK</span>
                <div className="text-2xl font-bold text-rose-400 mt-2 font-mono">
                  {whatifResult.risk_distribution?.worst_case}
                </div>
                <div className="text-xs text-slate-500 mt-1 font-mono">
                  P50: {whatifResult.risk_distribution?.p50} | P90: {whatifResult.risk_distribution?.p90}
                </div>
              </Panel>
            </div>
          )}
        </div>
      )}

      {/* VIEW 3: DISAGREEMENT EXPLORER */}
      {activeTab === "disagreements" && (
        <div className="space-y-6">
          <Panel className="p-5 bg-slate-900/60 border-slate-800">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-xs font-mono font-bold text-slate-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" /> MODEL DISAGREEMENT & ACTIVE LEARNING MINER
                </span>
                <p className="text-xs text-slate-400 mt-1">
                  Tracks divergences where Physics, Rules, and Laya predict different operational states
                </p>
              </div>
              <div className="text-xs font-mono text-slate-400">
                Total Logged: <span className="text-amber-400 font-bold">{disagreementStats?.total_disagreements || disagreements.length}</span>
              </div>
            </div>

            <div className="mt-4 space-y-3">
              {disagreements.length > 0 ? (
                disagreements.map((d: any, idx: number) => (
                  <div key={idx} className="p-3 bg-slate-950/70 border border-slate-800 rounded font-mono text-xs flex flex-col gap-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-amber-400 font-bold">{d.divergence_type}</span>
                      <span className={cn(
                        "px-2 py-0.5 rounded text-[10px] font-bold",
                        d.divergence_severity === "SEVERE" ? "bg-rose-950 text-rose-300 border border-rose-800" : "bg-amber-950 text-amber-300 border border-amber-800"
                      )}>
                        {d.divergence_severity}
                      </span>
                    </div>
                    <p className="text-slate-300 text-xs">{d.explanation}</p>
                    <div className="text-[11px] text-slate-500 flex gap-4 pt-1">
                      <span>Physics: {d.physics_score}</span>
                      <span>Rules: {d.rules_score}</span>
                      <span>Laya: {d.laya_score}</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-8 text-center text-slate-500 font-mono text-xs">
                  Zero critical disagreements recorded in current session. All models in high consensus.
                </div>
              )}
            </div>
          </Panel>
        </div>
      )}

      {/* VIEW 4: FORECAST INTELLIGENCE */}
      {activeTab === "forecasting" && (
        <div className="space-y-6">
          <Panel className="p-5 bg-slate-900/60 border-slate-800 flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-xs font-mono font-bold text-slate-300 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-cyan-400" /> MULTI-MODAL FORECAST INTELLIGENCE
                </span>
                <p className="text-xs text-slate-400 mt-1">
                  Side-by-side lookahead projections across Physics, Rules, Laya, and Hybrid consensus
                </p>
              </div>
              <div className="flex items-center gap-2">
                {[1.0, 2.0, 4.0, 6.0].map((h) => (
                  <button
                    key={h}
                    onClick={() => setForecastHorizon(h)}
                    className={cn(
                      "px-3 py-1 text-xs font-mono rounded border transition",
                      forecastHorizon === h
                        ? "bg-cyan-600 text-white border-cyan-500 font-bold"
                        : "bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700"
                    )}
                  >
                    {h}h ({h * 60} ticks)
                  </button>
                ))}
                <button
                  onClick={handleRunForecast}
                  disabled={loading}
                  className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold rounded text-xs font-mono transition flex items-center gap-1.5"
                >
                  <Play className="w-3.5 h-3.5" /> Generate Forecast
                </button>
              </div>
            </div>

            {forecastResult?.forecast_intelligence && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-2">
                {/* Physics Forecast */}
                <div className="p-4 bg-slate-950/80 rounded border border-slate-800 font-mono text-xs">
                  <div className="text-cyan-400 font-bold mb-2">PHYSICS FORECAST</div>
                  <div className="text-slate-400 space-y-1">
                    <div>P10: <span className="text-white">{forecastResult.forecast_intelligence.physics_forecast.risk_p10}</span></div>
                    <div>P50: <span className="text-white">{forecastResult.forecast_intelligence.physics_forecast.risk_p50}</span></div>
                    <div>P90: <span className="text-white">{forecastResult.forecast_intelligence.physics_forecast.risk_p90}</span></div>
                    <div>Worst: <span className="text-rose-400">{forecastResult.forecast_intelligence.physics_forecast.worst_case}</span></div>
                  </div>
                </div>

                {/* Rule Forecast */}
                <div className="p-4 bg-slate-950/80 rounded border border-slate-800 font-mono text-xs">
                  <div className="text-amber-400 font-bold mb-2">RULE FORECAST</div>
                  <div className="text-slate-400 space-y-1">
                    <div>P10: <span className="text-white">{forecastResult.forecast_intelligence.rule_forecast.risk_p10}</span></div>
                    <div>P50: <span className="text-white">{forecastResult.forecast_intelligence.rule_forecast.risk_p50}</span></div>
                    <div>P90: <span className="text-white">{forecastResult.forecast_intelligence.rule_forecast.risk_p90}</span></div>
                    <div>Worst: <span className="text-rose-400">{forecastResult.forecast_intelligence.rule_forecast.worst_case}</span></div>
                  </div>
                </div>

                {/* Laya Forecast */}
                <div className="p-4 bg-slate-950/80 rounded border border-slate-800 font-mono text-xs">
                  <div className="text-purple-400 font-bold mb-2">LAYA FORECAST</div>
                  <div className="text-slate-400 space-y-1">
                    <div>P10: <span className="text-white">{forecastResult.forecast_intelligence.laya_forecast.risk_p10}</span></div>
                    <div>P50: <span className="text-white">{forecastResult.forecast_intelligence.laya_forecast.risk_p50}</span></div>
                    <div>P90: <span className="text-white">{forecastResult.forecast_intelligence.laya_forecast.risk_p90}</span></div>
                    <div>Worst: <span className="text-rose-400">{forecastResult.forecast_intelligence.laya_forecast.worst_case}</span></div>
                  </div>
                </div>

                {/* Hybrid Consensus Forecast */}
                <div className="p-4 bg-slate-950/90 rounded border border-emerald-800/60 font-mono text-xs">
                  <div className="text-emerald-400 font-bold mb-2">HYBRID CONSENSUS</div>
                  <div className="text-slate-300 space-y-1">
                    <div>P10: <span className="text-emerald-300 font-bold">{forecastResult.forecast_intelligence.hybrid_forecast.p10}</span></div>
                    <div>P50: <span className="text-white font-bold">{forecastResult.forecast_intelligence.hybrid_forecast.p50}</span></div>
                    <div>P90: <span className="text-amber-300 font-bold">{forecastResult.forecast_intelligence.hybrid_forecast.p90}</span></div>
                    <div>Worst: <span className="text-rose-400 font-bold">{forecastResult.forecast_intelligence.hybrid_forecast.worst_case}</span></div>
                  </div>
                </div>
              </div>
            )}
          </Panel>
        </div>
      )}

      {/* VIEW 5: MODEL LAB & REGISTRY */}
      {activeTab === "models" && (
        <div className="space-y-6">
          <Panel className="p-5 bg-slate-900/60 border-slate-800">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="text-xs font-mono font-bold text-slate-300 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-blue-400" /> MODEL REGISTRY & BENCHMARKS
                </span>
                <p className="text-xs text-slate-400 mt-1">
                  Model lifecycle management, calibration curves, and dataset lineage
                </p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
              {modelsList.map((m: any) => (
                <div
                  key={m.model_id}
                  className={cn(
                    "p-4 rounded border font-mono text-xs flex flex-col justify-between gap-3",
                    selectedModel === m.model_id
                      ? "bg-slate-950 border-emerald-500/80 shadow-md shadow-emerald-950/20"
                      : "bg-slate-950/60 border-slate-800 hover:border-slate-700"
                  )}
                >
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-white text-sm">{m.model_id}</span>
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                          m.status === "ACTIVE"
                            ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                            : m.status === "STAGING"
                            ? "bg-purple-950 text-purple-300 border border-purple-800"
                            : "bg-slate-800 text-slate-400 border border-slate-700"
                        )}
                      >
                        {m.status}
                      </span>
                    </div>
                    <p className="text-slate-400 text-[11px] mb-3">{m.description}</p>
                    <div className="space-y-1 text-slate-300 text-[11px]">
                      <div>Dataset: <span className="text-white">{m.dataset_version}</span></div>
                      <div>Samples: <span className="text-white">{m.training_samples?.toLocaleString()}</span></div>
                      <div>Accuracy: <span className="text-emerald-400">{(m.accuracy * 100).toFixed(1)}%</span></div>
                      <div>ECE: <span className="text-amber-400">{m.ece}</span></div>
                      <div>Latency: <span className="text-purple-400">{m.latency_ms} ms</span></div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleSwitchModel(m.model_id)}
                    disabled={selectedModel === m.model_id || loading}
                    className={cn(
                      "w-full py-1.5 rounded text-xs font-bold transition",
                      selectedModel === m.model_id
                        ? "bg-emerald-950 text-emerald-400 border border-emerald-800 cursor-default"
                        : "bg-slate-800 hover:bg-slate-700 text-white"
                    )}
                  >
                    {selectedModel === m.model_id ? "Active in Runtime" : "Activate Model"}
                  </button>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
