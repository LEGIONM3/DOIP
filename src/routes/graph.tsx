import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  fetchSubgraph,
  fetchRootCause,
  fetchDependencies,
  seedDemoGraph,
  type SubgraphResponse,
  type RootCauseResponse,
  type DependencyResponse,
  type GraphNode,
} from "@/services/graph";
import {
  GitCommit,
  GitFork,
  Network,
  RefreshCw,
  Search,
  ShieldAlert,
  Sliders,
  Workflow,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/graph")({
  head: () => ({
    meta: [
      { title: "Operational Knowledge Graph & Causal Analysis — DOIP" },
      {
        name: "description",
        content: "NetworkX-powered operational knowledge graph, causal incident root-cause attribution, and dependency single-point-of-failure analysis.",
      },
    ],
  }),
  component: KnowledgeGraphVisualizer,
});

const TYPE_COLORS: Record<string, string> = {
  MISSION: "border-blue-500/50 bg-blue-950/30 text-blue-300",
  UNIT: "border-emerald-500/50 bg-emerald-950/30 text-emerald-300",
  ASSET: "border-purple-500/50 bg-purple-950/30 text-purple-300",
  INCIDENT: "border-rose-500/50 bg-rose-950/30 text-rose-300",
  ROUTE: "border-amber-500/50 bg-amber-950/30 text-amber-300",
  WEATHER: "border-cyan-500/50 bg-cyan-950/30 text-cyan-300",
  DOCTRINE: "border-indigo-500/50 bg-indigo-950/30 text-indigo-300",
};

function KnowledgeGraphVisualizer() {
  const [subgraph, setSubgraph] = useState<SubgraphResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [rootCauseResult, setRootCauseResult] = useState<RootCauseResponse | null>(null);
  const [dependenciesResult, setDependenciesResult] = useState<DependencyResponse | null>(null);
  const [depth, setDepth] = useState(2);
  const [searchFilter, setSearchFilter] = useState("");

  async function loadGraph(centerId?: string) {
    setLoading(true);
    try {
      const data = await fetchSubgraph(centerId, depth);
      setSubgraph(data);
      if (data.nodes.length > 0 && !selectedNode && data.nodes[0]) {
        handleSelectNode(data.nodes[0]);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to load operational subgraph");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectNode(node: GraphNode) {
    setSelectedNode(node);
    if (node.type === "INCIDENT") {
      try {
        const rc = await fetchRootCause(node.id);
        setRootCauseResult(rc);
      } catch {
        setRootCauseResult(null);
      }
    } else {
      setRootCauseResult(null);
    }

    try {
      const deps = await fetchDependencies(node.id);
      setDependenciesResult(deps);
    } catch {
      setDependenciesResult(null);
    }
  }

  async function handleSeed() {
    setLoading(true);
    try {
      const res = await seedDemoGraph();
      toast.success(`Seeded demo graph: ${res.nodes} nodes, ${res.edges} edges`);
      loadGraph();
    } catch (err: any) {
      toast.error(err.message || "Failed to seed demo graph");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadGraph();
  }, [depth]);

  const filteredNodes = (subgraph?.nodes || []).filter(
    (n) =>
      n.id.toLowerCase().includes(searchFilter.toLowerCase()) ||
      n.label.toLowerCase().includes(searchFilter.toLowerCase()) ||
      n.type.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="flex w-full flex-col gap-2 p-2">
      {/* Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border border-border bg-surface p-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center border border-primary/30 bg-primary/10 text-primary">
            <Network className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-sm font-semibold tracking-wider uppercase text-foreground">
              Operational Knowledge Graph &amp; Causal Analysis
            </h1>
            <p className="text-[11px] text-muted-foreground font-mono">
              NetworkX MultiDiGraph Engine &bull; Causal Attribution &bull; Single-Point-of-Failure Detector
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-muted-foreground font-mono">Ego Depth:</span>
            <select
              value={depth}
              onChange={(e) => setDepth(parseInt(e.target.value, 10))}
              className="border border-border bg-surface-2 px-2 py-1 text-xs font-mono text-foreground outline-none"
            >
              <option value={1}>Depth 1 (Direct)</option>
              <option value={2}>Depth 2 (Transitive)</option>
              <option value={3}>Depth 3 (Ecosystem)</option>
            </select>
          </div>

          <button
            onClick={handleSeed}
            disabled={loading}
            className="flex items-center gap-1.5 border border-border bg-surface-2 px-2.5 py-1 text-xs text-foreground hover:bg-surface-3 transition-colors"
          >
            <Zap className="h-3.5 w-3.5 text-amber-400" />
            Seed Demo Graph
          </button>

          <button
            onClick={() => loadGraph(selectedNode?.id)}
            disabled={loading}
            className="flex items-center gap-1.5 border border-primary bg-primary/20 px-3 py-1 text-xs font-medium text-primary hover:bg-primary/30 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Main 3-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2 flex-1 min-h-0">
        {/* Left Column: Entity Node Registry */}
        <Panel
          title={
            <div className="flex items-center justify-between w-full pr-2">
              <span>Entity Directory ({filteredNodes.length})</span>
              <span className="text-[10px] text-muted-foreground font-mono">
                {subgraph?.total_nodes || 0} Nodes / {subgraph?.total_links || 0} Links
              </span>
            </div>
          }
        >
          <div className="flex flex-col gap-2 h-full">
            <div className="relative">
              <Search className="absolute left-2 top-2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Filter entities..."
                className="w-full border border-border bg-surface-2 pl-7 pr-2 py-1 text-xs font-mono text-foreground outline-none"
              />
            </div>

            <div className="flex flex-col gap-1 overflow-y-auto max-h-[500px]">
              {filteredNodes.map((node) => {
                const colorCls = TYPE_COLORS[node.type] || "border-border bg-surface-2 text-foreground";
                const isSelected = selectedNode?.id === node.id;
                return (
                  <button
                    key={node.id}
                    onClick={() => handleSelectNode(node)}
                    className={cn(
                      "flex items-center justify-between border p-2 text-left text-xs transition-colors",
                      colorCls,
                      isSelected && "ring-1 ring-primary brightness-125"
                    )}
                  >
                    <div>
                      <div className="font-mono font-bold">{node.id}</div>
                      <div className="text-[11px] opacity-80 truncate">{node.label}</div>
                    </div>
                    <span className="font-mono text-[9px] uppercase px-1 py-0.5 border border-current">
                      {node.type}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </Panel>

        {/* Center Column: Node Details & Relational Links */}
        <Panel title={selectedNode ? `Entity: ${selectedNode.id}` : "Entity Details"}>
          {selectedNode ? (
            <div className="flex flex-col gap-3">
              <div className="border border-border bg-surface-2 p-3">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-foreground">{selectedNode.label}</span>
                  <span className="font-mono text-[10px] uppercase px-1.5 py-0.5 border border-primary text-primary">
                    {selectedNode.type}
                  </span>
                </div>
                {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
                  <div className="mt-2 text-[11px] font-mono text-muted-foreground grid grid-cols-2 gap-1">
                    {Object.entries(selectedNode.properties).map(([k, v]) => (
                      <div key={k}>
                        <span className="opacity-70">{k}:</span>{" "}
                        <span className="text-foreground">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Active Relational Edges */}
              <div>
                <h3 className="text-xs font-mono font-semibold uppercase text-muted-foreground mb-1.5">
                  Direct Relations in Ego Graph
                </h3>
                <div className="flex flex-col gap-1 max-h-[300px] overflow-y-auto">
                  {(subgraph?.links || [])
                    .filter((l) => l.source === selectedNode.id || l.target === selectedNode.id)
                    .map((l, idx) => {
                      const isOut = l.source === selectedNode.id;
                      const partnerId = isOut ? l.target : l.source;
                      return (
                        <div
                          key={idx}
                          className="flex items-center justify-between border border-border bg-surface-2 p-1.5 text-xs font-mono"
                        >
                          <span className="text-muted-foreground flex items-center gap-1">
                            {isOut ? (
                              <>
                                &rarr; <span className="text-primary">{l.relation}</span>
                              </>
                            ) : (
                              <>
                                &larr; <span className="text-amber-400">{l.relation}</span>
                              </>
                            )}
                          </span>
                          <span className="text-foreground font-semibold">{partnerId}</span>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-xs text-muted-foreground p-4 text-center">
              Select an entity node from the registry to inspect relations.
            </div>
          )}
        </Panel>

        {/* Right Column: Causal Root-Cause & Single Points of Failure */}
        <Panel title="Causal Attribution & SPOF Analysis">
          <div className="flex flex-col gap-3">
            {/* Causal Analysis */}
            {rootCauseResult ? (
              <div className="border border-rose-500/40 bg-rose-950/20 p-3">
                <div className="flex items-center gap-2 text-rose-400 text-xs font-bold uppercase tracking-wider">
                  <ShieldAlert className="h-4 w-4" /> Root Cause Attribution
                </div>
                <div className="mt-2 text-xs font-mono">
                  <span className="text-muted-foreground">Origin Trigger:</span>{" "}
                  <span className="font-bold text-foreground">{rootCauseResult.root_cause_label}</span> (
                  {rootCauseResult.root_cause_type})
                </div>
                <div className="text-[11px] font-mono text-muted-foreground mt-1">
                  Attribution Score: {(rootCauseResult.attribution_score * 100).toFixed(0)}%
                </div>
                <p className="mt-2 text-xs text-foreground/90">{rootCauseResult.summary}</p>

                {/* Ordered Causal Chain */}
                <div className="mt-3 flex flex-col gap-1">
                  <span className="text-[10px] font-mono uppercase text-muted-foreground font-semibold">
                    Directed Causal Progression:
                  </span>
                  {rootCauseResult.causal_chain.map((c) => (
                    <div
                      key={c.step}
                      className="flex items-center gap-2 text-[11px] font-mono border-l-2 border-primary pl-2 py-0.5"
                    >
                      <span className="text-primary font-bold">Step {c.step}:</span>
                      <span className="text-foreground">{c.label}</span>
                      <span className="text-[9px] uppercase px-1 py-0.2 border text-muted-foreground">
                        {c.role}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="border border-border bg-surface-2 p-3 text-xs text-muted-foreground font-mono">
                Select an <span className="text-rose-400 font-bold">INCIDENT</span> node to compute causal root-cause attribution.
              </div>
            )}

            {/* Single Points of Failure */}
            {dependenciesResult?.single_points_of_failure && dependenciesResult.single_points_of_failure.length > 0 && (
              <div className="border border-amber-500/40 bg-amber-950/20 p-3">
                <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-wider">
                  <GitFork className="h-4 w-4" /> Single Points of Failure (SPOF)
                </div>
                <div className="flex flex-col gap-1.5 mt-2">
                  {dependenciesResult.single_points_of_failure.map((spof) => (
                    <div
                      key={spof.asset_id}
                      className="flex items-center justify-between border border-amber-500/30 bg-surface-2 p-1.5 text-xs font-mono"
                    >
                      <div>
                        <span className="font-bold text-foreground">{spof.label}</span>
                        <span className="text-[10px] text-muted-foreground ml-2">({spof.asset_id})</span>
                      </div>
                      <span className="px-1.5 py-0.5 text-[10px] font-bold border border-amber-400 text-amber-400">
                        {spof.dependent_count} DEPENDENTS
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
