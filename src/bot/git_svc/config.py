"""teams/<id>/git.json"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class GitConfigError(Exception):
    pass


class GitConfig(BaseModel):
    enabled: bool = True
    repo_path: str = "data/{team_id}/workspace"
    remote_name: str = "origin"
    default_branch: str = "main"
    user_name: str = "bot"
    user_email: str = "bot@local"


def load_git_config(root: Path, team_id: str) -> GitConfig:
    path = root / "teams" / team_id / "git.json"
    if not path.is_file():
        return GitConfig(repo_path=f"data/{team_id}/workspace")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cfg = GitConfig.model_validate(data.get("git", data))
        if "{team_id}" in cfg.repo_path:
            cfg = cfg.model_copy(update={"repo_path": cfg.repo_path.format(team_id=team_id)})
        return cfg
    except Exception as exc:
        raise GitConfigError(str(exc)) from exc
