import { useEffect, useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  ExternalLink,
  HelpCircle,
  Loader2,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
  Check,
} from "lucide-react";
import { AiBadge, EmptyState, Mono, SeverityTag } from "@/components/doip/primitives";
import { formatSimClock, canOperate } from "@/lib/doip";
import { useSim } from "@/sim/store";
import { contextStore, useOperationalContext } from "@/sim/contextStore";
import { type WorkspaceId } from "@/lib/workspaces";
import { cn } from "@/lib/utils";
import {
  queryAi,
  type AICitation,
  type AIQueryResponse,
  type AIRecommendation,
} from "@/services/ai";
import type { SimEvent, WorldState } from "@/sim/types";
import { toast } from "sonner";

type Tab = "SITREPS" | "ASK" | "WHAT-IF";

interface Answer {
  id: number;
  q: string;
  a: string;
  facts?: string[] | undefined;
  projections?: string[] | undefined;
  recommendations?: AIRecommendation[] | undefined;
  citations?: AICitation[] | undefined;
  cites?: SimEvent[] | undefined;
  grounded?: boolean | undefined;
  warning?: string | null | undefined;
  mode?: string | undefined;
  latencyMs?: number | undefined;
}

const QUICK_QUERIES = [
  "What is the doctrine for minimum fuel reserves?",
  "What are the comms loss contingency steps?",
  "Assess open incidents and threat severity.",
  "What is the policy on synthetic-only data?",
];

const WORKSPACE_QUICK_QUERIES: Record<WorkspaceId, string[]> = {
  command: [
    "Assess open incidents and threat severity.",
    "Summarize unacknowledged alerts.",
    "What is the policy on synthetic-only data?",
  ],
  simulation: [
    "What is the doctrine for Point-of-No-Return?",
    "Evaluate current mission path feasibility.",
    "Assess risk divergence in branch simulation.",
  ],
  intelligence: [
    "What is the doctrine for minimum fuel reserves?",
    "What are the comms loss contingency steps?",
    "Identify single points of failure in knowledge graph.",
  ],
  readiness: [
    "What is the doctrine for minimum fuel reserves?",
    "Forecast depot time-to-empty burndown.",
    "Recommend personnel rotation for elevated fatigue.",
  ],
  collaboration: [
    "Draft strategic directive for theater dispersion.",
    "Check sector task backlog in War Room.",
    "Review active workflow approval gates.",
  ],
  analytics: [
    "Check P99 latency percentiles.",
    "Summarize mission success rate trends.",
    "Review telemetry event ingestion rate.",
  ],
  governance: [
    "Audit recent Human-in-the-Loop gate transitions.",
    "Verify simulation determinism seed purity.",
    "Check model routing allocation.",
  ],
};

/** Local fallback heuristic when both backend RAG and AI pipeline are unreachable. */
function localAnswerHeuristic(
  q: string,
  world: WorldState,
  events: SimEvent[],
): { a: string; cites: SimEvent[] } {
  const t = q.toLowerCase();
  const units = Object.values(world.units);
  const cite = (type: string, n = 3) =>
    events
      .filter((e) => e.type === type)
      .slice(-n)
      .reverse();

  if (/fuel|resupply|logisti|supply/.test(t)) {
    const low = units
      .filter((u) => u.fuel < 40)
      .sort((a, b) => a.fuel - b.fuel)
      .slice(0, 4);
    return {
      a: low.length
        ? `${low.length} unit(s) under 40% fuel: ${low.map((u) => `${u.callsign} (${u.fuel.toFixed(0)}%)`).join(", ")}. Recommend depot tasking before the next phase per SOP-02.`
        : "Fuel states are nominal — all active units exceed the 40% doctrine reserve threshold (SOP-02).",
      cites: cite("resource_level"),
    };
  }
  if (/comms|stale|radio|contact/.test(t)) {
    const stale = units.filter((u) => u.status === "stale");
    return {
      a: stale.length
        ? `${stale.length} unit(s) past the reporting threshold: ${stale.map((u) => u.callsign).join(", ")}. Primary comms heartbeat required per REF-01.`
        : "All units are reporting within the 180s threshold (REF-01).",
      cites: cite("comms_loss"),
    };
  }
  if (/incident|threat|attack|contact/.test(t)) {
    const open = Object.values(world.incidents).filter((i) => i.open);
    const worst = open.some((i) => i.severity === "critical")
      ? "CRITICAL"
      : open.some((i) => i.severity === "high")
        ? "HIGH"
        : "MEDIUM/LOW";
    return {
      a: open.length
        ? `${open.length} incident(s) open; peak threat severity ${worst}. Adjudicate per SOP-04.`
        : "No active incidents currently logged.",
      cites: cite("incident_open"),
    };
  }
  return {
    a: `${units.length} units deployed, ${Object.values(world.incidents).filter((i) => i.open).length} incident(s) open at ${formatSimClock(world.tick)}. Consult Tactical Doctrine Library.`,
    cites: events.slice(-3).reverse(),
  };
}

function CitationBadges({ citations }: { citations?: AICitation[] | undefined }) {
  if (!citations || !citations.length) return null;
  return (
    <div className="mt-2 space-y-1">
      <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
        Verified Source Citations:
      </div>
      <div className="flex flex-wrap gap-1">
        {citations.map((c, idx) => (
          <span
            key={`${c.source_id}-${idx}`}
            className={cn(
              "inline-flex items-center gap-1 border px-1.5 py-0.5 font-mono text-[9px]",
              c.verified
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
                : "border-amber-500/40 bg-amber-500/10 text-amber-400",
            )}
            title={c.title || c.citation}
          >
            {c.verified ? (
              <CheckCircle2 className="size-2.5 text-emerald-400" />
            ) : (
              <AlertTriangle className="size-2.5 text-amber-400" />
            )}
            <span>{c.citation}</span>
            {c.type === "doctrine" && <span className="opacity-60">DOC</span>}
          </span>
        ))}
      </div>
    </div>
  );
}

function LegacyCiteChips({ cites }: { cites?: SimEvent[] | undefined }) {
  if (!cites || !cites.length) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1">
      {cites.map((c) => (
        <span
          key={c.id}
          className="flex items-center gap-1 border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
          title={`${c.type} · ${c.entityId}`}
        >
          <SeverityTag severity={c.severity} showLabel={false} />
          e:{c.id} · T+{c.tick}
        </span>
      ))}
    </div>
  );
}

export function AiDrawer({ onClose }: { onClose: () => void }) {
  const world = useSim((s) => s.world);
  const events = useSim((s) => s.events);
  const role = useSim((s) => s.role);
  const userName = useSim((s) => s.userName);

  const activeWs = useOperationalContext((s) => s.activeWorkspace);
  const prefill = useOperationalContext((s) => s.aiPrefillPrompt);
  const selectedEntityId = useOperationalContext((s) => s.selectedEntityId);
  const selectedIncidentId = useOperationalContext((s) => s.selectedIncidentId);

  const [tab, setTab] = useState<Tab>("SITREPS");
  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState<Answer[]>([]);
  const [loading, setLoading] = useState(false);
  const [approvedRecs, setApprovedRecs] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (prefill) {
      setQ(prefill);
      setTab("ASK");
      contextStore.setAiPrefillPrompt(null);
    }
  }, [prefill]);

  const sections = useMemo(() => {
    const units = Object.values(world.units);
    const open = Object.values(world.incidents).filter((i) => i.open);
    const crit = open.filter((i) => i.severity === "critical" || i.severity === "high");
    const stale = units.filter((u) => u.status === "stale");
    const lowFuel = units.filter((u) => u.fuel < 30);
    const cite = (type: string, n = 2) =>
      events
        .filter((e) => e.type === type)
        .slice(-n)
        .reverse();
    return [
      {
        heading: "Posture",
        body: `${units.length} units committed · ${open.length} incident(s) open${
          crit.length ? ` · ${crit.length} high/critical` : ""
        } · ${Object.values(world.alerts).filter((a) => !a.acked).length} unacked alert(s).`,
        cites: cite("incident_open"),
      },
      {
        heading: "Comms",
        body: stale.length
          ? `${stale.length} stale: ${stale.map((u) => u.callsign).join(", ")}.`
          : "All units reporting inside threshold.",
        cites: cite("comms_loss"),
      },
      {
        heading: "Sustainment",
        body: lowFuel.length
          ? `${lowFuel.length} unit(s) below 30% fuel: ${lowFuel.map((u) => u.callsign).join(", ")}.`
          : "Fuel and battery states nominal.",
        cites: cite("resource_level"),
      },
    ];
  }, [world, events]);

  const handleAsk = async (textToAsk?: string) => {
    const query = (textToAsk ?? q).trim();
    if (!query || loading) return;
    setQ("");
    setLoading(true);

    try {
      const response: AIQueryResponse = await queryAi({
        query,
        run_id: (world as any).runId ?? null,
        tick: world.tick,
      });

      setMsgs((prev) => [
        ...prev,
        {
          id: prev.length + 1,
          q: query,
          a: response.answer,
          facts: response.facts,
          projections: response.projections,
          recommendations: response.recommendations,
          citations: response.citations,
          grounded: response.grounding.grounded,
          warning: response.grounding.warning,
          mode: response.mode,
          latencyMs: Math.round(response.latency_ms),
        },
      ]);
    } catch {
      // Complete offline fail-safe
      const { a, cites } = localAnswerHeuristic(query, world, events);
      setMsgs((prev) => [
        ...prev,
        {
          id: prev.length + 1,
          q: query,
          a,
          cites,
          grounded: true,
          mode: "offline_client_fallback",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleApproveDirective = (actionKey: string, rec: AIRecommendation) => {
    if (!canOperate(role)) {
      toast.error("Read-only role", {
        description: "Authorizing tactical directives requires Operator or Planner role.",
      });
      return;
    }

    setApprovedRecs((prev) => ({ ...prev, [actionKey]: true }));
    contextStore.decrementPendingApproval();
    toast.success("Directive Formally Authorized (HITL Approved)", {
      description: `Action ${rec.action} signed off by ${userName || role}. Recorded to audit log.`,
    });
  };

  const activeInquiries = WORKSPACE_QUICK_QUERIES[activeWs] || QUICK_QUERIES;

  return (
    <aside
      className="flex w-96 shrink-0 flex-col border-l border-border bg-surface text-foreground shadow-2xl z-40"
      aria-label="Tactical AI drawer"
    >
      {/* Header */}
      <header className="flex h-11 shrink-0 items-center justify-between border-b border-border px-3 bg-raised/30">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-ai animate-pulse" />
          <span className="font-mono text-xs font-bold tracking-wider text-ai">TACTICAL AI</span>
          <span className="border border-ai/40 bg-ai/10 px-1 py-0.5 font-mono text-[9px] text-ai">
            v3.2
          </span>
        </div>
        <button
          onClick={onClose}
          className="size-6 text-muted-foreground hover:text-foreground flex items-center justify-center border border-transparent hover:border-border"
          aria-label="Close drawer"
        >
          <X className="size-4" />
        </button>
      </header>

      {/* Active Operational Context Banner */}
      <div className="border-b border-border/70 bg-background/60 px-3 py-1 font-mono text-[9px] text-muted-foreground flex items-center justify-between">
        <span className="uppercase tracking-wider">
          WORKSPACE: <strong className="text-primary">{activeWs.toUpperCase()}</strong>
        </span>
        {(selectedEntityId || selectedIncidentId) && (
          <span className="truncate max-w-[150px] text-foreground">
            {selectedIncidentId || selectedEntityId}
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex shrink-0 border-b border-border">
        {(["SITREPS", "ASK", "WHAT-IF"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "flex-1 py-2 text-center font-mono text-xs uppercase tracking-wider transition-colors",
              tab === t
                ? "border-b-2 border-ai bg-raised font-bold text-ai"
                : "text-muted-foreground hover:bg-raised hover:text-foreground",
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-3 text-xs">
        {tab === "SITREPS" ? (
          <div className="space-y-3">
            {sections.map((s) => (
              <div key={s.heading} className="border border-border bg-background p-2.5 space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-primary font-bold">
                    {s.heading}
                  </span>
                  <span className="font-mono text-[9px] text-muted-foreground">T+{world.tick}</span>
                </div>
                <p className="text-[11px] leading-relaxed text-foreground/90">{s.body}</p>
                <LegacyCiteChips cites={s.cites} />
              </div>
            ))}
            <Link
              to="/sitrep"
              className="mt-2 block border border-border bg-raised p-2 text-center font-mono text-[10px] uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
            >
              Full situation report →
            </Link>
          </div>
        ) : tab === "ASK" ? (
          <div className="space-y-3">
            {/* Quick Inquiries */}
            {msgs.length === 0 && (
              <div className="space-y-1.5 border border-dashed border-border p-2">
                <div className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                  Quick Inquiries
                </div>
                <div className="space-y-1">
                  {activeInquiries.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => handleAsk(prompt)}
                      className="w-full text-left border border-border/60 bg-raised/40 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:border-ai/40 transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Q&A Stream */}
            {msgs.map((m) => (
              <div key={m.id} className="border border-border bg-background p-2.5 space-y-2">
                <div className="flex items-start gap-1.5 text-muted-foreground border-b border-border pb-1">
                  <span className="font-mono text-[10px] text-ai font-bold">Q:</span>
                  <span className="text-[11px] text-foreground font-medium">{m.q}</span>
                </div>

                <div className="space-y-2">
                  <p className="text-[11px] leading-relaxed text-foreground/90">{m.a}</p>

                  {/* Structured Facts */}
                  {m.facts && m.facts.length > 0 && (
                    <div className="space-y-1 border-l-2 border-emerald-500/60 pl-2">
                      <div className="font-mono text-[9px] font-bold uppercase tracking-wider text-emerald-400">
                        Verified Facts
                      </div>
                      <ul className="space-y-0.5 text-[11px] text-foreground/80 list-disc list-inside">
                        {m.facts.map((f, i) => (
                          <li key={i}>{f}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Structured Projections */}
                  {m.projections && m.projections.length > 0 && (
                    <div className="space-y-1 border-l-2 border-cyan-500/60 pl-2">
                      <div className="font-mono text-[9px] font-bold uppercase tracking-wider text-cyan-400">
                        AI Projections
                      </div>
                      <ul className="space-y-0.5 text-[11px] text-foreground/80 list-disc list-inside">
                        {m.projections.map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Structured Recommendations with Human-in-the-Loop Gate */}
                  {m.recommendations && m.recommendations.length > 0 && (
                    <div className="space-y-1.5 border-t border-ai/20 pt-1.5">
                      <div className="flex items-center justify-between font-mono text-[9px] font-bold uppercase tracking-wider text-amber-400">
                        <span>Tactical Recommendations</span>
                        <span className="text-[8px] text-amber-300/80 font-normal">
                          Requires Operator Approval
                        </span>
                      </div>
                      {m.recommendations.map((rec, i) => {
                        const recKey = `${m.id}-${i}`;
                        const isApproved = approvedRecs[recKey];
                        return (
                          <div
                            key={i}
                            className="border border-amber-500/30 bg-amber-500/10 p-2 space-y-1.5"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-[10px] font-bold text-amber-300">
                                {rec.action}
                              </span>
                              <span className="border border-amber-500/40 px-1 font-mono text-[8px] text-amber-400">
                                {rec.priority}
                              </span>
                            </div>
                            <p className="text-[11px] text-muted-foreground">{rec.rationale}</p>
                            <div className="flex items-center justify-between pt-1">
                              <div className="flex items-center gap-1 font-mono text-[8px] text-amber-200/70">
                                <ShieldAlert className="size-2.5" />
                                <span>DSL Safety Boundary: Human Confirmation Required</span>
                              </div>
                              <button
                                onClick={() => handleApproveDirective(recKey, rec)}
                                disabled={isApproved}
                                className={cn(
                                  "border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider transition-colors",
                                  isApproved
                                    ? "border-emerald-500/60 bg-emerald-950/40 text-emerald-300 cursor-default"
                                    : "border-amber-500/60 bg-amber-500/20 text-amber-300 hover:bg-amber-500/30",
                                )}
                              >
                                {isApproved ? "Approved ✓" : "Approve Directive"}
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Citations */}
                  <CitationBadges citations={m.citations} />
                  <LegacyCiteChips cites={m.cites} />
                </div>
              </div>
            ))}

            {/* Loading Indicator */}
            {loading && (
              <div className="flex items-center gap-2 border border-ai/30 bg-ai/10 p-2 text-xs text-ai animate-pulse">
                <Loader2 className="size-3.5 animate-spin" />
                <span className="font-mono text-[10px]">Consulting Doctrine & Sim Context...</span>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-2.5">
            <p className="text-[12px] leading-relaxed text-muted-foreground">
              Branch the current state, review AI-drafted scenario actions, approve, and watch
              the branch play out. Branches are sandboxed — the live run is untouched.
            </p>
            <Link
              to="/whatif"
              className="block border border-ai/40 bg-ai/5 px-2 py-1.5 text-center font-mono text-[10px] uppercase tracking-widest text-ai hover:bg-raised transition-colors"
            >
              Open What-If Theater →
            </Link>
          </div>
        )}
      </div>

      {/* Input Bar */}
      {tab === "ASK" && (
        <div className="flex shrink-0 gap-1.5 border-t border-border p-2 bg-raised/10">
          <input
            value={q}
            disabled={loading}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAsk()}
            placeholder="Query tactical doctrine or simulation..."
            className="min-w-0 flex-1 border border-border bg-background px-2.5 py-1.5 text-xs outline-none focus:border-ai/60 font-mono disabled:opacity-50"
          />
          <button
            onClick={() => handleAsk()}
            disabled={loading || !q.trim()}
            className="border border-ai/50 bg-ai/15 px-2.5 text-ai hover:bg-ai/25 disabled:opacity-40 transition-colors"
            aria-label="Ask"
          >
            {loading ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
          </button>
        </div>
      )}

      {/* Safety Footer Banner */}
      <footer className="shrink-0 border-t border-border px-2.5 py-1 font-mono text-[8.5px] leading-tight text-muted-foreground/80 bg-background/50">
        AI ASSISTANT · SYNTHETIC TRAINING DATA · ZERO DIRECT STATE MUTATION
      </footer>
    </aside>
  );
}
