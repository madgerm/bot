"""Pro-Agent LLM und Panel-Chat-Brücke."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.config.models import AgentBlock, TaskModelEntry, TaskModelsConfig
from bot.llm import LlmStack, ModelRouter
from bot.llm.agent_model import resolve_agent_model


def test_resolve_agent_model_prefers_agent_llm() -> None:
    router = ModelRouter(
        TaskModelsConfig(
            task_models={
                "planning": TaskModelEntry(default="global/planning"),
                "coding": TaskModelEntry(default="global/coding"),
            }
        )
    )
    stack = LlmStack(router=router, client=object())  # type: ignore[arg-type]
    agent = AgentBlock(id="t", role="worker", llm_model="ollama/vision-model")
    model, _ = resolve_agent_model(
        stack, role="worker", task_category="coding", agent=agent
    )
    assert model == "ollama/vision-model"


def test_resolve_agent_model_task_category_fallback() -> None:
    router = ModelRouter(
        TaskModelsConfig(
            task_models={
                "story": TaskModelEntry(default="ollama/story-writer"),
                "coding": TaskModelEntry(default="global/coding"),
            }
        )
    )
    stack = LlmStack(router=router, client=object())  # type: ignore[arg-type]
    agent = AgentBlock(id="w", role="story_writer", task_categories=["story"])
    model, _ = resolve_agent_model(
        stack, role="story_writer", task_category="coding", agent=agent
    )
    assert model == "ollama/story-writer"


def test_enqueue_panel_chat(runtime_project: Path) -> None:
    from bot.chat.orchestrator_bridge import enqueue_panel_chat
    from bot.messages import open_message_service

    msg = enqueue_panel_chat(
        runtime_project,
        "alpha",
        username="max",
        content="Bitte API bauen",
    )
    assert msg.type == "chat.user"
    svc = open_message_service(runtime_project)
    inbox = svc.list_inbox("alpha", "orchestrator")
    assert any(m.id == msg.id for m in inbox)


@pytest.fixture
def panel_client(runtime_project: Path):
    from fastapi.testclient import TestClient

    from bot.web import create_app

    (runtime_project / "config" / "users.json").write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "password": "secret",
                        "role": "admin",
                        "teams": ["alpha"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return TestClient(create_app(runtime_project))


def test_chat_send_queues_orchestrator(panel_client, runtime_project: Path) -> None:
    panel_client.get("/login")
    panel_client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    r = panel_client.post(
        "/teams/alpha/chat/send",
        data={"content": "Hallo Orchestrator", "role": "user"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    from bot.messages import open_message_service

    inbox = open_message_service(runtime_project).list_inbox("alpha", "orchestrator")
    assert any(m.type == "chat.user" for m in inbox)
