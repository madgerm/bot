"""Story: Plot, Graph, parallele Reviews, Memory."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bot.story import StoryDB, StoryReviewRunner
from bot.story.graph import relationships_mermaid


@pytest.fixture
def story_root(tmp_path: Path) -> Path:
    import shutil

    for name in ("config", "teams"):
        shutil.copytree(Path("/workspace") / name, tmp_path / name, dirs_exist_ok=True)
    return tmp_path


def test_plot_outline(story_root: Path) -> None:
    db = StoryDB(story_root, "demo")
    db.ensure_story(title="Test")
    plot = {
        "structure": "three_act",
        "acts": [
            {
                "act": 1,
                "title": "Setup",
                "chapters": [{"id": "kapitel-001", "title": "Start", "beats": ["Hook"]}],
            }
        ],
        "notes": "Testnotiz",
    }
    db.save_plot(plot)
    loaded = db.get_plot()
    assert loaded["acts"][0]["title"] == "Setup"


def test_relationship_graph_mermaid(story_root: Path) -> None:
    db = StoryDB(story_root, "demo")
    db.ensure_story(title="G")
    db.save_character(
        "max",
        {
            "name": "Max",
            "relationships": [{"to": "anna", "type": "Freundin"}],
        },
    )
    db.save_character("anna", {"name": "Anna", "relationships": []})
    mm = relationships_mermaid(db)
    assert "Max" in mm
    assert "anna" in mm or "Anna" in mm


def test_parallel_review_stub_llm(story_root: Path) -> None:
    db = StoryDB(story_root, "demo")
    db.ensure_story(title="R")
    ch = db.add_chapter()
    sc = db.add_scene(ch, content="Max betritt den Raum.")
    runner = StoryReviewRunner(story_root, "demo")
    results = runner.review_scene_parallel(ch, sc.scene_id, dispatch_inbox=False)
    assert len(results) >= 5
    assert all(r.checker_id for r in results)


def test_gather_memory_documents(story_root: Path) -> None:
    db = StoryDB(story_root, "demo")
    db.ensure_story(title="M")
    docs = db.gather_memory_documents()
    kinds = {d["kind"] for d in docs}
    assert "meta" in kinds


@patch("bot.qdrant.service.QdrantService.from_root")
def test_story_memory_reindex(mock_from: MagicMock, story_root: Path) -> None:
    db = StoryDB(story_root, "demo")
    db.ensure_story(title="Mem")
    mock_svc = MagicMock()
    mock_svc.ensure_team_collections.return_value = {"story": "team_demo__story"}
    mock_from.return_value = mock_svc
    from bot.story.memory import StoryMemoryService

    counts = StoryMemoryService(story_root, "demo").reindex_all()
    assert counts["story"] >= 1
    assert mock_svc.upsert.called
