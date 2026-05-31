"""JSON-Nachrichten für den Panel↔Runner-Kanal (WebSocket)."""

from __future__ import annotations

import json
from typing import Any, Literal

ChannelType = Literal[
    "channel.hello",
    "ping",
    "pong",
    "llm.request",
    "llm.response",
    "llm.error",
    "rpc.request",
    "rpc.response",
    "rpc.error",
]


def encode_message(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def decode_message(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError("Ungültige Kanal-Nachricht")
    return data
