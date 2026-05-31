"""FastAPI-App für den Internet-Relay (`bot relay serve`)."""

from __future__ import annotations

import os

from fastapi import FastAPI, WebSocket, WebSocketException, status

from bot.relay.hub import get_relay_hub


def create_relay_app() -> FastAPI:
    token = os.environ.get("BOT_RELAY_TOKEN")
    hub = get_relay_hub(token)

    app = FastAPI(title="Bot Channel Relay", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "bot-relay"}

    @app.websocket("/ws")
    async def relay_ws(websocket: WebSocket) -> None:
        role = websocket.query_params.get("role", "").strip().lower()
        room = websocket.query_params.get("room", "default").strip() or "default"
        tok = websocket.query_params.get("token")
        if not hub.verify_token(tok):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Ungültiger Token",
            )
        if role not in ("panel", "runner"):
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="role=panel oder role=runner erforderlich",
            )
        await hub.connect(websocket, role=role, room_id=room)

    return app
