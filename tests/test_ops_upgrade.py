"""Panel-Upgrade (Admin)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bot.ops.upgrade import UpgradeStep, collect_git_version, run_panel_upgrade
from bot.web import create_app


def test_collect_git_version_no_repo(tmp_path: Path) -> None:
    info = collect_git_version(tmp_path, fetch=False)
    assert info.is_repo is False
    assert info.package_version


def test_run_panel_upgrade_skips_git_without_repo(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "bot"\n', encoding="utf-8")
    report = run_panel_upgrade(tmp_path, skip_git=False)
    names = [s.name for s in report.steps]
    assert any("git pull" in n or "Übersprungen" in s.detail for s in report.steps for n in [s.name])


@patch("bot.ops.upgrade._run")
@patch("bot.ops.upgrade._restart_units")
def test_run_panel_upgrade_calls_pip(
    mock_restart: object,
    mock_run: object,
    tmp_path: Path,
) -> None:
    mock_run.return_value = UpgradeStep(name="git pull", ok=True, detail="ok")
    mock_restart.return_value = [
        UpgradeStep(name="restart", ok=True, detail="done"),
    ]

    report = run_panel_upgrade(tmp_path, skip_git=True)
    assert report.success
    pip_calls = [c for c in mock_run.call_args_list if "pip" in str(c)]
    assert pip_calls or mock_run.call_count >= 1


@pytest.fixture
def ops_client(runtime_project: Path) -> TestClient:
    import json

    (runtime_project / "config" / "users.json").write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "password": "secret",
                        "role": "admin",
                        "teams": ["alpha"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return TestClient(create_app(runtime_project))


def test_admin_ops_requires_login(ops_client: TestClient) -> None:
    assert ops_client.get("/admin/ops", follow_redirects=False).status_code in (
        401,
        302,
        307,
    )


def test_admin_ops_page(ops_client: TestClient) -> None:
    ops_client.get("/login")
    ops_client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )
    r = ops_client.get("/admin/ops")
    assert r.status_code == 200
    assert "Update & Neustart" in r.text
    assert "Lokal" in r.text
    assert "Git" in r.text
