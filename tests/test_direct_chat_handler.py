"""Handler für chat.direct (Dialog ohne Pipeline)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from bot.chat.team_feed import build_team_feed
from bot.config.models import AgentBlock, TaskModelEntry, TaskModelsConfig
from bot.llm import LlmStack, ModelRouter
from bot.messages.models import Message
from bot.runtime.context import HandlerContext
from bot.runtime.handlers import WorkerExecHandler


def _message() -> Message:
    return Message(
        id="msg-direct-1",
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-exec",
        subject="PM: admin",
        content="[Direkt-PM von admin]\nWie geht's?",
        type="chat.direct",
        status="processing",
        task_category="planning",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_worker_chat_direct_no_delegation(
    runtime_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handler = WorkerExecHandler()
    router = ModelRouter(
        TaskModelsConfig(
            task_models={"planning": TaskModelEntry(default="stub/plan")}
        )
    )
    stack = LlmStack(router=router, client=object())  # type: ignore[arg-type]
    ctx = HandlerContext(
        root=runtime_project,
        team_id="alpha",
        agent_id="worker-exec",
        role="worker",
        llm_stack=stack,
        agent=AgentBlock(id="worker-exec", role="worker"),
    )
    monkeypatch.setattr(
        "bot.runtime.handlers.run_tool_loop",
        lambda *a, **k: "Alles gut, danke der Nachfrage.",
    )

    result = handler.handle(_message(), ctx)
    assert result.complete
    assert not result.delegates

    feed = build_team_feed(
        runtime_project, "alpha", "orchestrator", direct_agent="worker-exec"
    )
    assert any("Alles gut" in ln.content for ln in feed)
