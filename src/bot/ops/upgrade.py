"""Code-Update und Dienst-Neustart vom Web-Panel (Admin)."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

USER_UNITS = ("bot-web-panel.service", "bot-team-runner.service")
SYSTEM_UNITS = USER_UNITS


@dataclass
class UpgradeStep:
    name: str
    ok: bool
    detail: str


@dataclass
class UpgradeReport:
    steps: list[UpgradeStep] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return all(s.ok for s in self.steps)


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 300) -> UpgradeStep:
    name = cmd[0] if cmd else "?"
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ},
        )
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        detail = out or err or f"exit {proc.returncode}"
        if len(detail) > 4000:
            detail = detail[:4000] + "\n…"
        return UpgradeStep(name=" ".join(cmd[:3]), ok=proc.returncode == 0, detail=detail)
    except subprocess.TimeoutExpired:
        return UpgradeStep(name=" ".join(cmd[:3]), ok=False, detail=f"Timeout nach {timeout}s")
    except OSError as exc:
        return UpgradeStep(name=" ".join(cmd[:3]), ok=False, detail=str(exc))


def _unit_is_active(unit: str, *, user: bool) -> bool:
    cmd = ["systemctl", "--user", "is-active", unit] if user else ["systemctl", "is-active", unit]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0
    except OSError:
        return False


def _restart_units(root: Path) -> list[UpgradeStep]:
    steps: list[UpgradeStep] = []
    user_units = [u for u in USER_UNITS if _unit_is_active(u, user=True)]
    system_units = [u for u in SYSTEM_UNITS if _unit_is_active(u, user=False)]

    if user_units:
        steps.append(_run(["systemctl", "--user", "daemon-reload"]))
        for unit in user_units:
            steps.append(_run(["systemctl", "--user", "restart", unit]))
    elif system_units:
        steps.append(_run(["systemctl", "daemon-reload"]))
        for unit in system_units:
            steps.append(_run(["systemctl", "restart", unit]))
    else:
        steps.append(
            UpgradeStep(
                name="dienste",
                ok=True,
                detail=(
                    "Keine systemd-Units bot-web-panel / bot-team-runner aktiv. "
                    "Bitte manuell neu starten: bot up oder bot web && bot run"
                ),
            )
        )
    return steps


def run_panel_upgrade(root: Path | str, *, skip_git: bool = False) -> UpgradeReport:
    """git pull (optional), pip install -e ., systemd-Neustart."""
    root_path = Path(root).resolve()
    report = UpgradeReport()

    if not skip_git and (root_path / ".git").is_dir():
        report.steps.append(
            _run(["git", "pull", "--ff-only"], cwd=root_path, timeout=180)
        )
    elif not skip_git:
        report.steps.append(
            UpgradeStep(
                name="git pull",
                ok=True,
                detail="Übersprungen — kein Git-Repository unter BOT_ROOT.",
            )
        )

    report.steps.append(
        _run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            cwd=root_path,
            timeout=600,
        )
    )
    report.steps.extend(_restart_units(root_path))
    return report
