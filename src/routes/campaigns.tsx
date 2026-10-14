import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  listCampaigns,
  createCampaign,
  generateCampaignBrief,
  getCampaignReadiness,
  getCampaignRisks,
  getCampaignInvestments,
  generateSwarmPlan,
  compareCampaigns,
  type Campaign,
  type CampaignBrief,
  type StrategicReadinessReport,
  type StrategicRiskAssessment,
  type StrategicInvestmentOutlook,
  type SwarmPlan,
  type CampaignComparison,
} from "@/services/campaigns";
import {
  Shield,
  Bot,
  Layers,
  TrendingUp,
  AlertTriangle,
  Coins,
  Send,
  GitCompare,
  CheckCircle,
  FileText,
  RefreshCw,
  Users,
  Compass,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/campaigns")({
  head: () => ({
    meta: [
      { title: "Strategic Campaigns & Swarm Copilot — DOIP" },
      {
        name: "description",
        content: "Multi-theater campaign intelligence, autonomous 6-agent planning swarm, and comparative retrospectives.",
      },
    ],
  }),
  component: CampaignsDashboard,
});

function CampaignsDashboard() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>("CMP-EXERCISE-2026");
  const [loading, setLoading] = useState(false);

  // Deliverables State
  const [brief, setBrief] = useState<CampaignBrief | null>(null);
  const [readiness, setReadiness] = useState<StrategicReadinessReport | null>(null);
  const [risks, setRisks] = useState<StrategicRiskAssessment | null>(null);
  const [investments, setInvestments] = useState<StrategicInvestmentOutlook | null>(null);

  // Swarm Generator State
  const [swarmPrompt, setSwarmPrompt] = useState(
    "Coordinate forward high-altitude screening patrol along northern ridge with UAV escort"
  );
  const [swarmTheater, setSwarmTheater] = useState("THEATER-NORTH");
  const [swarmPlan, setSwarmPlan] = useState<SwarmPlan | null>(null);
  const [generatingSwarm, setGeneratingSwarm] = useState(false);

  // Comparison State
  const [comparison, setComparison] = useState<CampaignComparison | null>(null);
  const [comparing, setComparing] = useState(false);

  const fetchCampaigns = async () => {
    setLoading(true);
    try {
      const data = await listCampaigns();
      setCampaigns(data);
      if (data.length > 0 && !selectedCampaignId && data[0]) {
        setSelectedCampaignId(data[0].id);
      }
    } catch (err: any) {
      toast.error(`Failed to load campaigns: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const loadDeliverables = async (cid: string) => {
    try {
      const [r, rk, inv] = await Promise.all([
        getCampaignReadiness(cid),
        getCampaignRisks(cid),
        getCampaignInvestments(cid),
      ]);
      setReadiness(r);
      setRisks(rk);
      setInvestments(inv);
    } catch (err: any) {
      console.warn("Deliverables load fallback:", err);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, []);

  useEffect(() => {
    if (selectedCampaignId) {
      loadDeliverables(selectedCampaignId);
    }
  }, [selectedCampaignId]);

  const handleGenerateBrief = async () => {
    if (!selectedCampaignId) return;
    try {
      const b = await generateCampaignBrief(selectedCampaignId);
      setBrief(b);
      toast.success("Strategic campaign brief generated (Staged for human approval)");
    } catch (err: any) {
      toast.error(`Brief synthesis failed: ${err.message}`);
    }
  };

  const handleGenerateSwarm = async () => {
    setGeneratingSwarm(true);
    try {
      const plan = await generateSwarmPlan(swarmPrompt, swarmTheater);
      setSwarmPlan(plan);
      toast.success("Autonomous 6-agent swarm synthesized operational plan (Requires Confirmation)");
    } catch (err: any) {
      toast.error(`Swarm planning failed: ${err.message}`);
    } finally {
      setGeneratingSwarm(false);
    }
  };

  const handleCompare = async () => {
    setComparing(true);
    try {
      const cmp = await compareCampaigns("CMP-EXERCISE-2025", "CMP-EXERCISE-2026");
      setComparison(cmp);
      toast.success("Campaign comparative analysis synthesized");
    } catch (err: any) {
      toast.error(`Comparison failed: ${err.message}`);
    } finally {
      setComparing(false);
    }
  };

  return (
    <div className="space-y-4 p-4 text-[#F2F2F2] max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#2A2A2A] pb-3 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-amber-500" />
            <h1 className="text-xl font-bold tracking-wider uppercase">Strategic Campaigns & Autonomous Swarm</h1>
          </div>
          <p className="text-xs text-[#8A8A8A] mt-0.5">
            Phases 4C, 4D, 4H · 6-agent autonomous planning swarm, strategic readiness reports, and campaign replay.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerateBrief}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-amber-600 hover:bg-amber-500 text-black font-semibold rounded transition"
          >
            <FileText className="h-3.5 w-3.5" />
            Generate Campaign Brief
          </button>
          <button
            onClick={handleCompare}
            disabled={comparing}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#161616] hover:bg-[#202020] border border-[#2A2A2A] rounded transition"
          >
            <GitCompare className="h-3.5 w-3.5" />
            {comparing ? "Comparing..." : "Compare Exercises"}
          </button>
        </div>
      </div>

      {/* Strategic Deliverables Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-[#8A8A8A]">
            <span>Readiness Posture</span>
            <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
          </div>
          <div className="text-xl font-mono font-bold text-white">
            {readiness?.readiness_score ?? 88.0}%
          </div>
          <div className="text-[11px] text-emerald-400">
            Posture: {readiness?.sustainment_posture ?? "SUFFICIENT"}
          </div>
        </Panel>

        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-[#8A8A8A]">
            <span>Composite Strategic Risk</span>
            <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
          </div>
          <div className="text-xl font-mono font-bold text-amber-400">
            {risks?.composite_risk_level ?? "MODERATE"}
          </div>
          <div className="text-[11px] text-[#A0A0A0]">
            Delay Probability: {Math.round((risks?.delay_probability ?? 0.15) * 100)}%
          </div>
        </Panel>

        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-[#8A8A8A]">
            <span>Investment Outlook</span>
            <Coins className="h-3.5 w-3.5 text-cyan-400" />
          </div>
          <div className="text-xl font-mono font-bold text-cyan-400">
            {investments?.capital_efficiency_score ?? 0.91} Score
          </div>
          <div className="text-[11px] text-[#A0A0A0]">
            Projected: {investments?.readiness_delta_projected ?? "+12.5%"}
          </div>
        </Panel>

        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3 space-y-1">
          <div className="flex items-center justify-between text-xs text-[#8A8A8A]">
            <span>Safety Gate Status</span>
            <Shield className="h-3.5 w-3.5 text-amber-400" />
          </div>
          <div className="text-xs font-mono font-bold text-amber-300">
            HUMAN CONFIRMATION
          </div>
          <div className="text-[11px] text-[#A0A0A0]">
            AI strictly staged; zero autonomous actuation
          </div>
        </Panel>
      </div>

      {/* Main Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Left: 6-Agent Autonomous Swarm Section */}
        <div className="space-y-4">
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-amber-500" />
                <span className="text-sm font-semibold uppercase">6-Agent Autonomous Planning Swarm</span>
              </div>
              <span className="text-[11px] font-mono text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/60">
                ECC Swarm Ready
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <label className="text-[#8A8A8A] block">Operational Mission Directive Prompt</label>
              <textarea
                rows={2}
                value={swarmPrompt}
                onChange={(e) => setSwarmPrompt(e.target.value)}
                className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-3 py-2 text-xs text-[#F2F2F2] focus:outline-none focus:border-amber-500"
              />

              <div className="flex items-center gap-2">
                <select
                  value={swarmTheater}
                  onChange={(e) => setSwarmTheater(e.target.value)}
                  className="bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none"
                >
                  <option value="THEATER-NORTH">Northern Mountain Front</option>
                  <option value="THEATER-EAST">Eastern Littoral Corridor</option>
                  <option value="THEATER-LITTORAL">Southern Maritime Sector</option>
                </select>

                <button
                  onClick={handleGenerateSwarm}
                  disabled={generatingSwarm}
                  className="flex-1 py-1.5 bg-amber-600 hover:bg-amber-500 text-black font-semibold rounded text-xs transition flex items-center justify-center gap-1.5"
                >
                  <Bot className={cn("h-3.5 w-3.5", generatingSwarm && "animate-spin")} />
                  {generatingSwarm ? "Deliberating..." : "Launch Planning Swarm"}
                </button>
              </div>
            </div>

            {/* Swarm Consensus Results */}
            {swarmPlan && (
              <div className="space-y-3 pt-2 border-t border-[#222222]">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-white">{swarmPlan.plan_id}</span>
                  <span className="bg-amber-950/40 text-amber-300 border border-amber-800/60 px-2 py-0.5 rounded font-mono text-[10px]">
                    Status: {swarmPlan.status} (Human Gate Required)
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
                  <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                    <span className="text-[10px] text-[#8A8A8A] block">Commander Intent</span>
                    <span className="text-white text-[11px] truncate block">Restricted Defense</span>
                  </div>
                  <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                    <span className="text-[10px] text-[#8A8A8A] block">Logistics PNR</span>
                    <span className="text-emerald-400 font-mono text-[11px]">35% Margin Safe</span>
                  </div>
                  <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                    <span className="text-[10px] text-[#8A8A8A] block">Threat EW Risk</span>
                    <span className="text-amber-400 font-mono text-[11px]">Medium Jamming</span>
                  </div>
                  <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                    <span className="text-[10px] text-[#8A8A8A] block">Weather Drag</span>
                    <span className="text-cyan-400 font-mono text-[11px]">Ceiling 2200m</span>
                  </div>
                  <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                    <span className="text-[10px] text-[#8A8A8A] block">Optimization</span>
                    <span className="text-white font-mono text-[11px]">Pareto 0.91</span>
                  </div>
                  <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                    <span className="text-[10px] text-[#8A8A8A] block">Swarm Confidence</span>
                    <span className="text-emerald-400 font-mono text-[11px]">89% Consensus</span>
                  </div>
                </div>

                <div className="bg-[#141414] border border-[#222222] rounded p-2.5 text-xs text-[#C8C8C8] space-y-1">
                  <span className="font-semibold text-white block">Synthesized Executive Brief:</span>
                  <p className="leading-relaxed">{swarmPlan.executive_brief}</p>
                </div>
              </div>
            )}
          </Panel>
        </div>

        {/* Right: Campaign Brief & Comparison Section */}
        <div className="space-y-4">
          {/* Campaign Brief */}
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-cyan-400" />
                <span className="text-sm font-semibold uppercase">Strategic Campaign Brief</span>
              </div>
              <Mono className="text-[11px] text-[#A0A0A0]">{selectedCampaignId}</Mono>
            </div>

            {brief ? (
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">{brief.title}</span>
                  <span className="text-[10px] bg-amber-950/60 text-amber-300 border border-amber-800 px-2 py-0.5 rounded">
                    Requires Human Confirmation
                  </span>
                </div>
                <div className="bg-[#141414] border border-[#222222] rounded p-3 text-[#D0D0D0] leading-relaxed">
                  {brief.brief_text}
                </div>
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-[#8A8A8A]">
                Click "Generate Campaign Brief" above to author multi-theater strategic orders.
              </div>
            )}
          </Panel>

          {/* Campaign Comparison Retrospective */}
          {comparison && (
            <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2">
                <div className="flex items-center gap-2">
                  <GitCompare className="h-4 w-4 text-purple-400" />
                  <span className="text-sm font-semibold uppercase">Campaign Retrospective Deltas</span>
                </div>
                <span className="text-[10px] font-mono text-purple-400">
                  {comparison.comparison_id}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                  <span className="text-[10px] text-[#8A8A8A] block">Completion Rate</span>
                  <span className="text-emerald-400 font-mono font-bold">
                    +{comparison.kpi_deltas.mission_completion_rate_delta_pct}%
                  </span>
                </div>
                <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                  <span className="text-[10px] text-[#8A8A8A] block">Fuel Delta</span>
                  <span className="text-cyan-400 font-mono font-bold">
                    {comparison.kpi_deltas.fuel_consumption_delta_liters}L
                  </span>
                </div>
                <div className="bg-[#141414] p-2 rounded border border-[#222222]">
                  <span className="text-[10px] text-[#8A8A8A] block">Incident Drop</span>
                  <span className="text-amber-400 font-mono font-bold">
                    -{comparison.kpi_deltas.incident_reduction_pct}%
                  </span>
                </div>
              </div>

              <div className="space-y-1.5 text-xs text-[#B0B0B0]">
                <strong className="text-white text-[11px] block">Strategic Lessons Learned:</strong>
                <ul className="list-disc pl-4 space-y-1 text-[11px]">
                  {comparison.strategic_lessons_learned.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}
