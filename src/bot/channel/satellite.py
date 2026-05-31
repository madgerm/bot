"""Satellit-Modus: Runner nutzt Panel für LLM, Qdrant, Medien."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bot.channel.rpc_queue import ChannelRpcQueue, ChannelRpcQueueError
from bot.config import load_runtime_config
from bot.config.models import RuntimeConfig


def is_satellite_runner(config: RuntimeConfig) -> bool:
    llm = config.system.system.llm
    return bool(llm.enabled and llm.mode == "channel")


def is_satellite_root(root: Path | str) -> bool:
    try:
        return is_satellite_runner(load_runtime_config(root))
    except Exception:
        return False


def channel_rpc(
    root: Path | str,
    kind: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    """Synchroner RPC über Panel-Kanal (gecached bei Verbindungsausfall)."""
    queue = ChannelRpcQueue(root)
    req_id = queue.enqueue(kind, payload)
    try:
        return queue.wait_for_result(req_id, timeout_seconds=timeout_seconds)
    except ChannelRpcQueueError as exc:
        raise RuntimeError(str(exc)) from exc
