"""Team-Feed und Direkt-PM."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bot.chat import ChatStore
from bot.chat.direct_agent import list_direct_agents, send_direct_to_agent
from bot.chat.direct_chat import record_direct_assistant
from bot.chat.team_feed import build_team_feed, collect_agent_messages
from bot.messages import open_message_service


def test_build_team_feed_nests_internal_between_panel(runtime_project: Path) -> None:
    store = ChatStore(runtime_project, "alpha")
    store.add(
        role="user",
        content="Panel A",
        agent_id="orchestrator",
        metadata={"username": "u"},
    )
    store.add(
        role="user",
        content="Panel B",
        agent_id="orchestrator",
        metadata={"username": "u"},
    )

    svc = open_message_service(runtime_project)
    svc.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-exec",
        subject="Delegieren",
        content="Bitte umsetzen",
        type="task.assign",
        task_category="coding",
    )

    feed = build_team_feed(
        runtime_project, "alpha", "orchestrator", include_internal=True
    )
    kinds = [ln.kind for ln in feed]
    assert "panel" in kinds
    assert "internal" in kinds
    internal = [ln for ln in feed if ln.kind == "internal"]
    assert internal[0].indent == 1
    panel_user = next(ln for ln in feed if ln.kind == "panel" and ln.content == "Panel A")
    assert panel_user.bubble_side == "out"
    assert panel_user.role == "user"


def test_build_team_feed_panel_only(runtime_project: Path) -> None:
    store = ChatStore(runtime_project, "alpha")
    store.add(role="user", content="Nur Panel", agent_id="orchestrator")
    open_message_service(runtime_project).send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-exec",
        subject="x",
        content="intern",
        type="task.assign",
        task_category="coding",
    )
    feed = build_team_feed(
        runtime_project, "alpha", "orchestrator", include_internal=False
    )
    assert all(ln.kind == "panel" for ln in feed)


def test_direct_assistant_reply_in_feed(runtime_project: Path) -> None:
    send_direct_to_agent(
        runtime_project,
        "alpha",
        username="admin",
        target_agent="worker-exec",
        content="Frage?",
    )
    record_direct_assistant(
        runtime_project, "alpha", "worker-exec", "Ja, klar — hier die Antwort."
    )
    feed = build_team_feed(
        runtime_project, "alpha", "orchestrator", direct_agent="worker-exec"
    )
    assert any("Ja, klar" in ln.content for ln in feed)
    assistant = [ln for ln in feed if "assistant" in ln.label]
    assert assistant
    assert "worker-exec" in assistant[0].label


def test_send_direct_to_agent(runtime_project: Path) -> None:
    msg = send_direct_to_agent(
        runtime_project,
        "alpha",
        username="admin",
        target_agent="worker-exec",
        content="Kurze Frage",
    )
    assert msg.type == "chat.direct"
    assert msg.to_agent == "worker-exec"
    inbox = open_message_service(runtime_project).list_inbox("alpha", "worker-exec")
    assert any(m.id == msg.id for m in inbox)

    feed = build_team_feed(
        runtime_project, "alpha", "orchestrator", direct_agent="worker-exec"
    )
    assert any("Kurze Frage" in ln.content for ln in feed)


def test_list_direct_agents_excludes_orchestrator(runtime_project: Path) -> None:
    rows = list_direct_agents(runtime_project, "alpha")
    ids = {r["id"] for r in rows}
    assert "orchestrator" not in ids
    assert "worker-exec" in ids


def test_collect_agent_messages_dedupes(runtime_project: Path) -> None:
    svc = open_message_service(runtime_project)
    msg = svc.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="worker-exec",
        subject="s",
        content="c",
        type="task.assign",
        task_category="coding",
    )
    rows = collect_agent_messages(runtime_project, "alpha")
    assert sum(1 for m in rows if m.id == msg.id) == 1


@pytest.fixture
def panel_client(runtime_project: Path) -> TestClient:
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


def test_chat_direct_route(panel_client: TestClient, runtime_project: Path) -> None:
    panel_client.get("/login")
    panel_client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    r = panel_client.post(
        "/teams/alpha/chat/send",
        data={"content": "PM Inhalt", "role": "user", "direct": "worker-exec"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "direct=worker-exec" in r.headers["location"]

    page = panel_client.get("/teams/alpha/chat?direct=worker-exec")
    assert page.status_code == 200
    assert "Direkt-Chat" in page.text
    assert "PM Inhalt" in page.text


def test_chat_feed_fragment(panel_client: TestClient) -> None:
    panel_client.get("/login")
    panel_client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    r = panel_client.get("/teams/alpha/chat/fragment?direct=worker-exec")
    assert r.status_code == 200
    assert "chat-feed" not in r.text
