import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import {
  listAgents,
  listAgentTasks,
  submitAgentTask,
  getAgentRuntimeStatus,
  type Agent,
  type AgentTask,
  type AgentRuntimeStatus,
} from "@/services/agentRuntime";
import {
  Bot,
  Cpu,
  Activity,
  Send,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Clock,
  Layers,
  Shield,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/agents")({
  head: () => ({
    meta: [
      { title: "Unified Agent Runtime — DOIP" },
      {
        name: "description",
        content: "Autonomous multi-agent lifecycle, coordination, and execution directory.",
      },
    ],
  }),
  component: AgentRuntimeDashboard,
});

function AgentRuntimeDashboard() {
  const [status, setStatus] = useState<AgentRuntimeStatus | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);

  // Task Submission State
  const [taskType, setTaskType] = useState("recon_analysis");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [rtStatus, agList, tList] = await Promise.all([
        getAgentRuntimeStatus(),
        listAgents(undefined, selectedRole || undefined),
        listAgentTasks(),
      ]);
      setStatus(rtStatus);
      setAgents(agList);
      setTasks(tList);
    } catch (err: any) {
      toast.error(`Error loading agent runtime: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedRole]);

  const handleSubmitTask = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await submitAgentTask(
        taskType,
        { origin: "agent_dashboard", requested_at: new Date().toISOString() },
        selectedAgentId || undefined
      );
      toast.success(`Task '${taskType}' dispatched to runtime.`);
      fetchData();
    } catch (err: any) {
      toast.error(`Task dispatch failed: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (st: string) => {
    switch (st) {
      case "idle":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "active":
      case "in_progress":
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
      case "busy":
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
            <Bot className="w-6 h-6 text-cyan-400" />
            <h1 className="text-xl font-bold tracking-wider uppercase text-zinc-100">
              Unified Agent Runtime
            </h1>
          </div>
          <p className="text-xs text-zinc-400 font-mono mt-1">
            Phase 5A Unified Autonomous Swarm & Advisory Runtime Control Center
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-xs font-mono rounded text-zinc-200 transition-colors"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
            Sync Swarm
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Active Agents"
            value={status?.active_agents_count ?? agents.length}
            sub="Registered In Swarm"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Queued Tasks"
            value={tasks.filter((t) => t.status === "pending").length}
            sub="Awaiting Execution"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Executed Tasks"
            value={tasks.filter((t) => t.status === "completed").length}
            sub="Completed (24h)"
          />
        </Panel>
        <Panel className="p-4 bg-zinc-900/60 border-zinc-800">
          <Stat
            label="Runtime Version"
            value={status?.runtime_version ?? "5.0.0"}
            sub="Unified Multi-Tier"
          />
        </Panel>
      </div>

      {/* Main Grid: Agents List & Task Dispatch */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Agent Directory */}
        <div className="lg:col-span-2 space-y-4">
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center justify-between mb-4 border-b border-zinc-800/80 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                  Registered Swarm Directory
                </h2>
              </div>
              <div className="flex gap-1">
                {["all", "copilot", "strategic_copilot", "red_team", "forecaster"].map((r) => (
                  <button
                    key={r}
                    onClick={() => setSelectedRole(r === "all" ? null : r)}
                    className={cn(
                      "px-2 py-0.5 text-[10px] font-mono rounded border uppercase transition-colors",
                      (r === "all" && !selectedRole) || selectedRole === r
                        ? "bg-cyan-500/20 border-cyan-500/50 text-cyan-300"
                        : "bg-zinc-900 border-zinc-800 text-zinc-400 hover:text-zinc-200"
                    )}
                  >
                    {r.replace("_", " ")}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {agents.map((ag) => (
                <div
                  key={ag.id}
                  className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded flex flex-col justify-between hover:border-zinc-700 transition-colors"
                >
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-semibold text-xs text-zinc-100">{ag.name}</span>
                      <span
                        className={cn(
                          "px-1.5 py-0.5 text-[9px] font-mono rounded border uppercase",
                          getStatusBadge(ag.status)
                        )}
                      >
                        {ag.status}
                      </span>
                    </div>
                    <Mono className="text-[10px] text-zinc-400 block mb-2">{ag.id}</Mono>
                    <div className="flex flex-wrap gap-1 mb-2">
                      {ag.capabilities?.slice(0, 3).map((cap) => (
                        <span
                          key={cap}
                          className="px-1.5 py-0.2 text-[9px] font-mono bg-zinc-900 text-zinc-300 rounded border border-zinc-800"
                        >
                          {cap.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="pt-2 border-t border-zinc-900 flex justify-between items-center text-[10px] font-mono text-zinc-500">
                    <span>ROLE: {ag.role.toUpperCase()}</span>
                    <span>ACTIVE</span>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          {/* Execution History */}
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center gap-2 mb-3 border-b border-zinc-800/80 pb-2">
              <Clock className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                Recent Task Execution Log
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-400">
                    <th className="py-2">TASK ID</th>
                    <th className="py-2">TYPE</th>
                    <th className="py-2">AGENT</th>
                    <th className="py-2">STATUS</th>
                    <th className="py-2 text-right">TIME</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900">
                  {tasks.slice(0, 8).map((t) => (
                    <tr key={t.id} className="hover:bg-zinc-900/30">
                      <td className="py-2 text-cyan-400">{t.id}</td>
                      <td className="py-2 text-zinc-200">{t.task_type}</td>
                      <td className="py-2 text-zinc-400">{t.agent_id || "autonomous"}</td>
                      <td className="py-2">
                        <span
                          className={cn(
                            "px-1.5 py-0.5 text-[9px] rounded border uppercase",
                            getStatusBadge(t.status)
                          )}
                        >
                          {t.status}
                        </span>
                      </td>
                      <td className="py-2 text-right text-zinc-500">
                        {new Date(t.created_at).toLocaleTimeString()}
                      </td>
                    </tr>
                  ))}
                  {tasks.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-zinc-500">
                        No recent tasks recorded.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>

        {/* Right: Task Dispatch Form */}
        <div className="space-y-4">
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center gap-2 mb-4 border-b border-zinc-800/80 pb-3">
              <Zap className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                Dispatch Agent Task
              </h2>
            </div>

            <form onSubmit={handleSubmitTask} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  TASK TYPE
                </label>
                <select
                  value={taskType}
                  onChange={(e) => setTaskType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-zinc-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="recon_analysis">Reconnaissance Analysis</option>
                  <option value="tactical_route_review">Tactical Route Review</option>
                  <option value="red_team_stress_test">Red Team Stress Test</option>
                  <option value="risk_tensor_lookahead">Risk Tensor Lookahead</option>
                  <option value="supply_burn_projection">Supply Burn Projection</option>
                  <option value="knowledge_synthesis">Cross-Source Knowledge Synthesis</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  TARGET AGENT (OPTIONAL)
                </label>
                <select
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-zinc-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="">Auto-Route (Swarm Coordinator)</option>
                  {agents.map((ag) => (
                    <option key={ag.id} value={ag.id}>
                      {ag.name} ({ag.role})
                    </option>
                  ))}
                </select>
              </div>

              <div className="p-3 bg-zinc-950/70 border border-zinc-800/80 rounded text-xs space-y-1 font-mono text-zinc-400">
                <div className="flex justify-between">
                  <span>DISPATCH GATE:</span>
                  <span className="text-emerald-400">OPEN</span>
                </div>
                <div className="flex justify-between">
                  <span>LATENCY BUDGET:</span>
                  <span className="text-zinc-300">&lt; 100ms</span>
                </div>
              </div>

              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-zinc-800 text-zinc-950 font-semibold text-xs tracking-wider uppercase rounded transition-colors flex items-center justify-center gap-2"
              >
                <Send className="w-3.5 h-3.5" />
                {submitting ? "Dispatching..." : "Submit Task to Swarm"}
              </button>
            </form>
          </Panel>
        </div>
      </div>
    </div>
  );
}
