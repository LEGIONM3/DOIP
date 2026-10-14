/**
 * War Room Real-Time Collaboration Service Client (Phase 2C).
 *
 * Implements:
 * - Real-time WebSocket connection (/ws/warroom) with auto-reconnect.
 * - Multi-operator presence & live cursor / selection synchronization.
 * - Operations chat & tactical task board with incident assignment.
 * - Shared tactical map annotations.
 */

export interface WarRoomPresence {
  username: string;
  name: string;
  role: string;
  status: "online" | "away" | "busy" | "offline";
  current_screen?: string;
  cursor_lat?: number | null;
  cursor_lon?: number | null;
  selected_entity?: string | null;
  last_heartbeat?: number;
}

export interface WarRoomTask {
  id?: number;
  title: string;
  description: string;
  incident_id?: string | null;
  assigned_to?: string | null;
  status: "TODO" | "IN_PROGRESS" | "DONE" | "BLOCKED" | "open" | "doing" | "done";
  priority: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  created_by?: string;
  created_at?: string;
  updated_at?: string;
  assignments?: Array<{
    id: number;
    from_user: string;
    to_user: string;
    reason: string;
    created_at: string;
  }>;
}

export interface WarRoomAnnotation {
  id: string;
  author: string;
  kind: "marker" | "line" | "polygon" | "danger_zone";
  title: string;
  coordinates: [number, number][];
  color: string;
  created_at?: number;
}

export interface WarRoomChatMessage {
  id: number;
  username: string;
  sender_name: string;
  role: string;
  text: string;
  timestamp: string;
}

export interface WarRoomSocketHandlers {
  onSync?: (data: {
    active_presence: WarRoomPresence[];
    tasks: WarRoomTask[];
    annotations: WarRoomAnnotation[];
  }) => void;
  onPresenceUpdate?: (presence: WarRoomPresence) => void;
  onCursorUpdate?: (data: { username: string; lat: number; lon: number }) => void;
  onSelectionUpdate?: (data: { username: string; entity_id: string | null }) => void;
  onChatMessage?: (msg: WarRoomChatMessage) => void;
  onTaskUpdated?: (task: WarRoomTask) => void;
  onTaskAssigned?: (data: { task: WarRoomTask; from_user: string; to_user: string; reason: string }) => void;
  onAnnotationCreated?: (ann: WarRoomAnnotation) => void;
  onOpen?: () => void;
  onClose?: () => void;
}

const BASE_URL = (
  (import.meta.env?.["VITE_DOIP_API_URL"] as string | undefined) ?? "http://localhost:8000"
).replace(/\/$/, "");

const WS_BASE_URL = BASE_URL.replace(/^http/, "ws");

function getAuthHeader(): Record<string, string> {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("doip.token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getWarRoomPresence(): Promise<WarRoomPresence[]> {
  try {
    const res = await fetch(`${BASE_URL}/api/warroom/presence`, { headers: getAuthHeader() });
    if (res.ok) {
      const data = await res.json();
      return data.presence || [];
    }
  } catch {}
  return [];
}

export async function getWarRoomTasks(
  incidentId?: string,
  status?: string,
): Promise<WarRoomTask[]> {
  try {
    const url = new URL(`${BASE_URL}/api/warroom/tasks`);
    if (incidentId) url.searchParams.set("incident_id", incidentId);
    if (status) url.searchParams.set("status", status);

    const res = await fetch(url.toString(), { headers: getAuthHeader() });
    if (res.ok) {
      const data = await res.json();
      return data.tasks || [];
    }
  } catch {}
  return [];
}

export async function createWarRoomTask(task: Partial<WarRoomTask>): Promise<WarRoomTask> {
  const res = await fetch(`${BASE_URL}/api/warroom/tasks`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify(task),
  });

  if (!res.ok) {
    throw new Error(`Failed to create task: HTTP ${res.status}`);
  }
  return (await res.json()) as WarRoomTask;
}

export async function assignWarRoomTask(
  taskId: number,
  assignedTo: string,
  reason = "",
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/warroom/tasks/${taskId}/assign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeader(),
    },
    body: JSON.stringify({ assigned_to: assignedTo, reason }),
  });

  if (!res.ok) {
    throw new Error(`Failed to assign task: HTTP ${res.status}`);
  }
  return await res.json();
}

/**
 * Open resilient WebSocket connection to /ws/warroom with full event dispatching.
 */
export function connectWarRoomSocket(handlers: WarRoomSocketHandlers): {
  sendCursor: (username: string, lat: number, lon: number) => void;
  sendSelection: (username: string, entityId: string | null) => void;
  sendChat: (username: string, name: string, role: string, text: string) => void;
  sendAnnotation: (annotation: WarRoomAnnotation) => void;
  close: () => void;
} {
  const token = typeof window !== "undefined" ? window.localStorage.getItem("doip.token") : "demo";
  const url = `${WS_BASE_URL}/ws/warroom?token=${encodeURIComponent(token || "demo")}`;

  let ws: WebSocket | null = null;
  let closedManually = false;

  function init() {
    ws = new WebSocket(url);

    ws.onopen = () => {
      handlers.onOpen?.();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const type = msg.type;
        const payload = msg.payload;

        if (type === "warroom_sync") {
          handlers.onSync?.(payload);
        } else if (type === "presence_update") {
          handlers.onPresenceUpdate?.(payload);
        } else if (type === "cursor_update") {
          handlers.onCursorUpdate?.(payload);
        } else if (type === "selection_update") {
          handlers.onSelectionUpdate?.(payload);
        } else if (type === "chat_broadcast") {
          handlers.onChatMessage?.(payload);
        } else if (type === "task_updated") {
          handlers.onTaskUpdated?.(payload);
        } else if (type === "task_assigned") {
          handlers.onTaskAssigned?.(payload);
        } else if (type === "annotation_created") {
          handlers.onAnnotationCreated?.(payload);
        }
      } catch (err) {
        // parse error ignored
      }
    };

    ws.onclose = () => {
      handlers.onClose?.();
      if (!closedManually) {
        setTimeout(init, 3000); // auto reconnect
      }
    };
  }

  init();

  function safeSend(data: any) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data));
    }
  }

  return {
    sendCursor: (username, lat, lon) => {
      safeSend({ type: "cursor_move", payload: { username, lat, lon } });
    },
    sendSelection: (username, entityId) => {
      safeSend({ type: "selection_sync", payload: { username, entity_id: entityId } });
    },
    sendChat: (username, name, role, text) => {
      safeSend({ type: "chat_message", payload: { username, name, role, text } });
    },
    sendAnnotation: (annotation) => {
      safeSend({ type: "map_annotation", payload: annotation });
    },
    close: () => {
      closedManually = true;
      if (ws) ws.close();
    },
  };
}
