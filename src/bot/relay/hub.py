"""Raum-basierter Relay: leitet Panel ↔ Runner durch."""

from __future__ import annotations

import asyncio
import logging
import secrets
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


@dataclass
class RelayRoom:
    room_id: str
    panel: WebSocket | None = None
    runner: WebSocket | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RelayHub:
    def __init__(self, *, token: str | None = None) -> None:
        self._token = token
        self._rooms: dict[str, RelayRoom] = {}

    def verify_token(self, provided: str | None) -> bool:
        if not self._token:
            return True
        if not provided:
            return False
        return secrets.compare_digest(provided, self._token)

    def _room(self, room_id: str) -> RelayRoom:
        if room_id not in self._rooms:
            self._rooms[room_id] = RelayRoom(room_id=room_id)
        return self._rooms[room_id]

    async def connect(self, websocket: WebSocket, *, role: str, room_id: str) -> None:
        await websocket.accept()
        room = self._room(room_id)
        async with room.lock:
            if role == "panel":
                room.panel = websocket
            elif role == "runner":
                room.runner = websocket
            else:
                await websocket.close(code=4000, reason="role muss panel oder runner sein")
                return
        logger.info("Relay: %s verbunden (Raum %s)", role, room_id)
        try:
            while True:
                raw = await websocket.receive_text()
                await self._forward(room, role, raw)
        except WebSocketDisconnect:
            pass
        finally:
            async with room.lock:
                if role == "panel" and room.panel is websocket:
                    room.panel = None
                if role == "runner" and room.runner is websocket:
                    room.runner = None
            logger.info("Relay: %s getrennt (Raum %s)", role, room_id)

    async def _forward(self, room: RelayRoom, from_role: str, raw: str) -> None:
        async with room.lock:
            target = room.runner if from_role == "panel" else room.panel
            if target is None:
                return
            try:
                await target.send_text(raw)
            except Exception as exc:
                logger.warning("Relay forward: %s", exc)


_hub: RelayHub | None = None


def get_relay_hub(token: str | None = None) -> RelayHub:
    global _hub
    if _hub is None:
        _hub = RelayHub(token=token)
    return _hub
