import { useCallback, useSyncExternalStore } from "react";
import type { WorkspaceId } from "@/lib/workspaces";

export interface OperationalContextState {
  activeWorkspace: WorkspaceId;
  activeRunId: string | null;
  activeScenarioId: string | null;
  selectedEntityId: string | null;
  selectedIncidentId: string | null;
  selectedEventId: number | null;
  selectedTaskId: string | null;
  aiDrawerOpen: boolean;
  aiPrefillPrompt: string | null;
  pendingApprovalsCount: number;
}

const initialContext: OperationalContextState = {
  activeWorkspace: "command",
  activeRunId: null,
  activeScenarioId: "SC-1",
  selectedEntityId: null,
  selectedIncidentId: null,
  selectedEventId: null,
  selectedTaskId: null,
  aiDrawerOpen: false,
  aiPrefillPrompt: null,
  pendingApprovalsCount: 2, // Default staged HITL directives awaiting sign-off
};

class OperationalContextStore {
  private state: OperationalContextState = initialContext;
  private listeners = new Set<() => void>();

  getState = () => this.state;

  subscribe = (cb: () => void) => {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  };

  private set(patch: Partial<OperationalContextState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((l) => l());
  }

  setWorkspace(activeWorkspace: WorkspaceId) {
    this.set({ activeWorkspace });
  }

  selectEntity(selectedEntityId: string | null) {
    this.set({ selectedEntityId });
  }

  selectIncident(selectedIncidentId: string | null) {
    this.set({ selectedIncidentId });
  }

  selectEvent(selectedEventId: number | null) {
    this.set({ selectedEventId });
  }

  selectTask(selectedTaskId: string | null) {
    this.set({ selectedTaskId });
  }

  selectRun(activeRunId: string | null) {
    this.set({ activeRunId });
  }

  selectScenario(activeScenarioId: string | null) {
    this.set({ activeScenarioId });
  }

  setAiDrawerOpen(aiDrawerOpen: boolean) {
    this.set({ aiDrawerOpen });
  }

  setAiPrefillPrompt(aiPrefillPrompt: string | null) {
    this.set({ aiPrefillPrompt, aiDrawerOpen: true });
  }

  setPendingApprovalsCount(pendingApprovalsCount: number) {
    this.set({ pendingApprovalsCount: Math.max(0, pendingApprovalsCount) });
  }

  decrementPendingApproval() {
    this.set({ pendingApprovalsCount: Math.max(0, this.state.pendingApprovalsCount - 1) });
  }

  // -------------------------------------------------------------------------
  // Typed Cross-Feature Workflow Handoffs (Phase 5)
  // -------------------------------------------------------------------------

  /** Handoff from Incident / Alert / Live Map to Contextual AI Inquiry */
  handoffToAi(opts: { prompt: string; incidentId?: string; entityId?: string }) {
    this.set({
      selectedIncidentId: opts.incidentId ?? this.state.selectedIncidentId,
      selectedEntityId: opts.entityId ?? this.state.selectedEntityId,
      aiPrefillPrompt: opts.prompt,
      aiDrawerOpen: true,
    });
  }

  /** Handoff from Logistics or Personnel warning to Mission Planning route */
  handoffToPlanner(opts: { unitId?: string; taskId?: string }) {
    this.set({
      activeWorkspace: "simulation",
      selectedEntityId: opts.unitId ?? this.state.selectedEntityId,
      selectedTaskId: opts.taskId ?? this.state.selectedTaskId,
    });
  }

  /** Handoff from Simulation execution to Replay scrubber & AAR */
  handoffToReplay(opts: { runId: string }) {
    this.set({
      activeWorkspace: "simulation",
      activeRunId: opts.runId,
    });
  }

  /** Handoff from live battle to isolated What-If branch */
  handoffToWhatIf(opts: { scenarioId?: string; prompt?: string }) {
    this.set({
      activeWorkspace: "simulation",
      activeScenarioId: opts.scenarioId ?? this.state.activeScenarioId,
      aiPrefillPrompt: opts.prompt ?? null,
    });
  }

  /** Handoff from active incident to Causal Knowledge Graph */
  handoffToGraph(opts: { incidentId: string }) {
    this.set({
      activeWorkspace: "intelligence",
      selectedIncidentId: opts.incidentId,
    });
  }
}

export const contextStore = new OperationalContextStore();

export function useOperationalContext<T>(selector: (s: OperationalContextState) => T): T {
  const getSnapshot = useCallback(() => selector(contextStore.getState()), [selector]);
  return useSyncExternalStore(contextStore.subscribe, getSnapshot, getSnapshot);
}
