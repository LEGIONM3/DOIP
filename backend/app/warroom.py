"""War Room Real-Time Collaboration Hub for DOIP (Phase 2C).

Implements:
- Multi-operator presence tracking, roles, and heartbeats.
- Shared tactical cursor and entity selection sync.
- Operations chat and tactical task board with incident assignment.
- Shared map annotations (points, lines, polygons).
- Incident ownership tracking and handoff workflows.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

try:
    from . import db
except ImportError:
    from app import db

log = logging.getLogger(__name__)


class WarRoomHub:
    """Central real-time collaboration hub managing WebSocket streams and multi-operator state."""

    def __init__(self) -> None:
        self.active_sockets: list[WebSocket] = []
        self.user_sockets: dict[str, WebSocket] = {}  # username -> websocket
        self.presence: dict[str, dict[str, Any]] = {}  # username -> presence info
        self.annotations: list[dict[str, Any]] = []

    async def connect(self, ws: WebSocket, user_info: dict[str, Any]) -> None:
        """Register newly connected operator and broadcast presence."""
        await ws.accept()
        username = user_info.get("username", f"operator_{id(ws) % 1000}")
        name = user_info.get("name", username)
        role = user_info.get("role", "operator")

        self.active_sockets.append(ws)
        self.user_sockets[username] = ws

        presence_data = {
            "username": username,
            "name": name,
            "role": role,
            "status": "online",
            "current_screen": "map",
            "cursor_lat": None,
            "cursor_lon": None,
            "selected_entity": None,
            "last_heartbeat": time.time(),
        }
        self.presence[username] = presence_data

        # Persist presence to DB
        try:
            db.update_warroom_presence(
                username=username,
                name=name,
                role=role,
                status="online",
                current_screen="map",
            )
        except Exception as exc:
            log.debug("WarRoom DB presence notice: %s", exc)

        # 1. Send initial hydration snapshot to new joiner
        tasks = db.list_warroom_tasks()
        await ws.send_json({
            "type": "warroom_sync",
            "payload": {
                "active_presence": list(self.presence.values()),
                "tasks": tasks,
                "annotations": self.annotations[-50:],
                "server_time": time.time(),
            },
        })
        await ws.send_json({"type": "snapshot", "tasks": tasks})

        # 2. Broadcast updated presence to all peers
        await self.broadcast({
            "type": "presence_update",
            "payload": presence_data,
        }, exclude=ws)

        log.info("WarRoom operator connected: %s (%s)", username, role)

    def disconnect(self, ws: WebSocket) -> None:
        """Handle operator disconnect and broadcast status."""
        if ws in self.active_sockets:
            self.active_sockets.remove(ws)

        disconnected_user = None
        for username, user_ws in list(self.user_sockets.items()):
            if user_ws == ws:
                disconnected_user = username
                del self.user_sockets[username]
                if username in self.presence:
                    self.presence[username]["status"] = "offline"
                    try:
                        db.update_warroom_presence(
                            username=username,
                            name=self.presence[username]["name"],
                            role=self.presence[username]["role"],
                            status="offline",
                        )
                    except Exception:
                        pass
                break

        if disconnected_user:
            asyncio.create_task(
                self.broadcast({
                    "type": "presence_update",
                    "payload": {
                        "username": disconnected_user,
                        "status": "offline",
                    },
                })
            )
            log.info("WarRoom operator disconnected: %s", disconnected_user)

    async def broadcast(self, message: dict[str, Any], exclude: WebSocket | None = None) -> None:
        """Broadcast event to all connected operators."""
        stale_sockets = []
        for ws in self.active_sockets:
            if ws == exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                stale_sockets.append(ws)

        for stale in stale_sockets:
            self.disconnect(stale)

    async def handle_message(self, ws: WebSocket, raw: str | dict[str, Any]) -> None:
        """Parse incoming JSON-RPC / event message from operator client."""
        if isinstance(raw, dict):
            data = raw
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return

        msg_type = data.get("type")
        payload = data.get("payload", {})
        if not payload and msg_type in ("add", "advance", "delete"):
            payload = data
        username = payload.get("username", "unknown")

        if msg_type == "cursor_move":
            # Shared cursor coordinates
            if username in self.presence:
                self.presence[username]["cursor_lat"] = payload.get("lat")
                self.presence[username]["cursor_lon"] = payload.get("lon")
                self.presence[username]["last_heartbeat"] = time.time()
            await self.broadcast({
                "type": "cursor_update",
                "payload": {
                    "username": username,
                    "lat": payload.get("lat"),
                    "lon": payload.get("lon"),
                },
            }, exclude=ws)

        elif msg_type == "selection_sync":
            # Selected entity / unit / zone on the tactical map
            if username in self.presence:
                self.presence[username]["selected_entity"] = payload.get("entity_id")
            await self.broadcast({
                "type": "selection_update",
                "payload": {
                    "username": username,
                    "entity_id": payload.get("entity_id"),
                },
            }, exclude=ws)

        elif msg_type == "chat_message":
            # Operations chat
            chat_record = {
                "id": int(time.time() * 1000),
                "username": username,
                "sender_name": payload.get("name", username),
                "role": payload.get("role", "operator"),
                "text": payload.get("text", "").strip(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            # Persist message
            try:
                db.add_audit("chat", f"CHAT_{username}", chat_record["text"][:100])
            except Exception:
                pass

            await self.broadcast({
                "type": "chat_broadcast",
                "payload": chat_record,
            })

        elif msg_type == "map_annotation":
            # Shared drawing or tactical marker
            annotation = {
                "id": payload.get("id") or f"ANN-{int(time.time() * 1000)}",
                "author": username,
                "kind": payload.get("kind", "marker"),  # marker, line, polygon, danger_zone
                "title": payload.get("title", ""),
                "coordinates": payload.get("coordinates", []),
                "color": payload.get("color", "#FBBF24"),
                "created_at": time.time(),
            }
            self.annotations.append(annotation)
            await self.broadcast({
                "type": "annotation_created",
                "payload": annotation,
            })

        elif msg_type == "task_create":
            # New task on the operations board
            created = db.save_warroom_task(payload)
            await self.broadcast({
                "type": "task_updated",
                "payload": created,
            })

        elif msg_type == "task_assign":
            # Assign task / incident to operator
            task_id = payload.get("task_id")
            to_user = payload.get("to_user")
            from_user = payload.get("from_user", username)
            reason = payload.get("reason", "Incident escalation")
            if task_id and to_user:
                db.assign_warroom_task(task_id, to_user, from_user, reason)
                tasks = db.list_warroom_tasks()
                updated_task = next((t for t in tasks if t["id"] == task_id), None)
                await self.broadcast({
                    "type": "task_assigned",
                    "payload": {
                        "task": updated_task,
                        "from_user": from_user,
                        "to_user": to_user,
                        "reason": reason,
                    },
                })


warroom_hub = WarRoomHub()
