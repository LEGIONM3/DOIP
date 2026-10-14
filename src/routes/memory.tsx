import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  rememberMemory,
  retrieveMemories,
  consolidateMemories,
  getMemorySummary,
  type AgentMemory,
} from "@/services/memory";
import {
  Brain,
  Search,
  Database,
  RefreshCw,
  Sparkles,
  Bookmark,
  Layers,
  FileText,
  Plus,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/memory")({
  head: () => ({
    meta: [
      { title: "Long-Term Memory Explorer — DOIP" },
      {
        name: "description",
        content: "Multi-tiered cognitive store: Semantic doctrine, episodic mission logs, and operational working memory.",
      },
    ],
  }),
  component: MemoryDashboard,
});

function MemoryDashboard() {
  const [memories, setMemories] = useState<AgentMemory[]>([]);
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);

  // New Memory Form
  const [newContent, setNewContent] = useState("");
  const [newType, setNewType] = useState<"semantic" | "episodic" | "operational">("semantic");
  const [newImportance, setNewImportance] = useState(1.0);
  const [storing, setStoring] = useState(false);

  const fetchMemories = async () => {
    setLoading(true);
    try {
      const [mList, sData] = await Promise.all([
        retrieveMemories(searchQuery || "*", undefined, selectedType || undefined),
        getMemorySummary(undefined, selectedType || undefined),
      ]);
      setMemories(mList);
      setSummary(sData.summary);
    } catch (err: any) {
      toast.error(`Error loading memory store: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemories();
  }, [selectedType]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetchMemories();
  };

  const handleConsolidate = async () => {
    try {
      const res = await consolidateMemories();
      toast.success(
        `Consolidated ${res.consolidated_into_semantic} episodes into semantic memory.`
      );
      fetchMemories();
    } catch (err: any) {
      toast.error(`Consolidation failed: ${err.message}`);
    }
  };

  const handleStoreMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;
    setStoring(true);
    try {
      await rememberMemory(
        newContent,
        newType,
        ["operator_noted"],
        newImportance
      );
      toast.success("Operational memory committed to store.");
      setNewContent("");
      fetchMemories();
    } catch (err: any) {
      toast.error(`Failed to store memory: ${err.message}`);
    } finally {
      setStoring(false);
    }
  };

  const getTypeBadge = (type: string) => {
    switch (type) {
      case "semantic":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "episodic":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
      case "operational":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
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
            <Brain className="w-6 h-6 text-purple-400" />
            <h1 className="text-xl font-bold tracking-wider uppercase text-zinc-100">
              Persistent Cognitive Memory Store
            </h1>
          </div>
          <p className="text-xs text-zinc-400 font-mono mt-1">
            Phase 5B Multi-Tiered Memory: Semantic Doctrine, Episodic Events, and Working Operational Context
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleConsolidate}
            className="flex items-center gap-2 px-3 py-1.5 bg-purple-950/60 border border-purple-800 hover:border-purple-600 text-xs font-mono rounded text-purple-300 transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Consolidate Episodes
          </button>
          <button
            onClick={fetchMemories}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-xs font-mono rounded text-zinc-200 transition-colors"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Total Memories"
            value={memories.length}
            sub="Indexed In Vector Store"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Semantic Doctrine"
            value={memories.filter((m) => m.memory_type === "semantic").length}
            sub="Permanent Knowledge"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Episodic Logs"
            value={memories.filter((m) => m.memory_type === "episodic").length}
            sub="Mission Timelines"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Operational Cache"
            value={memories.filter((m) => m.memory_type === "operational").length}
            sub="Working Telemetry"
          />
        </Panel>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Explorer */}
        <div className="lg:col-span-2 space-y-4">
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            {/* Search and Filters */}
            <form onSubmit={handleSearch} className="flex gap-2 mb-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-zinc-500" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search cognitive memory across doctrine and events..."
                  className="w-full pl-9 pr-3 py-2 bg-zinc-950 border border-zinc-800 rounded text-xs font-mono text-zinc-100 focus:outline-none focus:border-purple-500"
                />
              </div>
              <button
                type="submit"
                className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 border border-zinc-700 text-xs font-mono rounded text-zinc-200"
              >
                Search
              </button>
            </form>

            <div className="flex gap-1 mb-4 border-b border-zinc-800/80 pb-3">
              {["all", "semantic", "episodic", "operational"].map((t) => (
                <button
                  key={t}
                  onClick={() => setSelectedType(t === "all" ? null : t)}
                  className={cn(
                    "px-2.5 py-1 text-xs font-mono rounded border uppercase transition-colors",
                    (t === "all" && !selectedType) || selectedType === t
                      ? "bg-purple-500/20 border-purple-500/50 text-purple-300"
                      : "bg-zinc-950 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                  )}
                >
                  {t}
                </button>
              ))}
            </div>

            {/* Memories List */}
            <div className="space-y-3">
              {memories.map((m) => (
                <div
                  key={m.id}
                  className="p-3 bg-zinc-950/70 border border-zinc-800/80 rounded hover:border-zinc-700 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={cn(
                        "px-1.5 py-0.5 text-[9px] font-mono rounded border uppercase",
                        getTypeBadge(m.memory_type)
                      )}
                    >
                      {m.memory_type}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-500">
                      IMPORTANCE: {m.importance}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-200 mb-2 leading-relaxed">{m.content}</p>
                  <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 pt-2 border-t border-zinc-900">
                    <Mono>{m.id}</Mono>
                    <span>{new Date(m.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))}
              {memories.length === 0 && (
                <div className="text-center py-8 text-zinc-500 text-xs font-mono">
                  No memories found matching query.
                </div>
              )}
            </div>
          </Panel>
        </div>

        {/* Right Column: Commit New Memory & Consolidated Narrative */}
        <div className="space-y-4">
          {/* Commit Form */}
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center gap-2 mb-3 border-b border-zinc-800/80 pb-2">
              <Plus className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                Commit Observation
              </h2>
            </div>
            <form onSubmit={handleStoreMemory} className="space-y-3">
              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  MEMORY TIER
                </label>
                <select
                  value={newType}
                  onChange={(e: any) => setNewType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-zinc-100 focus:outline-none focus:border-purple-500"
                >
                  <option value="semantic">Semantic (Doctrine & Factual)</option>
                  <option value="episodic">Episodic (Historical Event)</option>
                  <option value="operational">Operational (Working State)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  IMPORTANCE RATING ({newImportance})
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.1"
                  value={newImportance}
                  onChange={(e) => setNewImportance(parseFloat(e.target.value))}
                  className="w-full accent-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  OBSERVATION CONTENT
                </label>
                <textarea
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder="Record tactical observation or doctrine guideline..."
                  rows={3}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-zinc-100 focus:outline-none focus:border-purple-500"
                />
              </div>

              <button
                type="submit"
                disabled={storing}
                className="w-full py-2 bg-purple-600 hover:bg-purple-500 text-zinc-950 font-semibold text-xs tracking-wider uppercase rounded transition-colors"
              >
                {storing ? "Committing..." : "Remember to Memory Store"}
              </button>
            </form>
          </Panel>

          {/* Consolidated Intelligence Summary */}
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center gap-2 mb-3 border-b border-zinc-800/80 pb-2">
              <FileText className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                Cognitive Summary
              </h2>
            </div>
            <pre className="text-xs font-mono text-zinc-300 whitespace-pre-wrap leading-relaxed bg-zinc-950/70 p-3 rounded border border-zinc-900">
              {summary || "Loading intelligence narrative..."}
            </pre>
          </Panel>
        </div>
      </div>
    </div>
  );
}
