import { useEffect, useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { EmptyState, Panel, Stat, Mono } from "@/components/doip/primitives";
import { Sparkline } from "@/components/doip/Sparkline";
import { SCENARIOS } from "@/sim/scenarios";
import { simStore, useSim } from "@/sim/store";
import { canOperate, computeEventFingerprint } from "@/lib/doip";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { contextStore } from "@/sim/contextStore";
import {
  Play,
  Pause,
  Square,
  RotateCcw,
  Copy,
  History,
  Download,
  BookmarkPlus,
  Zap,
  Sparkles,
  FileText,
  Navigation,
} from "lucide-react";

export const Route = createFileRoute("/run")({
  head: () => ({
    meta: [
      { title: "Run Control — DOIP" },
      {
        name: "description",
        content:
          "Start, pause and replay deterministic training scenarios with seed control and speed 1-20x.",
      },
      { property: "og:title", content: "Run Control — DOIP" },
      {
        property: "og:description",
        content:
          "Deterministic scenario control: seed, speed, run history and clone-with-same-seed.",
      },
    ],
  }),
  component: RunControlScreen,
});

function downloadJson(name: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function RunControlScreen() {
  const status = useSim((s) => s.status);
  const speed = useSim((s) => s.speed);
  const tick = useSim((s) => s.world.tick);
  const seed = useSim((s) => s.seed);
  const scenarioId = useSim((s) => s.scenarioId);
  const rate = useSim((s) => s.eventRate);
  const events = useSim((s) => s.events);
  const eventCount = events.length;
  const snapshot = useSim((s) => s.snapshot);
  const role = useSim((s) => s.role);
  const runs = useSim((s) => s.runs);
  const worldMode = useSim((s) => s.worldMode);
  const activeBranchId = useSim((s) => s.activeBranchId);
  const envContext = useSim((s) => s.environmentalContext);

  const fingerprint = useMemo(() => computeEventFingerprint(events), [events]);

  const [seedInput, setSeedInput] = useState(String(seed));
  const [picked, setPicked] = useState(scenarioId);
  const [categoryFilter, setCategoryFilter] = useState<
    "all" | "live-baseline" | "artificial-impact" | "legacy"
  >("all");
  const allowed = canOperate(role);

  useEffect(() => {
    setPicked(scenarioId);
  }, [scenarioId]);

  const filteredScenarios = useMemo(() => {
    if (categoryFilter === "all") return SCENARIOS;
    return SCENARIOS.filter((s) => s.category === categoryFilter);
  }, [categoryFilter]);

  const guard = (fn: () => void, label: string) => () => {
    if (!allowed) {
      toast.error("Read-only role", { description: `${label} requires operator access or above.` });
      return;
    }
    fn();
    toast.success(label);
  };

  return (
    <div className="grid gap-2 p-2 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-2">
        {/* Cross-Feature Workflow Handoffs */}
        <div className="flex flex-wrap items-center justify-between gap-2 border border-border bg-raised/40 px-3 py-1.5 font-mono text-xs">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            WORKFLOW HANDOFFS:
          </span>
          <div className="flex flex-wrap items-center gap-1.5">
            <Link
              to="/replay"
              search={{ run: "LIVE" }}
              className="flex items-center gap-1 border border-primary/40 bg-primary/10 px-2 py-0.5 text-[10px] text-primary hover:bg-primary/20"
              title="Open current live/recorded state in Replay"
            >
              <History className="size-3" /> Total Replay (S6)
            </Link>
            <Link
              to="/whatif"
              search={{ scenario: picked }}
              className="flex items-center gap-1 border border-ai/40 bg-ai/10 px-2 py-0.5 text-[10px] text-ai hover:bg-ai/20"
              title="Branch What-If scenario from current state"
            >
              <Sparkles className="size-3" /> Branch What-If (S8)
            </Link>
            <Link
              to="/sitrep"
              className="flex items-center gap-1 border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
              title="Generate AI situation report"
            >
              <FileText className="size-3" /> AI SITREP (S7)
            </Link>
            <Link
              to="/planner"
              className="flex items-center gap-1 border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
              title="Plan new waypoint routes"
            >
              <Navigation className="size-3" /> Mission Planner (S5)
            </Link>
          </div>
        </div>

        {/* World Model Authority & Management Strip */}
        <div className="border border-border bg-raised/30 p-2.5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/80 pb-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                WORLD MODEL:
              </span>
              <div className="flex border border-border bg-background">
                <button
                  onClick={guard(() => {
                    simStore.resetToBaseline();
                    setPicked("IN-BASE-LIVE");
                  }, "Switched to Pan-India Real World Model (Live Baseline)")}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 font-mono text-xs uppercase tracking-wide transition-colors",
                    worldMode === "baseline"
                      ? "bg-emerald-500/20 text-emerald-300 font-bold border-r border-emerald-500/40"
                      : "text-muted-foreground hover:text-foreground border-r border-border",
                  )}
                >
                  <span
                    className={cn(
                      "size-2 rounded-full",
                      worldMode === "baseline" ? "bg-emerald-400 animate-pulse" : "bg-zinc-600",
                    )}
                  />
                  Real World Baseline
                </button>
                <button
                  onClick={guard(() => {
                    simStore.switchWorldMode("simulation");
                    setPicked("IN-SC-CASCADE");
                  }, "Switched to Artificial Impact Simulation World")}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 font-mono text-xs uppercase tracking-wide transition-colors",
                    worldMode === "simulation"
                      ? "bg-amber-500/20 text-amber-300 font-bold"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "size-2 rounded-full",
                      worldMode === "simulation" ? "bg-amber-400 animate-pulse" : "bg-zinc-600",
                    )}
                  />
                  Simulation World (Impact Branches)
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2 font-mono text-[11px]">
              {worldMode === "baseline" ? (
                <>
                  <span className="border border-emerald-700/60 bg-emerald-950/60 px-2 py-0.5 text-emerald-300 font-medium">
                    {envContext?.stationsCount ?? 11} MET STATIONS LIVE
                  </span>
                  <span className="border border-emerald-800/80 bg-emerald-950/40 px-1.5 py-0.5 text-[10px] text-emerald-400">
                    PROVENANCE: {envContext?.globalProvenance ?? "REAL_FORECAST"}
                  </span>
                  <button
                    onClick={guard(() => {
                      simStore.forkSimulation("IN-SC-CASCADE", Number(seedInput) || 20261014);
                      setPicked("IN-SC-CASCADE");
                    }, "Forked Simulation World: Pan-India Multi-Sector Cascade")}
                    className="flex items-center gap-1 border border-amber-500/60 bg-amber-500/20 px-2 py-0.5 text-amber-200 hover:bg-amber-500/30 font-semibold"
                  >
                    <Zap className="size-3" /> FORK SIMULATION WORLD
                  </button>
                </>
              ) : (
                <>
                  <span className="border border-amber-700/60 bg-amber-950/60 px-2 py-0.5 text-amber-300 font-semibold">
                    BRANCH: {activeBranchId ?? "BRANCH-ISOLATED"}
                  </span>
                  <button
                    onClick={guard(() => {
                      simStore.resetToBaseline();
                      setPicked("IN-BASE-LIVE");
                    }, "Reset to Pan-India Baseline World")}
                    className="flex items-center gap-1 border border-emerald-500/60 bg-emerald-500/20 px-2 py-0.5 text-emerald-200 hover:bg-emerald-500/30 font-semibold"
                  >
                    <RotateCcw className="size-3" /> ↺ RESET TO REAL WORLD BASELINE
                  </button>
                </>
              )}
            </div>
          </div>

          {/* 1-Click Artificial Impact Branch Launchers */}
          <div className="mt-2.5">
            <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
              <span>⚡ 1-Click Artificial Impact Branch Launchers (Subcontinent-Wide Multi-Sector)</span>
              <span className="text-[9px] text-zinc-500">ISOLATED FROM BASELINE WORLD</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-1.5">
              {[
                {
                  id: "IN-SC-CASCADE",
                  name: "Multi-Sector Cascade",
                  sector: "Pan-India",
                  desc: "Cyclone + Blizzard + Heatwave + Logistics",
                  color: "border-rose-500/50 bg-rose-950/20 text-rose-300 hover:bg-rose-950/40",
                },
                {
                  id: "IN-SC-CYCLONE",
                  name: "Bay of Bengal Cyclone",
                  sector: "Eastern Littoral",
                  desc: "Cat 3 coastal flooding & port choke",
                  color: "border-sky-500/50 bg-sky-950/20 text-sky-300 hover:bg-sky-950/40",
                },
                {
                  id: "IN-SC-NORTH-COMMS",
                  name: "Himalayan Blizzard",
                  sector: "Northern Ladakh",
                  desc: "Sub-zero blizzard & RF comms loss",
                  color: "border-blue-500/50 bg-blue-950/20 text-blue-300 hover:bg-blue-950/40",
                },
                {
                  id: "IN-SC-WEST-HEAT",
                  name: "Thar Desert Heatwave",
                  sector: "Western Desert",
                  desc: "48°C extreme heat & fuel boil-off",
                  color: "border-amber-500/50 bg-amber-950/20 text-amber-300 hover:bg-amber-950/40",
                },
                {
                  id: "IN-SC-LOGISTICS",
                  name: "Central Logistics Choke",
                  sector: "Central Nagpur",
                  desc: "Transit hub rail breakdown",
                  color: "border-orange-500/50 bg-orange-950/20 text-orange-300 hover:bg-orange-950/40",
                },
              ].map((b) => (
                <button
                  key={b.id}
                  onClick={guard(() => {
                    simStore.forkSimulation(b.id, Number(seedInput) || 20261014);
                    setPicked(b.id);
                  }, `Forked Artificial Branch: ${b.name}`)}
                  className={cn(
                    "flex flex-col text-left p-1.5 border font-mono transition-all",
                    b.color,
                    scenarioId === b.id && worldMode === "simulation"
                      ? "ring-1 ring-white shadow-md"
                      : "opacity-90 hover:opacity-100",
                  )}
                >
                  <div className="flex items-center justify-between text-[10px] font-bold">
                    <span>{b.name}</span>
                    <span className="text-[9px] opacity-70">[{b.sector}]</span>
                  </div>
                  <p className="text-[9px] text-zinc-400 mt-0.5 line-clamp-1">{b.desc}</p>
                  <span className="text-[8px] uppercase tracking-wider text-primary mt-1 font-semibold">
                    ⚡ Launch Branch
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <Panel
          title="Scenario library"
          actions={
            <div className="flex items-center gap-1 font-mono text-[10px]">
              {(
                [
                  { id: "all", label: "ALL" },
                  { id: "live-baseline", label: "PAN-INDIA LIVE" },
                  { id: "artificial-impact", label: "ARTIFICIAL IMPACT" },
                  { id: "legacy", label: "LEGACY" },
                ] as const
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setCategoryFilter(tab.id)}
                  className={cn(
                    "px-1.5 py-0.5 uppercase tracking-wide border transition-colors",
                    categoryFilter === tab.id
                      ? "border-primary bg-primary/20 text-primary font-bold"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          }
        >
          <ul className="grid gap-2 sm:grid-cols-2">
            {filteredScenarios.map((sc) => (
              <li key={sc.id}>
                <button
                  onClick={() => setPicked(sc.id)}
                  className={cn(
                    "h-full w-full border p-2 text-left transition-colors",
                    picked === sc.id
                      ? "border-primary/60 bg-raised"
                      : "border-border hover:bg-raised doip-btn-primary",
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-primary">{sc.id}</span>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono text-[9px] px-1 py-0.2 bg-muted/60 text-muted-foreground uppercase">
                        {sc.sector || "PAN-INDIA"}
                      </span>
                      <span
                        className={cn(
                          "font-mono text-[10px] uppercase",
                          sc.validation === "valid" ? "text-success" : "text-sev-medium",
                        )}
                      >
                        {sc.validation}
                      </span>
                    </div>
                  </div>
                  <div className="mt-1 text-sm font-medium">{sc.name}</div>
                  <p className="mt-1 text-xs text-muted-foreground">{sc.description}</p>
                  <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-muted-foreground">
                    <span>
                      patrols {sc.patrolCount} · uav {sc.uavCount} · convoy {sc.convoyCount}
                    </span>
                    <span className="text-[9px] text-zinc-500 uppercase">{sc.category}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Run controls">
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-1">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                Seed
              </span>
              <input
                value={seedInput}
                onChange={(e) => setSeedInput(e.target.value.replace(/\D/g, ""))}
                className="w-40 border border-border bg-background px-2 py-1 font-mono text-sm outline-none focus:border-primary"
              />
            </label>
            <button
              onClick={guard(
                () => simStore.startRun(Number(seedInput) || 1, picked),
                `Run started · ${picked} · seed ${seedInput}`,
              )}
              className="flex items-center gap-1.5 bg-primary px-2 py-1.5 font-mono text-xs uppercase tracking-widest text-primary-foreground hover:opacity-90"
            >
              <Play className="size-3.5" /> Start <span className="opacity-60">[SPACE]</span>
            </button>
            <button
              onClick={guard(() => simStore.pause(), "Run paused")}
              className="flex items-center gap-1.5 border border-border px-2 py-1.5 font-mono text-xs uppercase tracking-widest doip-btn-solid"
            >
              <Pause className="size-3.5" /> Pause <span className="opacity-60">[SPACE]</span>
            </button>
            <button
              onClick={guard(() => simStore.resume(), "Run resumed")}
              className="flex items-center gap-1.5 border border-border px-2 py-1.5 font-mono text-xs uppercase tracking-widest hover:bg-raised doip-btn-primary"
            >
              <RotateCcw className="size-3.5" /> Resume <span className="opacity-60">[R]</span>
            </button>
            <button
              onClick={guard(() => simStore.stop(), "Run stopped")}
              className="flex items-center gap-1.5 border border-border px-2 py-1.5 font-mono text-xs uppercase tracking-widest text-sev-critical hover:bg-raised doip-btn-primary"
            >
              <Square className="size-3.5" /> Stop <span className="opacity-60">[X]</span>
            </button>
          </div>

          <div className="mt-2">
            <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Speed · {speed}x
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {[1, 2, 4, 5, 8, 10, 16, 20].map((s) => (
                <button
                  key={s}
                  onClick={guard(() => simStore.setSpeed(s), `Speed set to ${s}x`)}
                  className={cn(
                    "h-8 px-2 border font-mono text-xs",
                    speed === s
                      ? "border-primary/60 bg-raised text-primary"
                      : "border-border hover:bg-raised doip-btn-primary",
                  )}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>
          <div className="mt-3 border-t border-border pt-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                State Checkpoint (Snapshot)
              </span>
              {snapshot && (
                <span className="font-mono text-[10px] text-primary">
                  Saved at T+{snapshot.tick} ({snapshot.events.length} evts)
                </span>
              )}
            </div>
            <div className="mt-1.5 flex gap-2">
              <button
                onClick={guard(() => simStore.saveSnapshot(), `Checkpoint saved at tick ${tick}`)}
                disabled={!tick}
                className="flex items-center gap-1.5 border border-border px-2 py-1 font-mono text-xs uppercase tracking-widest hover:bg-raised disabled:opacity-40"
              >
                <BookmarkPlus className="size-3.5" /> Save Checkpoint (T+{tick})
              </button>
              <button
                onClick={guard(
                  () => simStore.restoreSnapshot(),
                  `Checkpoint restored to tick ${snapshot?.tick}`,
                )}
                disabled={!snapshot}
                className="flex items-center gap-1.5 border border-primary/60 bg-primary/10 px-2 py-1 font-mono text-xs uppercase tracking-widest text-primary hover:bg-primary/20 disabled:opacity-40"
              >
                <RotateCcw className="size-3.5" /> Restore Checkpoint
              </button>
            </div>
          </div>

          {!allowed && (
            <p className="mt-2 font-mono text-[10px] text-sev-medium">
              ■ Viewer role is read-only — run controls are disabled.
            </p>
          )}
        </Panel>

        <Panel title="Defensive DSL inject console">
          <div className="space-y-2">
            <p className="text-[11px] text-muted-foreground">
              Inject calibrated tactical injects into the deterministic event loop. Defensive
              operations only.
            </p>
            <div className="flex flex-wrap gap-1.5">
              <button
                onClick={guard(() => {
                  simStore.injectRaw([
                    {
                      type: "weather_spawn",
                      severity: "high",
                      entityId: "weather-storm-beta",
                      payload: {
                        kind: "storm",
                        intensity: 0.85,
                        lat: 28.61,
                        lon: 77.21,
                        radiusKm: 18,
                      },
                    },
                  ]);
                }, "Injected: Severe Weather Front (Intensity 0.85)")}
                className="flex items-center gap-1 border border-border bg-base px-2 py-1 font-mono text-[10px] uppercase tracking-wider hover:border-primary/60"
              >
                <Zap className="size-3 text-sev-high" /> + Severe Storm Cell
              </button>
              <button
                onClick={guard(() => {
                  simStore.injectRaw([
                    {
                      type: "alert_raise",
                      severity: "critical",
                      entityId: "UN-01",
                      payload: {
                        message: "Tactical comms degrade below threshold",
                        entityId: "UN-01",
                      },
                    },
                  ]);
                }, "Injected: Critical Comms Alert UN-01")}
                className="flex items-center gap-1 border border-border bg-base px-2 py-1 font-mono text-[10px] uppercase tracking-wider hover:border-primary/60"
              >
                <Zap className="size-3 text-sev-critical" /> + C2 Comms Drop
              </button>
              <button
                onClick={guard(() => {
                  simStore.injectRaw([
                    {
                      type: "incident_open",
                      severity: "medium",
                      entityId: "UN-02",
                      payload: { kind: "fuel_leak", lat: 28.58, lon: 77.19 },
                    },
                  ]);
                }, "Injected: Fuel Anomaly Incident")}
                className="flex items-center gap-1 border border-border bg-base px-2 py-1 font-mono text-[10px] uppercase tracking-wider hover:border-primary/60"
              >
                <Zap className="size-3 text-sev-medium" /> + Fuel Degrade
              </button>
            </div>
          </div>
        </Panel>

        <Panel
          title="Run history"
          actions={
            <Mono className="text-[10px] text-muted-foreground">LAST {runs.length} / 8</Mono>
          }
        >
          {!runs.length ? (
            <EmptyState
              label="No recorded runs"
              hint="Stop the current run (or start a new one) to log it here with its full event record."
            />
          ) : (
            <ul className="space-y-1">
              {runs
                .slice()
                .reverse()
                .map((r) => (
                  <li
                    key={r.id}
                    className="flex flex-wrap items-center gap-2 border border-border p-1.5"
                  >
                    <span className="font-mono text-xs text-primary">{r.id}</span>
                    <Mono className="text-[10px] text-muted-foreground">
                      {r.scenarioId} · seed {r.seed} · {r.ticks} ticks · {r.events} events
                    </Mono>
                    <div className="ml-auto flex gap-1">
                      <button
                        onClick={guard(() => {
                          setSeedInput(String(r.seed));
                          setPicked(r.scenarioId);
                          simStore.cloneRun(r);
                        }, `Cloned ${r.id} · ${r.scenarioId} · seed ${r.seed}`)}
                        className="flex items-center gap-1 border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest hover:bg-raised"
                        title="Re-run with the same scenario and seed — reproduces the run event-for-event"
                      >
                        <Copy className="size-3" /> Clone seed
                      </button>
                      <Link
                        to="/replay"
                        search={{ run: r.id }}
                        className="flex items-center gap-1 border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-primary hover:bg-raised"
                        title="Open this run in Replay"
                      >
                        <History className="size-3" /> Replay
                      </Link>
                      <button
                        onClick={() =>
                          downloadJson(`doip-${r.id.toLowerCase()}-log.json`, {
                            id: r.id,
                            scenarioId: r.scenarioId,
                            seed: r.seed,
                            ticks: r.ticks,
                            events: r.log,
                          })
                        }
                        className="flex items-center gap-1 border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest hover:bg-raised"
                        title="Export the full event log as JSON"
                      >
                        <Download className="size-3" /> Export
                      </button>
                    </div>
                  </li>
                ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <Stat label="Status" value={status} />
          <Stat label="Tick" value={tick} />
          <Stat label="Seed" value={<Mono>{seed}</Mono>} />
          <Stat label="Events" value={eventCount} />
          <Stat
            label="Hash FNV-1a"
            value={<Mono className="text-xs font-bold text-primary">{fingerprint}</Mono>}
          />
          <Stat label="Checkpoint" value={snapshot ? <Mono>T+{snapshot.tick}</Mono> : "None"} />
        </div>
        <Panel title="Event rate (events / tick)">
          <Sparkline data={rate} height={60} />
          <div className="mt-1 font-mono text-[10px] text-muted-foreground">
            last {rate.length} ticks · peak {rate.length ? Math.max(...rate) : 0}
          </div>
        </Panel>
        <Panel title="Determinism & Integrity">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between border-b border-border pb-1 font-mono text-xs">
              <span className="text-muted-foreground">Rolling Hash</span>
              <span className="font-bold text-primary">{fingerprint}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              The tick engine is a seeded mulberry32 PRNG. Re-running{" "}
              <Mono>
                {picked} / {seedInput}
              </Mono>{" "}
              reproduces this run event-for-event with byte-identical telemetry and golden hashes.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
