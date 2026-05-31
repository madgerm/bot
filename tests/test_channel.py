"""Bidirektionaler Panel↔Runner-Kanal (Queue + WebSocket)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.channel.queue import LlmChannelQueue
from bot.config import load_runtime_config
from bot.llm import build_llm_stack
from bot.llm.channel_client import ChannelLlmClient


def test_channel_queue_persist_and_complete(tmp_path: Path) -> None:
    q = LlmChannelQueue(tmp_path)
    req_id = q.enqueue(
        model="ollama/x",
        messages=[{"role": "user", "content": "Hi"}],
        fallbacks=[],
    )
    assert q.list_pending()
    q.complete(req_id, "Antwort")
    assert q.wait_for_result(req_id, timeout_seconds=1.0) == "Antwort"


def test_channel_queue_survives_restart(tmp_path: Path) -> None:
    q1 = LlmChannelQueue(tmp_path)
    req_id = q1.enqueue(
        model="m",
        messages=[{"role": "user", "content": "x"}],
        fallbacks=[],
    )
    q2 = LlmChannelQueue(tmp_path)
    assert any(p["id"] == req_id for p in q2.list_pending())
    q2.complete(req_id, "nach Reconnect")
    assert q2.wait_for_result(req_id, timeout_seconds=1.0) == "nach Reconnect"


def test_build_llm_stack_channel_mode(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config" / "system.json").write_text(
        json.dumps(
            {
                "system": {
                    "name": "r",
                    "llm": {"enabled": True, "mode": "channel", "timeout_seconds": 60},
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "config" / "task_models.json").write_text(
        json.dumps(
            {"task_models": {"planning": {"default": "m", "alternatives": []}}}
        ),
        encoding="utf-8",
    )
    stack = build_llm_stack(load_runtime_config(tmp_path), root=tmp_path)
    assert isinstance(stack.client, ChannelLlmClient)


def test_channel_queue_fail(tmp_path: Path) -> None:
    q = LlmChannelQueue(tmp_path)
    req_id = q.enqueue(
        model="m",
        messages=[{"role": "user", "content": "x"}],
        fallbacks=[],
    )
    q.fail(req_id, "Ollama down")
    with pytest.raises(Exception, match="Ollama"):
        q.wait_for_result(req_id, timeout_seconds=1.0)
