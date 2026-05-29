import pytest

from bot.story.db import StoryDB, StoryDBError


def test_scene_version_conflict(runtime_project) -> None:
    db = StoryDB(runtime_project, "alpha")
    db.ensure_story(title="T")
    ch = db.add_chapter()
    info = db.add_scene(ch, content="v1")
    db.update_scene(ch, info.scene_id, "v2", expected_version=1)
    with pytest.raises(StoryDBError, match="Versionskonflikt"):
        db.update_scene(ch, info.scene_id, "v3", expected_version=1)
