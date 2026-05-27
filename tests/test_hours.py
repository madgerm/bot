import json
from pathlib import Path

import pytest

from bot.hours.diff import compute_diff
from bot.hours.master import HoursMaster, save_master
from bot.hours.service import HoursService, HoursServiceError


def _setup_hours_team(root: Path, team: str = "alpha") -> None:
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

    hours_json = root / "teams" / team / "hours.json"
    hours_json.write_text(
        json.dumps(
            {
                "hours": {
                    "master_file": f"teams/{team}/hours.master.json",
                    "website": {"type": "file", "path": f"teams/{team}/website_hours.json"},
                    "google_business": {"enabled": False},
                }
            }
        ),
        encoding="utf-8",
    )


def test_compute_diff_detects_change() -> None:
    diff = compute_diff(
        {"weekly": {"monday": {"close": "17:00"}}},
        {"weekly": {"monday": {"close": "18:00"}}},
    )
    assert diff["has_diff"] is True
    assert diff["change_count"] >= 1


def test_hours_check_approve_publish(runtime_project: Path) -> None:
    _setup_hours_team(runtime_project)
    service = HoursService.for_team(runtime_project, "alpha")
    record = service.check()
    assert record.status == "awaiting_approval"
    assert record.diff_json["has_diff"] is True

    with pytest.raises(HoursServiceError):
        service.publish(record.id)

    approved = service.approve(record.id, "max")
    assert approved.status == "approved"

    published = service.publish(record.id)
    assert published.status == "published"

    website = json.loads(
        (runtime_project / "teams" / "alpha" / "website_hours.json").read_text()
    )
    assert website["hours"]["weekly"]["monday"]["close"] == "17:00"
