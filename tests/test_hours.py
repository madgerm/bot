import json
from pathlib import Path

import pytest

from bot.config.models import TaskModelsConfig
from bot.hours.diff import compute_diff
from bot.hours.extract import extract_hours_from_markdown
from bot.hours.master import HoursMaster, save_master
from bot.hours.page_fetch import fetch_page_markdown
from bot.hours.service import HoursService, HoursServiceError
from bot.llm import ModelRouter, StubLlmClient
from bot.llm.factory import LlmStack


def _stub_stack() -> LlmStack:
    task_models = TaskModelsConfig.model_validate(
        {"task_models": {"review": {"default": "stub/review", "alternatives": []}}}
    )
    return LlmStack(router=ModelRouter(task_models), client=StubLlmClient())


def _setup_hours_team(root: Path, team: str = "alpha", *, website_type: str = "file") -> None:
    master = HoursMaster(
        weekly={
            "monday": {"open": "09:00", "close": "17:00", "closed": False},
            "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
        }
    )
    save_master(root, f"teams/{team}/hours.master.json", master)

    website_path = root / "teams" / team / "website_hours.json"
    website_path.write_text(
        json.dumps(
            {
                "hours": {
                    "weekly": {
                        "monday": {"open": "09:00", "close": "18:00", "closed": False},
                        "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    if website_type == "page":
        website_cfg = {"type": "page", "url": "", "crawl_engine": "httpx"}
        hours_body = {
            "master_file": f"teams/{team}/hours.master.json",
            "website": website_cfg,
            "publish": {"type": "file", "path": f"teams/{team}/website_hours.json"},
            "google_business": {"enabled": False},
        }
    else:
        hours_body = {
            "master_file": f"teams/{team}/hours.master.json",
            "website": {"type": "file", "path": f"teams/{team}/website_hours.json"},
            "google_business": {"enabled": False},
        }

    (root / "teams" / team / "hours.json").write_text(
        json.dumps({"hours": hours_body}), encoding="utf-8"
    )


def test_compute_diff_detects_change() -> None:
    diff = compute_diff(
        {"weekly": {"monday": {"close": "17:00"}}},
        {"weekly": {"monday": {"close": "18:00"}}},
    )
    assert diff["has_diff"] is True


def test_hours_check_approve_publish(runtime_project: Path) -> None:
    _setup_hours_team(runtime_project)
    service = HoursService.for_team(runtime_project, "alpha")
    record = service.check()
    assert record.status == "awaiting_approval"
    assert record.diff_json["has_diff"] is True

    with pytest.raises(HoursServiceError):
        service.publish(record.id)

    service.approve(record.id, "max")
    published = service.publish(record.id)
    assert published.status == "published"

    website = json.loads(
        (runtime_project / "teams" / "alpha" / "website_hours.json").read_text()
    )
    assert website["hours"]["weekly"]["monday"]["close"] == "17:00"


def test_extract_embedded_hours(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text(
        '<!-- hours-json: {"timezone":"Europe/Berlin","weekly":{"monday":{"open":"09:00","close":"18:00","closed":false}},"exceptions":[]} -->',
        encoding="utf-8",
    )
    from bot.hours.config import WebsitePageConfig

    md = fetch_page_markdown(WebsitePageConfig(url=page.as_uri(), crawl_engine="httpx"))
    hours, method = extract_hours_from_markdown(md["markdown"], _stub_stack())
    assert method == "embedded"
    assert hours["weekly"]["monday"]["close"] == "18:00"


def test_hours_page_agent_check(runtime_project: Path, tmp_path: Path) -> None:
    page = tmp_path / "kontakt.html"
    page.write_text(
        "<html><body><p>Montag 09:00-18:00</p><p>Dienstag 09:00-17:00</p></body></html>",
        encoding="utf-8",
    )
    _setup_hours_team(runtime_project, website_type="page")
    data = json.loads((runtime_project / "teams" / "alpha" / "hours.json").read_text())
    data["hours"]["website"]["url"] = page.as_uri()
    (runtime_project / "teams" / "alpha" / "hours.json").write_text(
        json.dumps(data), encoding="utf-8"
    )

    record = HoursService.for_team(runtime_project, "alpha").check(llm_stack=_stub_stack())
    assert record.diff_json["check_mode"] == "agent_page"
    assert record.diff_json["has_diff"] is True


def test_hours_checker_agent(runtime_project: Path, tmp_path: Path) -> None:
    page = tmp_path / "kontakt.html"
    page.write_text(
        '<!-- hours-json: {"timezone":"Europe/Berlin","weekly":{"monday":{"open":"09:00","close":"17:00","closed":false}},"exceptions":[]} -->',
        encoding="utf-8",
    )
    _setup_hours_team(runtime_project, website_type="page")
    data = json.loads((runtime_project / "teams" / "alpha" / "hours.json").read_text())
    data["hours"]["website"]["url"] = page.as_uri()
    (runtime_project / "teams" / "alpha" / "hours.json").write_text(
        json.dumps(data), encoding="utf-8"
    )

    hc = runtime_project / "teams" / "alpha" / "agents" / "hours-checker"
    hc.mkdir(parents=True, exist_ok=True)
    (hc / "inbox").mkdir(exist_ok=True)
    (hc / "outbox").mkdir(exist_ok=True)
    (hc / "agent.json").write_text(
        json.dumps(
            {
                "agent": {
                    "id": "hours-checker",
                    "role": "hours_checker",
                    "enabled": True,
                    "interval_seconds": 1,
                }
            }
        ),
        encoding="utf-8",
    )

    from bot.messages import MessageService
    from bot.runtime.supervisor import Supervisor

    MessageService(runtime_project).send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="hours-checker",
        subject="Prüfen",
        content="Website prüfen",
        type="hours_check",
    )
    sup = Supervisor(runtime_project)
    sup.start(team_ids=["alpha"])
    import time

    time.sleep(2.5)
    sup.stop()

    diffs = HoursService.for_team(runtime_project, "alpha").store.list_diffs(limit=3)
    assert len(diffs) >= 1
