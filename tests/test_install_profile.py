"""Tests für scripts/apply-install-profile.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_CONFIG = Path(__file__).resolve().parents[1] / "config"
_EXAMPLES = (
    "system.panel-lan.example.json",
    "system.runner-channel.example.json",
    "team_hosts.channel.example.json",
)


@pytest.fixture
def project_with_examples(runtime_project: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    pyproject = repo_root / "pyproject.toml"
    if pyproject.is_file():
        (runtime_project / "pyproject.toml").write_text(
            pyproject.read_text(encoding="utf-8"), encoding="utf-8"
        )
    cfg = runtime_project / "config"
    for name in _EXAMPLES:
        src = _REPO_CONFIG / name
        if src.is_file():
            (cfg / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return runtime_project


def _run_profile(runtime_project: Path, profile: str, *extra: str) -> subprocess.CompletedProcess:
    script = Path(__file__).resolve().parents[1] / "scripts" / "apply-install-profile.py"
    return subprocess.run(
        [sys.executable, str(script), str(runtime_project), profile, *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def test_panel_merges_llm(project_with_examples: Path) -> None:
    r = _run_profile(project_with_examples, "panel")
    assert r.returncode == 0, r.stderr
    system = json.loads((project_with_examples / "config" / "system.json").read_text())
    assert system["system"]["llm"]["mode"] == "direct"
    assert system["system"]["llm"]["enabled"] is True


def test_runner_writes_team_api(project_with_examples: Path) -> None:
    r = _run_profile(project_with_examples, "runner")
    assert r.returncode == 0, r.stderr
    api = json.loads((project_with_examples / "config" / "team_api.json").read_text())
    assert api["token_env"] == "BOT_TEAM_API_TOKEN"
    assert "alpha" in api["teams"]
    system = json.loads((project_with_examples / "config" / "system.json").read_text())
    assert system["system"]["llm"]["mode"] == "channel"


def test_install_script_syntax() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "install-debian.sh"
    r = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_relay_profile_noop(project_with_examples: Path) -> None:
    before = (project_with_examples / "config" / "system.json").read_text()
    r = _run_profile(project_with_examples, "relay")
    assert r.returncode == 0
    assert (project_with_examples / "config" / "system.json").read_text() == before
