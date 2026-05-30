"""Tests für Phase-3-Features."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from bot.web.app import create_app


@pytest.fixture
def root(tmp_path: Path) -> Path:
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


def test_communication_is_direct_only(root: Path) -> None:
    from bot.config import load_runtime_config

    cfg = load_runtime_config(root)
    assert cfg.system.system.communication.mode == "direct"


def test_story_file_structure(root: Path) -> None:
    from bot.story import StoryDB

    db = StoryDB(root, "demo")
    db.ensure_story(
        title="Testroman",
        genre="Sci-Fi",
        setting="München 2045",
        main_characters=["Max"],
    )
    assert (db.path / "AGENTS.md").is_file()
    assert (db.path / "meta.json").is_file()
    db.save_character(
        "max_mueller",
        {
            "name": "Max Müller",
            "role": "Protagonist",
            "background": "Informatiker",
            "relationships": [{"to": "anna", "type": "Freundin"}],
        },
    )
    assert (db.path / "characters" / "max_mueller.json").is_file()
    ch = db.add_chapter()
    scene = db.add_scene(ch, title="Eröffnung", content="Es war dunkel.")
    meta, body = db.get_scene(ch, scene.scene_id)
    assert "dunkel" in body
    db.update_scene(ch, scene.scene_id, "Neuer Text.", expected_version=1)
    _, body2 = db.get_scene(ch, scene.scene_id)
    assert body2 == "Neuer Text."


def test_story_version_conflict(root: Path) -> None:
    from bot.story import StoryDB, StoryDBError

    db = StoryDB(root, "demo")
    db.ensure_story(title="X")
    ch = db.add_chapter()
    s = db.add_scene(ch, content="a")
    with pytest.raises(StoryDBError):
        db.update_scene(ch, s.scene_id, "b", expected_version=99)


def test_crawl4ai_markdown_extracted() -> None:
    from bot.crawl.service import _markdown_from_result

    md_obj = MagicMock()
    md_obj.fit_markdown = "# Hauptinhalt\n\nText ohne Menü."
    md_obj.raw_markdown = "# Raw\n\nNav Menu Footer"
    result = MagicMock(markdown=md_obj)
    assert "Hauptinhalt" in _markdown_from_result(result)


@patch("bot.crawl.service.asyncio.run")
def test_crawl_url_uses_crawl4ai(mock_run: MagicMock, root: Path, tmp_path: Path) -> None:
    def _run_mock(coro):
        if asyncio.iscoroutine(coro):
            coro.close()
        return {
            "url": "https://example.com",
            "title": "Example",
            "markdown": "# Example Domain\n\nContent only.",
            "crawled_at": "2026-01-01T00:00:00+00:00",
            "content_hash": "abc",
            "engine": "crawl4ai",
        }

    mock_run.side_effect = _run_mock
    crawl_json = tmp_path / "teams" / "demo" / "crawl.json"
    crawl_json.parent.mkdir(parents=True, exist_ok=True)
    crawl_json.write_text(
        json.dumps(
            {
                "crawl": {
                    "enabled": True,
                    "domains": [{"url": "https://example.com", "max_pages": 1}],
                    "snapshot_dir": f"data/demo/crawl",
                }
            }
        ),
        encoding="utf-8",
    )
    import shutil

    shutil.copytree(Path("/workspace/teams/demo"), root / "teams" / "demo", dirs_exist_ok=True)
    (root / "teams" / "demo" / "crawl.json").write_text(crawl_json.read_text(), encoding="utf-8")

    from bot.crawl import CrawlService

    svc = CrawlService.for_team(root, "demo")
    page = svc.crawl_url("https://example.com")
    assert page["engine"] == "crawl4ai"
    assert "Content only" in page["markdown"]
