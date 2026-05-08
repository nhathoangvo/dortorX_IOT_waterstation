from __future__ import annotations
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections per user_id for real-time dashboard updates."""

    def __init__(self):
        # user_id -> set of active WebSocket connections
        self._connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self._connections.setdefault(user_id, set()).add(websocket)
        logger.info("WS connected user=%s total=%s", user_id, len(self._connections[user_id]))

    def disconnect(self, websocket: WebSocket, user_id: int):
        conns = self._connections.get(user_id, set())
        conns.discard(websocket)
        if not conns:
            self._connections.pop(user_id, None)
        logger.info("WS disconnected user=%s", user_id)

    async def broadcast_to_user(self, user_id: int, data: dict):
        conns = list(self._connections.get(user_id, set()))
        dead = []
        for ws in conns:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, user_id)

    async def broadcast_all(self, data: dict):
        for uid in list(self._connections.keys()):
            await self.broadcast_to_user(uid, data)


manager = ConnectionManager()
