"""WebSocket connection manager for customer and agent real-time messaging."""

import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._customer_connections: dict[str, list[WebSocket]] = {}
        self._agent_connections: list[WebSocket] = []

    async def connect_customer(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self._customer_connections.setdefault(session_id, []).append(websocket)

    def disconnect_customer(self, session_id: str, websocket: WebSocket):
        conns = self._customer_connections.get(session_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._customer_connections.pop(session_id, None)

    async def connect_agent(self, websocket: WebSocket):
        await websocket.accept()
        self._agent_connections.append(websocket)

    def disconnect_agent(self, websocket: WebSocket):
        if websocket in self._agent_connections:
            self._agent_connections.remove(websocket)

    async def send_to_session(self, session_id: str, payload: dict[str, Any]):
        message = json.dumps(payload)
        for ws in list(self._customer_connections.get(session_id, [])):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect_customer(session_id, ws)

    async def broadcast_to_agents(self, payload: dict[str, Any]):
        message = json.dumps(payload)
        for ws in list(self._agent_connections):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect_agent(ws)


ws_manager = ConnectionManager()
