import json
from pathlib import Path

import pytest

from bot.config.loader import discover_teams
from bot.runtime.pipeline import resolve_pipeline


@pytest.fixture
def preset_project(tmp_path: Path) -> Path:
    for team_id, preset, agents in (
        (
            "coding",
            "coding",
            [
                ("orchestrator", "orchestrator"),
                ("coder", "coder"),
                ("tester", "tester"),
                ("doku", "documenter"),
            ],
        ),
        (
            "story",
            "story",
            [
                ("orchestrator", "orchestrator"),
                ("drehbuch-autor", "story_writer"),
                ("logik-pruefer", "reviewer"),
                ("literatur-review", "story_reviewer"),
            ],
        ),
    ):
        tdir = tmp_path / "teams" / team_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "team.json").write_text(
            json.dumps(
                {
                    "team": {
                        "id": team_id,
                        "name": team_id,
                        "orchestrator_id": "orchestrator",
                        "preset": preset,
                    }
                }
            ),
            encoding="utf-8",
        )
        for aid, role in agents:
            adir = tdir / "agents" / aid
            adir.mkdir(parents=True)
            (adir / "agent.json").write_text(
                json.dumps({"agent": {"id": aid, "role": role, "enabled": True}}),
                encoding="utf-8",
            )
    return tmp_path


def test_coding_pipeline(preset_project: Path) -> None:
    teams = discover_teams(preset_project / "teams")
    pipe = resolve_pipeline(teams["coding"])
    assert pipe.execute_id == "coder"
    assert pipe.review_id == "tester"
    assert pipe.document_id == "doku"


def test_story_pipeline(preset_project: Path) -> None:
    teams = discover_teams(preset_project / "teams")
    pipe = resolve_pipeline(teams["story"])
    assert pipe.execute_id == "drehbuch-autor"
    assert pipe.review_id == "logik-pruefer"
