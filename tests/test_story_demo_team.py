"""Story-Demo-Team: 9 Agents, Config, Handler, Inbox-Delegation."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.config import load_runtime_config
from bot.runtime.handlers import StoryOrchestratorHandler, StoryWriterHandler, handler_for_role
from bot.story import StoryDB, StoryReviewRunner


def test_story_demo_team_loads() -> None:
    cfg = load_runtime_config(Path("/workspace"))
    assert "story-demo" in cfg.teams
    bundle = cfg.teams["story-demo"]
    assert len(bundle.agents) == 9
    assert "drehbuch-autor" in bundle.agents
    assert "logik-pruefer" in bundle.agents
    assert bundle.team.team.orchestrator_id == "orchestrator"


def test_story_handlers_when_story_data_exists(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(Path("/workspace/teams/story-demo"), tmp_path / "teams" / "story-demo")
    db = StoryDB(tmp_path, "story-demo")
    db.ensure_story(title="Test")
    h_orch = handler_for_role("orchestrator", team_id="story-demo", root=tmp_path)
    assert isinstance(h_orch, StoryOrchestratorHandler)
    h_writer = handler_for_role("story_writer", team_id="story-demo", root=tmp_path)
    assert isinstance(h_writer, StoryWriterHandler)


def test_review_dispatches_to_existing_agents(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(Path("/workspace"), tmp_path, dirs_exist_ok=True)
    db = StoryDB(tmp_path, "story-demo")
    db.ensure_story(title="Demo")
    ch = db.add_chapter()
    sc = db.add_scene(ch, content="Testszene.")
    runner = StoryReviewRunner(tmp_path, "story-demo")
    cfg = load_runtime_config(tmp_path)
    bundle = cfg.teams["story-demo"]
    results = runner.review_scene_parallel(
        ch, sc.scene_id, dispatch_inbox=True
    )
    assert len(results) == 7
    inbox = tmp_path / "teams/story-demo/agents/logik-pruefer/inbox"
    pending = list(inbox.glob("*.json"))
    assert len(pending) >= 1
    assert "logik-pruefer" in bundle.agents
