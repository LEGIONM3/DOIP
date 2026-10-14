import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  listModels,
  routeModelTask,
  checkModelHealth,
  type ModelRecord,
  type ModelRouteResult,
} from "@/services/models";
import {
  Cpu,
  Layers,
  Activity,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Send,
  Zap,
  Shield,
  Server,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/models")({
  head: () => ({
    meta: [
      { title: "Model Management & Router — DOIP" },
      {
        name: "description",
        content: "Enterprise model governance, local GPU vs cloud routing, and dynamic task allocation.",
      },
    ],
  }),
  component: ModelsDashboard,
});

function ModelsDashboard() {
  const [models, setModels] = useState<ModelRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);

  // Dynamic Router Test
  const [routingTask, setRoutingTask] = useState("vision_adjudication");
  const [requireLocal, setRequireLocal] = useState(false);
  const [routeResult, setRouteResult] = useState<ModelRouteResult | null>(null);
  const [routing, setRouting] = useState(false);

  const fetchModels = async () => {
    setLoading(true);
    try {
      const data = await listModels(undefined, selectedType || undefined);
      setModels(data);
    } catch (err: any) {
      toast.error(`Error loading model registry: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, [selectedType]);

  const handleRouteTest = async (e: React.FormEvent) => {
    e.preventDefault();
    setRouting(true);
    try {
      const res = await routeModelTask(routingTask, "normal", requireLocal);
      setRouteResult(res);
      toast.success(`Task routed to: ${res.selected_model.name}`);
    } catch (err: any) {
      toast.error(`Routing failed: ${err.message}`);
    } finally {
      setRouting(false);
    }
  };

  const getModelTypeBadge = (type: string) => {
    switch (type) {
      case "llm":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
      case "vision":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "embedding":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "classifier":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      default:
        return "bg-zinc-800 text-zinc-400 border-zinc-700";
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-[1600px] mx-auto text-zinc-100">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="w-6 h-6 text-cyan-400" />
            <h1 className="text-xl font-bold tracking-wider uppercase text-zinc-100">
              Model Governance & Dynamic Task Router
            </h1>
          </div>
          <p className="text-xs text-zinc-400 font-mono mt-1">
            Phase 5I Multi-Provider AI Infrastructure: Local GPU, Ollama, HuggingFace, and Dynamic Task Routing
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchModels}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-xs font-mono rounded text-zinc-200 transition-colors"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
            Sync Registry
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat label="Total Models" value={models.length} sub="Registered Backends" />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Local Models"
            value={models.filter((m) => m.provider !== "openai").length}
            sub="Air-Gapped Operational"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Vision Analyzers"
            value={models.filter((m) => m.model_type === "vision").length}
            sub="YOLOv8 & Tracking"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Embedding Backends"
            value={models.filter((m) => m.model_type === "embedding").length}
            sub="Dense Doctrine RAG"
          />
        </Panel>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Model Catalog */}
        <div className="lg:col-span-2 space-y-4">
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center justify-between mb-4 border-b border-zinc-800/80 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                  Model Directory & Health
                </h2>
              </div>
              <div className="flex gap-1">
                {["all", "llm", "vision", "embedding", "classifier"].map((t) => (
                  <button
                    key={t}
                    onClick={() => setSelectedType(t === "all" ? null : t)}
                    className={cn(
                      "px-2.5 py-1 text-[10px] font-mono rounded border uppercase transition-colors",
                      (t === "all" && !selectedType) || selectedType === t
                        ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300"
                        : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {models.map((m) => (
                <div
                  key={m.id}
                  className="p-3 bg-zinc-950/70 border border-zinc-800/80 rounded space-y-2 hover:border-zinc-700 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-xs text-zinc-100">{m.name}</span>
                    <span
                      className={cn(
                        "px-1.5 py-0.5 text-[9px] font-mono rounded border uppercase",
                        getModelTypeBadge(m.model_type)
                      )}
                    >
                      {m.model_type}
                    </span>
                  </div>

                  <Mono className="text-[10px] text-zinc-500 block">{m.id}</Mono>

                  <div className="flex justify-between items-center text-[10px] font-mono text-zinc-400 pt-2 border-t border-zinc-900">
                    <span>PROVIDER: {m.provider.toUpperCase()}</span>
                    <span className="text-emerald-400 flex items-center gap-1">
                      <CheckCircle className="w-3 h-3" /> ONLINE
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* Right: Dynamic Task Router */}
        <div className="space-y-4">
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center gap-2 mb-3 border-b border-zinc-800/80 pb-2">
              <Zap className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                Dynamic Task Router Test
              </h2>
            </div>

            <form onSubmit={handleRouteTest} className="space-y-3">
              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  TACTICAL TASK
                </label>
                <select
                  value={routingTask}
                  onChange={(e) => setRoutingTask(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-zinc-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="vision_adjudication">Vision Object Adjudication</option>
                  <option value="rag_retrieve">Doctrine Vector Retrieval (RAG)</option>
                  <option value="strategic_planning">Multi-Theater Strategic Reasoning</option>
                  <option value="classification">Fast Intent Classification</option>
                </select>
              </div>

              <div className="flex items-center gap-2 py-1">
                <input
                  type="checkbox"
                  id="requireLocal"
                  checked={requireLocal}
                  onChange={(e) => setRequireLocal(e.target.checked)}
                  className="accent-cyan-500 rounded"
                />
                <label htmlFor="requireLocal" className="text-xs font-mono text-zinc-300">
                  Require Air-Gapped Local Model Only
                </label>
              </div>

              <button
                type="submit"
                disabled={routing}
                className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 text-zinc-950 font-semibold text-xs tracking-wider uppercase rounded transition-colors"
              >
                {routing ? "Evaluating Router..." : "Route Operational Task"}
              </button>
            </form>

            {routeResult && (
              <div className="mt-4 p-3 bg-zinc-950/80 rounded border border-zinc-900 space-y-2 text-xs font-mono">
                <div className="flex justify-between items-center text-cyan-300 font-bold">
                  <span>SELECTED BACKEND:</span>
                  <span>{routeResult.selected_model.name}</span>
                </div>
                <div className="text-[10px] text-zinc-400">
                  {routeResult.routing_reason}
                </div>
                <div className="text-[10px] text-zinc-500">
                  PROVIDER: {routeResult.selected_model.provider}
                </div>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
