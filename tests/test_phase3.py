"""Tests für Phase-3-Features."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bot.web.app import create_app


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """Minimales Projekt-Root mit demo-Team."""
    import shutil

    workspace = Path("/workspace")
    for name in ("config", "teams"):
        src = workspace / name
        if src.is_dir():
            shutil.copytree(src, tmp_path / name, dirs_exist_ok=True)
    (tmp_path / "data").mkdir(exist_ok=True)
    return tmp_path


def test_webhook_ingest(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_WEBHOOK_SECRET", "test-secret")
    from bot.webhooks import WebhookService

    wh = WebhookService(root)
    result = wh.ingest(
        team_id="demo",
        to_agent="orchestrator",
        subject="Test",
        content="Webhook body",
    )
    assert result["subject"] == "Test"


def test_webhook_api_unauthorized(root: Path) -> None:
    app = create_app(root)
    client = TestClient(app)
    r = client.post(
        "/api/v1/webhooks/demo/orchestrator",
        json={"subject": "x", "content": "y"},
    )
    assert r.status_code == 401


def test_webhook_api_ok(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_WEBHOOK_SECRET", "tok")
    app = create_app(root)
    client = TestClient(app)
    r = client.post(
        "/api/v1/webhooks/demo/orchestrator",
        json={"subject": "API", "content": "via http"},
        headers={"X-Webhook-Token": "tok"},
    )
    assert r.status_code == 200
    assert r.json()["subject"] == "API"


def test_tasks_crud(root: Path) -> None:
    from bot.tasks import TaskService

    svc = TaskService.for_team(root, "demo")
    t = svc.create(title="Task 1", description="desc")
    assert t.status == "todo"
    moved = svc.move(t.id, "in_progress")
    assert moved.status == "in_progress"
    tasks = svc.store.list_tasks(status="in_progress")
    assert any(x.id == t.id for x in tasks)


def test_agent_manager(root: Path) -> None:
    from bot.agents_mgmt import AgentManager, AgentManagerError

    mgr = AgentManager(root)
    agents_before = len(mgr.list_agents("demo"))
    mgr.create_agent("demo", agent_id="test-agent-99", role="worker")
    assert len(mgr.list_agents("demo")) == agents_before + 1
    mgr.delete_agent("demo", "test-agent-99")
    assert len(mgr.list_agents("demo")) == agents_before


def test_file_service(root: Path) -> None:
    from bot.files import FileService

    fs = FileService.for_team(root, "demo")
    fs.write_file("readme.md", "# Hello")
    assert fs.read_file("readme.md") == "# Hello"
    entries = fs.list_dir("")
    assert any(e.name == "readme.md" for e in entries)


def test_git_service(root: Path) -> None:
    from bot.git_svc import GitService

    svc = GitService.for_team(root, "demo")
    svc.ensure_repo()
    status = svc.status()
    assert "main" in status or status == "" or "master" in status


def test_story_store(root: Path) -> None:
    from bot.story import StoryService

    svc = StoryService.for_team(root, "demo")
    c = svc.store.save_character("Alice", "Protagonistin")
    w = svc.store.save_world("Welt A", "Beschreibung")
    s = svc.store.save_scene("Szene 1", "Es war einmal…", world_id=w.id)
    assert c.name == "Alice"
    assert s.world_id == w.id


def test_media_image_webhook_error(root: Path) -> None:
    from bot.media import MediaService, MediaServiceError

    with pytest.raises((MediaServiceError, Exception)):
        MediaService.for_team(root, "demo").generate_image("test")


def test_deploy_generate(root: Path) -> None:
    from bot.deploy import DeployService

    paths = DeployService(root).write_artifacts("demo", root / "out")
    assert Path(paths["systemd"]).is_file()
    assert Path(paths["provision"]).is_file()


def test_tasks_web(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_SESSION_SECRET", "test")
    app = create_app(root)
    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "changeme"})
    r = client.get("/teams/demo/tasks")
    assert r.status_code == 200


def test_broker_not_active(root: Path) -> None:
    from bot.messages.broker import MessageBroker

    assert MessageBroker.from_root(root) is None
