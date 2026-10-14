import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  listFederationNodes,
  broadcastDirective,
  synchronizeIntelligence,
  type FederationNode,
} from "@/services/federation";
import {
  Radio,
  Server,
  Shield,
  Layers,
  Send,
  RefreshCw,
  Share2,
  CheckCircle,
  AlertCircle,
  Clock,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/federation")({
  head: () => ({
    meta: [
      { title: "Federated Command Mesh — DOIP" },
      {
        name: "description",
        content: "Decentralized multi-tier command hierarchy: Regional Strategic, Operational Theater, and Tactical nodes.",
      },
    ],
  }),
  component: FederationDashboard,
});

function FederationDashboard() {
  const [nodes, setNodes] = useState<FederationNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTier, setSelectedTier] = useState<string | null>(null);

  // Directive Broadcast Form State
  const [directiveTitle, setDirectiveTitle] = useState("Operational Readiness Directive");
  const [directiveContent, setDirectiveContent] = useState("Disperse reconnaissance UAV assets along perimeter corridors.");
  const [targetTier, setTargetTier] = useState("operational");
  const [broadcasting, setBroadcasting] = useState(false);

  // Intelligence Sync State
  const [intelKind, setIntelKind] = useState("RADAR_EMISSION_SPIKE");
  const [intelSector, setIntelSector] = useState("SECTOR-NORTH-RIDGE");
  const [syncing, setSyncing] = useState(false);

  const fetchNodes = async () => {
    setLoading(true);
    try {
      const data = await listFederationNodes(selectedTier || undefined);
      setNodes(data);
    } catch (err: any) {
      toast.error(`Error loading federation nodes: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNodes();
  }, [selectedTier]);

  const handleBroadcast = async () => {
    if (!directiveTitle || !directiveContent) {
      toast.error("Please provide both directive title and content");
      return;
    }
    setBroadcasting(true);
    try {
      const results = await broadcastDirective(
        "NODE-REGIONAL-HQ",
        directiveTitle,
        directiveContent,
        targetTier
      );
      toast.success(`Directive cascaded to ${results.length} nodes (Staged for Human Approval)`);
      fetchNodes();
    } catch (err: any) {
      toast.error(`Broadcast failed: ${err.message}`);
    } finally {
      setBroadcasting(false);
    }
  };

  const handleSyncIntel = async () => {
    setSyncing(true);
    try {
      const res = await synchronizeIntelligence("NODE-REGIONAL-HQ", intelKind, {
        sector: intelSector,
        detected_at: new Date().toISOString(),
        threat_level: "HIGH",
      });
      toast.success(`Intelligence synced to ${res.synced_nodes_count} federated nodes`);
      fetchNodes();
    } catch (err: any) {
      toast.error(`Intelligence sync failed: ${err.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const regionalCount = nodes.filter((n) => n.tier === "regional").length;
  const operationalCount = nodes.filter((n) => n.tier === "operational").length;
  const tacticalCount = nodes.filter((n) => n.tier === "tactical").length;

  return (
    <div className="space-y-4 p-4 text-[#F2F2F2] max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-[#2A2A2A] pb-3 gap-2">
        <div>
          <div className="flex items-center gap-2">
            <Radio className="h-5 w-5 text-amber-500 animate-pulse" />
            <h1 className="text-xl font-bold tracking-wider uppercase">Federated Command Architecture</h1>
          </div>
          <p className="text-xs text-[#8A8A8A] mt-0.5">
            Phase 4A · Multi-region, multi-theater synchronized intelligence and command hierarchy.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchNodes}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#161616] hover:bg-[#202020] border border-[#2A2A2A] rounded transition"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh Mesh
          </button>
        </div>
      </div>

      {/* KPI Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat label="Total Active Nodes" value={nodes.length} sub="Synchronized" />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat label="Regional Strategic" value={regionalCount} sub="Tier 1 Commands" />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat label="Operational Theaters" value={operationalCount} sub="Tier 2 Commands" />
        </Panel>
        <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-3">
          <Stat label="Tactical Units" value={tacticalCount} sub="Battle-space Nodes" />
        </Panel>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Node Topology Column */}
        <div className="lg:col-span-2 space-y-4">
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4">
            <div className="flex items-center justify-between border-b border-[#2A2A2A] pb-2 mb-3">
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-cyan-400" />
                <span className="text-sm font-semibold uppercase">Command Mesh Hierarchy</span>
              </div>
              <div className="flex gap-1 text-xs">
                {(["all", "regional", "operational", "tactical"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setSelectedTier(t === "all" ? null : t)}
                    className={cn(
                      "px-2 py-0.5 rounded capitalize",
                      (selectedTier === t || (t === "all" && !selectedTier))
                        ? "bg-amber-500 text-black font-semibold"
                        : "bg-[#161616] text-[#8A8A8A] hover:bg-[#202020]"
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2.5">
              {nodes.map((node) => (
                <div
                  key={node.id}
                  className="bg-[#141414] border border-[#242424] rounded p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:border-[#383838] transition"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-sm">{node.name}</span>
                      <span
                        className={cn(
                          "text-[10px] uppercase px-1.5 py-0.5 rounded font-mono font-medium border",
                          node.tier === "regional"
                            ? "bg-purple-950/60 text-purple-300 border-purple-800"
                            : node.tier === "operational"
                            ? "bg-blue-950/60 text-blue-300 border-blue-800"
                            : "bg-emerald-950/60 text-emerald-300 border-emerald-800"
                        )}
                      >
                        {node.tier}
                      </span>
                      <span className="flex items-center gap-1 text-[11px] text-emerald-400">
                        <CheckCircle className="h-3 w-3" />
                        Online
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-[#8A8A8A]">
                      <Mono className="text-[11px] text-[#A0A0A0]">{node.id}</Mono>
                      <span>Region: {node.region}</span>
                      {node.endpoint && <span className="font-mono text-[10px] text-cyan-400">{node.endpoint}</span>}
                    </div>
                  </div>

                  <div className="flex sm:flex-col items-end gap-1 text-xs text-[#8A8A8A]">
                    <div className="flex items-center gap-1 text-[11px]">
                      <Layers className="h-3 w-3 text-amber-400" />
                      <span>{node.directives_count ?? 0} Directives</span>
                    </div>
                    <div className="flex items-center gap-1 text-[11px]">
                      <Share2 className="h-3 w-3 text-cyan-400" />
                      <span>{node.intelligence_count ?? 0} Intel Syncs</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* Control Side Panel */}
        <div className="space-y-4">
          {/* Directive Cascade Card */}
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4">
            <div className="flex items-center gap-2 border-b border-[#2A2A2A] pb-2 mb-3">
              <Send className="h-4 w-4 text-amber-500" />
              <span className="text-sm font-semibold uppercase">Cascade Strategic Directive</span>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-[#8A8A8A] block mb-1">Directive Title</label>
                <input
                  type="text"
                  value={directiveTitle}
                  onChange={(e) => setDirectiveTitle(e.target.value)}
                  className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none focus:border-amber-500"
                />
              </div>

              <div>
                <label className="text-[#8A8A8A] block mb-1">Target Command Tier</label>
                <select
                  value={targetTier}
                  onChange={(e) => setTargetTier(e.target.value)}
                  className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none focus:border-amber-500"
                >
                  <option value="operational">Operational Theaters</option>
                  <option value="tactical">Tactical Units</option>
                  <option value="all">All Tiers (Network-Wide)</option>
                </select>
              </div>

              <div>
                <label className="text-[#8A8A8A] block mb-1">Directive Content</label>
                <textarea
                  rows={3}
                  value={directiveContent}
                  onChange={(e) => setDirectiveContent(e.target.value)}
                  className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="p-2.5 bg-amber-950/30 border border-amber-800/60 rounded flex items-start gap-2">
                <Shield className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <span className="text-[11px] text-amber-200">
                  Directives are staged with <strong className="font-mono">requires_human_confirmation: true</strong>. Local human command approval is mandatory before asset execution.
                </span>
              </div>

              <button
                onClick={handleBroadcast}
                disabled={broadcasting}
                className="w-full py-2 bg-amber-600 hover:bg-amber-500 text-black font-semibold text-xs rounded transition flex items-center justify-center gap-1.5"
              >
                <Send className="h-3.5 w-3.5" />
                {broadcasting ? "Cascading..." : "Cascade Directive"}
              </button>
            </div>
          </Panel>

          {/* Synchronize Intelligence Card */}
          <Panel className="bg-[#0D0D0D] border-[#2A2A2A] p-4">
            <div className="flex items-center gap-2 border-b border-[#2A2A2A] pb-2 mb-3">
              <Share2 className="h-4 w-4 text-cyan-400" />
              <span className="text-sm font-semibold uppercase">Synchronize Intelligence</span>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-[#8A8A8A] block mb-1">Intelligence Kind</label>
                <select
                  value={intelKind}
                  onChange={(e) => setIntelKind(e.target.value)}
                  className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none focus:border-cyan-500"
                >
                  <option value="RADAR_EMISSION_SPIKE">Radar Emission Spike</option>
                  <option value="EW_JAMMING_CORRIDOR">EW Jamming Corridor</option>
                  <option value="DEFCON_ADVISORY">DEFCON Readiness Advisory</option>
                  <option value="WEATHER_HAZARD_ALERT">Weather Hazard Alert</option>
                </select>
              </div>

              <div>
                <label className="text-[#8A8A8A] block mb-1">Target Sector / Coordinates</label>
                <input
                  type="text"
                  value={intelSector}
                  onChange={(e) => setIntelSector(e.target.value)}
                  className="w-full bg-[#161616] border border-[#2A2A2A] rounded px-2.5 py-1.5 text-xs text-[#F2F2F2] focus:outline-none focus:border-cyan-500"
                />
              </div>

              <button
                onClick={handleSyncIntel}
                disabled={syncing}
                className="w-full py-2 bg-cyan-700 hover:bg-cyan-600 text-white font-semibold text-xs rounded transition flex items-center justify-center gap-1.5"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", syncing && "animate-spin")} />
                {syncing ? "Replicating..." : "Replicate Intelligence"}
              </button>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
