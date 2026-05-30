"""Collection-Namenskonvention pro Team."""

from __future__ import annotations

import json
import re
from pathlib import Path

COLLECTION_SUFFIXES = ("project", "background", "web")


def team_slug(team_id: str) -> str:
    slug = re.sub(r"[^a-z0-9_]", "_", team_id.lower())
    return slug.strip("_") or "team"


def collection_name(team_id: str, suffix: str) -> str:
    if suffix not in COLLECTION_SUFFIXES:
        raise ValueError(f"Unbekanntes Collection-Suffix: {suffix}")
    return f"team_{team_slug(team_id)}__{suffix}"


def all_collections(team_id: str) -> dict[str, str]:
    return {suffix: collection_name(team_id, suffix) for suffix in COLLECTION_SUFFIXES}


def registry_path(root: Path, team_id: str) -> Path:
    return root / "data" / team_id / "qdrant_registry.json"


def save_registry(root: Path, team_id: str) -> dict[str, str]:
    path = registry_path(root, team_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    names = all_collections(team_id)
    path.write_text(json.dumps({"collections": names}, indent=2) + "\n", encoding="utf-8")
    return names


def load_registry(root: Path, team_id: str) -> dict[str, str]:
    path = registry_path(root, team_id)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return dict(data.get("collections", {}))
    return save_registry(root, team_id)
