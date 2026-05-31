"""Prüffragen-Workflow (Fragen-Team)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.config.writers.team_admin import load_team_config, save_team_general
from bot.verification.parse import parse_questions_json, parse_verdict_json
from bot.verification.router import route_verification_check
from bot.verification.store import VerificationStore
from bot.verification.workflow import (
    apply_review_and_continue,
    is_verification_team,
    store_questions_from_llm,
    team_workflow,
)


@pytest.fixture
def verification_team(runtime_project: Path) -> Path:
    save_team_general(
        runtime_project,
        "alpha",
        actor="test",
        name="Alpha QA",
        enabled=True,
        preset="generic",
        orchestrator_id="orchestrator",
        workflow="verification",
    )
    return runtime_project


def test_parse_questions_json() -> None:
    text = """```json
[
  {"seq": 1, "title": "Login", "question": "Gibt es Login?", "check_method": "browser"}
]
```"""
    items = parse_questions_json(text)
    assert len(items) == 1
    assert items[0]["question"] == "Gibt es Login?"
    assert items[0]["check_method"] == "browser"


def test_parse_verdict_json() -> None:
    v = parse_verdict_json(
        '{"verdict": "nein", "reasons": "Session fehlt", "gaps": ["Route"], "fix_needed": true}'
    )
    assert v["verdict"] == "nein"
    assert v["fix_needed"] is True


def test_verification_store_and_files(verification_team: Path) -> None:
    created = store_questions_from_llm(
        verification_team,
        "alpha",
        '[{"seq":1,"title":"Start","question":"Startseite?","check_method":"browser"}]',
    )
    assert len(created) == 1
    store = VerificationStore(verification_team, "alpha")
    assert store.get_question(created[0].id) is not None
    assert (verification_team / "teams" / "alpha" / "verification" / "state.json").is_file()


def test_route_browser(verification_team: Path) -> None:
    route = route_verification_check(verification_team, "alpha", "browser")
    assert route.check_method == "browser"
    assert route.agent_id == "worker-exec"


def test_team_workflow_flag(verification_team: Path) -> None:
    assert team_workflow(verification_team, "alpha") == "verification"
    assert is_verification_team(verification_team, "alpha") is True
    cfg = load_team_config(verification_team, "alpha")
    assert cfg.team.workflow == "verification"


def test_apply_review_ja_starts_next(verification_team: Path) -> None:
    from bot.messages import open_message_service

    qs = store_questions_from_llm(
        verification_team,
        "alpha",
        '[{"seq":1,"title":"A","question":"Q1?","check_method":"code"},'
        '{"seq":2,"title":"B","question":"Q2?","check_method":"code"}]',
    )
    q1 = qs[0]
    apply_review_and_continue(
        verification_team,
        "alpha",
        "orchestrator",
        "worker-exec",
        "worker-review",
        q1.id,
        '{"verdict":"ja","reasons":"ok","gaps":[],"fix_needed":false}',
    )
    store = VerificationStore(verification_team, "alpha")
    assert store.get_question(q1.id).status == "passed"
    inbox = open_message_service(verification_team).list_inbox(
        "alpha", "worker-exec"
    )
    assert any(m.type == "verify.check" for m in inbox)


def test_apply_review_nein_enqueues_fix(verification_team: Path) -> None:
    qs = store_questions_from_llm(
        verification_team,
        "alpha",
        '[{"seq":1,"title":"Login","question":"Login?","check_method":"code"}]',
    )
    apply_review_and_continue(
        verification_team,
        "alpha",
        "orchestrator",
        "worker-exec",
        "worker-review",
        qs[0].id,
        '{"verdict":"nein","reasons":"fehlt","gaps":["Route"],"fix_needed":true,"next_fix":"Login bauen"}',
    )
    store = VerificationStore(verification_team, "alpha")
    assert store.get_question(qs[0].id).status == "fixing"
    from bot.messages import open_message_service

    inbox = open_message_service(verification_team).list_inbox("alpha", "worker-exec")
    assert any(m.type == "verify.fix" for m in inbox)
