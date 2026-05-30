import json
from pathlib import Path

import pytest

from bot.story.db import StoryDB
from bot.story.export import export_epub, export_markdown_zip, export_pdf


@pytest.fixture
def story_team(tmp_path: Path) -> Path:
    db = StoryDB(tmp_path, "novel")
    db.ensure_story(title="Testroman", genre="Sci-Fi")
    ch = db.add_chapter()
    db.add_scene(ch, title="Eröffnung", content="Es war einmal…")
    return tmp_path


def test_export_mdzip(story_team: Path) -> None:
    db = StoryDB(story_team, "novel")
    out = story_team / "out.zip"
    export_markdown_zip(db, out)
    assert out.is_file()
    assert out.stat().st_size > 0


def test_export_epub(story_team: Path) -> None:
    db = StoryDB(story_team, "novel")
    out = story_team / "book.epub"
    export_epub(db, out)
    assert out.is_file()


def test_export_pdf(story_team: Path) -> None:
    db = StoryDB(story_team, "novel")
    out = story_team / "book.pdf"
    export_pdf(db, out)
    assert out.is_file()
