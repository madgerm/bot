"""Git-Befehle via subprocess."""

from __future__ import annotations

import subprocess
from pathlib import Path

from bot.git_svc.config import load_git_config


class GitServiceError(Exception):
    pass


class GitService:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.cfg = load_git_config(self.root, team_id)
        self.repo_dir = (self.root / self.cfg.repo_path).resolve()

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> GitService:
        return cls(Path(root), team_id)

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        if not self.cfg.enabled:
            raise GitServiceError("Git ist deaktiviert")
        self.repo_dir.mkdir(parents=True, exist_ok=True)
        cmd = ["git", "-C", str(self.repo_dir), *args]
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=check,
                timeout=120,
            )
        except subprocess.CalledProcessError as exc:
            raise GitServiceError(exc.stderr or exc.stdout or str(exc)) from exc
        except FileNotFoundError as exc:
            raise GitServiceError("git nicht installiert") from exc

    def ensure_repo(self) -> None:
        if not (self.repo_dir / ".git").is_dir():
            self._run("init")
            self._run("config", "user.name", self.cfg.user_name)
            self._run("config", "user.email", self.cfg.user_email)

    def status(self) -> str:
        self.ensure_repo()
        result = self._run("status", "--short", "--branch")
        return result.stdout

    def log(self, limit: int = 10) -> str:
        self.ensure_repo()
        result = self._run("log", f"-{limit}", "--oneline")
        return result.stdout

    def add_all(self) -> str:
        self.ensure_repo()
        return self._run("add", "-A").stdout

    def commit(self, message: str) -> str:
        self.ensure_repo()
        self._run("add", "-A")
        result = self._run("commit", "-m", message)
        return result.stdout

    def push(self) -> str:
        self.ensure_repo()
        result = self._run(
            "push",
            self.cfg.remote_name,
            self.cfg.default_branch,
            check=False,
        )
        if result.returncode != 0:
            raise GitServiceError(result.stderr or "push fehlgeschlagen")
        return result.stdout

    def pull(self) -> str:
        self.ensure_repo()
        result = self._run("pull", self.cfg.remote_name, self.cfg.default_branch)
        return result.stdout
