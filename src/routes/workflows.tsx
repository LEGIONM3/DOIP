import { useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { Panel, Mono, Stat } from "@/components/doip/primitives";
import { cn } from "@/lib/utils";
import { contextStore } from "@/sim/contextStore";
import {
  listWorkflows,
  createWorkflow,
  approveWorkflow,
  rejectWorkflow,
  advanceWorkflow,
  type WorkflowInstance,
} from "@/services/workflows";
import {
  CheckSquare,
  ShieldAlert,
  UserCheck,
  Play,
  XCircle,
  Plus,
  RefreshCw,
  Clock,
  Layers,
  CheckCircle,
  FileText,
} from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/workflows")({
  head: () => ({
    meta: [
      { title: "Operational Workflow Engine — DOIP" },
      {
        name: "description",
        content: "State machine governing mission dispatch, after-action reviews, and mandatory human-in-the-loop gates.",
      },
    ],
  }),
  component: WorkflowsDashboard,
});

function WorkflowsDashboard() {
  const [workflows, setWorkflows] = useState<WorkflowInstance[]>([]);
  const [loading, setLoading] = useState(false);
  const [operatorId, setOperatorId] = useState("OPERATOR-CMD-01");

  // Create Workflow Form
  const [newTitle, setNewTitle] = useState("Operation Granite Shield Authorization");
  const [newType, setNewType] = useState("strike_dispatch");
  const [creating, setCreating] = useState(false);

  const fetchWorkflows = async () => {
    setLoading(true);
    try {
      const data = await listWorkflows();
      setWorkflows(data);
    } catch (err: any) {
      toast.error(`Error loading workflows: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await createWorkflow(newType, newTitle, undefined, true);
      toast.success("Operational workflow staged with mandatory human gate.");
      setNewTitle("");
      fetchWorkflows();
    } catch (err: any) {
      toast.error(`Failed to stage workflow: ${err.message}`);
    } finally {
      setCreating(false);
    }
  };

  const handleApprove = async (wfId: string) => {
    try {
      await approveWorkflow(wfId, operatorId);
      contextStore.decrementPendingApproval();
      toast.success(`Workflow ${wfId} approved by ${operatorId}.`);
      fetchWorkflows();
    } catch (err: any) {
      toast.error(`Approval failed: ${err.message}`);
    }
  };

  const handleReject = async (wfId: string) => {
    try {
      await rejectWorkflow(wfId, operatorId, "Risk threshold exceeded.");
      toast.warning(`Workflow ${wfId} rejected by operator.`);
      fetchWorkflows();
    } catch (err: any) {
      toast.error(`Rejection failed: ${err.message}`);
    }
  };

  const handleAdvance = async (wfId: string, nextStep: string) => {
    try {
      await advanceWorkflow(wfId, nextStep);
      toast.success(`Advanced to step: ${nextStep}`);
      fetchWorkflows();
    } catch (err: any) {
      toast.error(`Advance failed (Safety Invariant): ${err.message}`);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "approved":
      case "completed":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "staged":
      case "running":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "rejected":
        return "bg-red-500/10 text-red-400 border-red-500/30";
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
            <CheckSquare className="w-6 h-6 text-amber-400" />
            <h1 className="text-xl font-bold tracking-wider uppercase text-zinc-100">
              Operational Workflow & Authorization Engine
            </h1>
          </div>
          <p className="text-xs text-zinc-400 font-mono mt-1">
            Phase 5J Mandatory Human-in-the-Loop Authorization & Mission Dispatch State Machine
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 bg-zinc-950 border border-zinc-800 rounded">
            <span className="text-[10px] font-mono text-zinc-400">OPERATOR ID:</span>
            <input
              type="text"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              className="bg-transparent text-xs font-mono text-cyan-400 focus:outline-none w-32"
            />
          </div>
          <button
            onClick={fetchWorkflows}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 hover:border-zinc-500 text-xs font-mono rounded text-zinc-200 transition-colors"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
            Sync
          </button>
        </div>
      </div>

      {/* Invariant Banner */}
      <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded flex items-center justify-between gap-3 text-xs font-mono text-amber-300">
        <div className="flex items-center gap-3">
          <ShieldAlert className="w-4 h-4 flex-shrink-0" />
          <span>
            MANDATORY HUMAN-IN-THE-LOOP GATE ENFORCED: Autonomous agents cannot transition workflows into execution
            without cryptographically logged human sign-off.
          </span>
        </div>
        <Link
          to="/admin"
          className="flex-shrink-0 inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono text-cyan-400 bg-cyan-950/40 border border-cyan-800/60 rounded hover:bg-cyan-900/50 hover:text-cyan-300 transition-colors"
        >
          <FileText className="w-3.5 h-3.5" />
          Audit Trail
        </Link>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Active Workflows List */}
        <div className="lg:col-span-2 space-y-4">
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center justify-between mb-4 border-b border-zinc-800/80 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                  Staged & Executed Workflows
                </h2>
              </div>
              <span className="text-xs font-mono text-zinc-500">{workflows.length} Total</span>
            </div>

            <div className="space-y-4">
              {workflows.map((wf) => (
                <div
                  key={wf.id}
                  className="p-4 bg-zinc-950/70 border border-zinc-800/80 rounded space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-zinc-100">{wf.title}</h3>
                      <Mono className="text-[10px] text-zinc-500">{wf.id} • {wf.workflow_type.toUpperCase()}</Mono>
                    </div>
                    <span
                      className={cn(
                        "px-2 py-0.5 text-[10px] font-mono rounded border uppercase",
                        getStatusBadge(wf.status)
                      )}
                    >
                      {wf.status}
                    </span>
                  </div>

                  {/* Steps Progress */}
                  <div className="grid grid-cols-4 gap-2 pt-2 border-t border-zinc-900 text-center text-[10px] font-mono">
                    {wf.steps?.map((step, idx) => (
                      <div
                        key={step.step_id || idx}
                        className={cn(
                          "p-1.5 rounded border",
                          step.status === "approved" || step.status === "completed"
                            ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                            : step.status === "in_progress"
                            ? "bg-cyan-500/10 border-cyan-500/30 text-cyan-300"
                            : step.status === "rejected"
                            ? "bg-red-500/10 border-red-500/30 text-red-300"
                            : "bg-zinc-900/60 border-zinc-800 text-zinc-500"
                        )}
                      >
                        <div className="font-semibold">{step.name}</div>
                        <div className="text-[8px] uppercase">{step.status}</div>
                      </div>
                    ))}
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center justify-between pt-2 border-t border-zinc-900">
                    <div className="text-[10px] font-mono text-zinc-400">
                      CURRENT STEP: <span className="text-cyan-400">{wf.current_step}</span>
                      {wf.approved_by && (
                        <span className="ml-3 text-emerald-400">APPROVED BY: {wf.approved_by}</span>
                      )}
                    </div>

                    <div className="flex gap-2">
                      {wf.status === "staged" && (
                        <>
                          <button
                            onClick={() => handleApprove(wf.id)}
                            className="flex items-center gap-1.5 px-3 py-1 bg-emerald-600/80 hover:bg-emerald-600 text-zinc-950 font-semibold text-xs rounded transition-colors"
                          >
                            <UserCheck className="w-3.5 h-3.5" />
                            Approve Gate
                          </button>
                          <button
                            onClick={() => handleReject(wf.id)}
                            className="flex items-center gap-1.5 px-3 py-1 bg-red-950/60 border border-red-800 hover:border-red-600 text-red-300 text-xs rounded transition-colors"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            Reject
                          </button>
                        </>
                      )}

                      {wf.status === "approved" && (
                        <button
                          onClick={() => handleAdvance(wf.id, "completed")}
                          className="flex items-center gap-1.5 px-3 py-1 bg-cyan-600/80 hover:bg-cyan-600 text-zinc-950 font-semibold text-xs rounded transition-colors"
                        >
                          <Play className="w-3.5 h-3.5" />
                          Complete Execution
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              {workflows.length === 0 && (
                <div className="text-center py-8 text-zinc-500 text-xs font-mono">
                  No active workflows staged. Use the form on the right to stage a workflow.
                </div>
              )}
            </div>
          </Panel>
        </div>

        {/* Right: Stage New Workflow */}
        <div className="space-y-4">
          <Panel className="p-4 bg-zinc-900/40 border-zinc-800">
            <div className="flex items-center gap-2 mb-3 border-b border-zinc-800/80 pb-2">
              <Plus className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold tracking-wide uppercase text-zinc-200">
                Stage New Workflow
              </h2>
            </div>

            <form onSubmit={handleCreate} className="space-y-3">
              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  WORKFLOW TYPE
                </label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-zinc-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="strike_dispatch">Strike Dispatch Workflow</option>
                  <option value="convoy_transit">Convoy Transit & Route Clear</option>
                  <option value="threat_aar">Threat After-Action Review</option>
                  <option value="countermeasure_staging">Kinetic Countermeasure Staging</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  WORKFLOW TITLE
                </label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Operation Iron Spear Clearance"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded px-3 py-2 text-xs font-mono text-zinc-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="p-3 bg-zinc-950/70 border border-zinc-800/80 rounded text-xs space-y-1 font-mono text-zinc-400">
                <div className="flex justify-between">
                  <span>HUMAN CONFIRMATION:</span>
                  <span className="text-emerald-400">REQUIRED</span>
                </div>
                <div className="flex justify-between">
                  <span>SAFETY LEVEL:</span>
                  <span className="text-cyan-400">CLASS 4 GATE</span>
                </div>
              </div>

              <button
                type="submit"
                disabled={creating}
                className="w-full py-2 bg-amber-600 hover:bg-amber-500 text-zinc-950 font-semibold text-xs tracking-wider uppercase rounded transition-colors"
              >
                {creating ? "Staging..." : "Stage Operational Workflow"}
              </button>
            </form>
          </Panel>
        </div>
      </div>
    </div>
  );
}
