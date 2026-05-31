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
class GitVersionInfo:
    """Vergleich: was lokal läuft vs. was Git (Remote) anbietet."""

    is_repo: bool
    package_version: str
    branch: str | None = None
    local_short: str | None = None
    local_subject: str | None = None
    remote_ref: str | None = None
    remote_short: str | None = None
    commits_ahead: int = 0
    commits_behind: int = 0
    update_available: bool = False
    fetch_ran: bool = False
    error: str | None = None


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


def _git_line(cmd: list[str], *, cwd: Path, timeout: int = 30) -> str | None:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            return None
        return (proc.stdout or "").strip() or None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _package_version() -> str:
    try:
        from importlib.metadata import version

        return version("bot")
    except Exception:
        return "0.1.0"


def collect_git_version(root: Path | str, *, fetch: bool = True) -> GitVersionInfo:
    """Lokal installierter Stand vs. Remote-Branch (nach optionalem git fetch)."""
    root_path = Path(root).resolve()
    pkg = _package_version()
    if not (root_path / ".git").is_dir():
        return GitVersionInfo(
            is_repo=False,
            package_version=pkg,
            error="Kein Git-Repository — nur manuelles Kopieren/ pip install möglich.",
        )

    info = GitVersionInfo(is_repo=True, package_version=pkg)
    if fetch:
        fetch_step = _run(["git", "fetch", "--quiet"], cwd=root_path, timeout=90)
        info.fetch_ran = True
        if not fetch_step.ok:
            info.error = f"git fetch: {fetch_step.detail[:200]}"

    info.branch = _git_line(["git", "branch", "--show-current"], cwd=root_path)
    info.local_short = _git_line(["git", "rev-parse", "--short", "HEAD"], cwd=root_path)
    info.local_subject = _git_line(
        ["git", "log", "-1", "--format=%s"],
        cwd=root_path,
    )

    upstream = _git_line(["git", "rev-parse", "--abbrev-ref", "@{upstream}"], cwd=root_path)
    if not upstream:
        for fallback in ("origin/main", "origin/master"):
            if _git_line(["git", "rev-parse", "--verify", fallback], cwd=root_path):
                upstream = fallback
                break
    info.remote_ref = upstream
    if upstream:
        info.remote_short = _git_line(["git", "rev-parse", "--short", upstream], cwd=root_path)
        counts = _git_line(
            ["git", "rev-list", "--left-right", "--count", f"HEAD...{upstream}"],
            cwd=root_path,
        )
        if counts:
            parts = counts.split()
            if len(parts) == 2:
                info.commits_ahead = int(parts[0])
                info.commits_behind = int(parts[1])
                info.update_available = info.commits_behind > 0

    return info


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
