# War Room Real-Time Collaboration Specification (Phase 2C)

**Owner:** WARROOM_ENGINEER Agent (ECC Protocol)  
**Program:** Defense Operations Intelligence Platform (DOIP)  

---

## 1. Collaboration Hub Architecture

The War Room enables simultaneous tactical collaboration across operators (`analyst`, `operator`, `planner`, `admin`).

```text
Web Browser (Operator 1)   Web Browser (Operator 2)   Web Browser (Commander)
        │                           │                           │
        └───────────────────┬───────┴───────────────────────────┘
                            │ WS /ws/warroom?token=<JWT>
                            ▼
              ┌───────────────────────────┐
              │    WarRoom WebSocket Hub  │
              │  (Presence, Map, Tasks)   │
              └─────────────┬─────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      In-Memory Pub/Sub          PostgreSQL Persistence
    (Broadcast to Peers)      (Messages, Tasks, Assignments)
```

---

## 2. Event Types & Protocols

### 2.1 Presence & Heartbeat
```json
{
  "type": "presence_update",
  "payload": {
    "user_id": "operator_1",
    "name": "Capt. Miller",
    "role": "operator",
    "status": "active",
    "current_screen": "map",
    "last_seen": 1720000000
  }
}
```

### 2.2 Shared Tactical Cursor & Entity Selection
```json
{
  "type": "cursor_move",
  "payload": {
    "user_id": "operator_1",
    "lat": 12.981,
    "lon": 77.592,
    "selected_entity": "UAV-01"
  }
}
```

### 2.3 Operations Task Board & Incident Assignment
- Tasks support: `TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`.
- Incident Ownership: Direct mapping between an active Incident (`INC-101`) and an assigned Operator.
- Handoff Workflow: Records origin operator, recipient operator, reason, and timestamp.

---

## 3. Endpoints & WebSocket Protocol
- `WS /ws/warroom`: Bi-directional real-time event pipe with JWT token query.
- `GET /api/warroom/presence`: List currently active operators and statuses.
- `GET /api/warroom/tasks`: Query tactical tasks.
- `POST /api/warroom/tasks`: Create task.
- `POST /api/warroom/tasks/{id}/assign`: Assign task/incident to operator.
- `GET /api/warroom/messages`: Query recent chat & announcement history.
