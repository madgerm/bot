"""Workspace- und Crawl-Snapshots in Qdrant indexieren."""

from __future__ import annotations

import uuid
from pathlib import Path

from bot.files.service import FileService
from bot.qdrant.service import QdrantService, QdrantServiceError

def _is_indexable(path: Path) -> bool:
    return path.suffix.lower() in _INDEXABLE


def _stable_point_id(namespace: str, key: str) -> str:
    """Deterministische UUID für Qdrant (Upsert/Update derselben Datei)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{namespace}/{key}"))


_INDEXABLE = {
    ".py",
    ".md",
    ".json",
    ".txt",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".yaml",
    ".yml",
    ".toml",
    ".sql",
    ".sh",
    ".rst",
}


def index_team_workspace(
    root: Path | str,
    team_id: str,
    *,
    max_file_bytes: int = 80_000,
) -> int:
    """Indexiert Textdateien aus data/<team>/workspace nach team_*__project."""
    root_path = Path(root).resolve()
    try:
        qdrant = QdrantService.from_root(root_path)
    except QdrantServiceError:
        return 0
    qdrant.ensure_team_collections(team_id)
    fs = FileService.for_team(root_path, team_id)
    workspace = fs.workspace
    if not workspace.is_dir():
        return 0

    count = 0
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _INDEXABLE:
            continue
        if path.stat().st_size > max_file_bytes:
            continue
        rel = str(path.relative_to(workspace))
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not text.strip():
            continue
        qdrant.upsert(
            team_id,
            "project",
            text=text,
            payload={"path": rel, "source": "workspace"},
            point_id=_stable_point_id("workspace", rel),
        )
        count += 1
    return count


def workspace_snapshot(root: Path | str, team_id: str) -> dict[str, float]:
    """mtime-Snapshot aller indexierbaren Workspace-Dateien (für Watch)."""
    root_path = Path(root).resolve()
    fs = FileService.for_team(root_path, team_id)
    workspace = fs.workspace
    if not workspace.is_dir():
        return {}
    snap: dict[str, float] = {}
    for path in workspace.rglob("*"):
        if path.is_file() and _is_indexable(path):
            try:
                rel = str(path.relative_to(workspace))
                snap[rel] = path.stat().st_mtime
            except OSError:
                continue
    return snap


def index_workspace_file(
    root: Path | str,
    team_id: str,
    rel_path: str,
    *,
    max_file_bytes: int = 80_000,
) -> bool:
    """Hook: eine geänderte Datei in team_*__project upserten."""
    root_path = Path(root).resolve()
    try:
        qdrant = QdrantService.from_root(root_path)
    except QdrantServiceError:
        return False
    qdrant.ensure_team_collections(team_id)
    fs = FileService.for_team(root_path, team_id)
    try:
        target = fs._resolve(rel_path)
    except Exception:
        return False
    if not target.is_file() or not _is_indexable(target):
        return False
    if target.stat().st_size > max_file_bytes:
        return False
    text = target.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return False
    rel = str(target.relative_to(fs.workspace))
    qdrant.upsert(
        team_id,
        "project",
        text=text,
        payload={"path": rel, "source": "workspace"},
        point_id=_stable_point_id("workspace", rel),
    )
    return True


def index_crawl_snapshots(root: Path | str, team_id: str) -> int:
    """Indexiert gespeicherte Crawl-Markdown-Dateien nach team_*__background."""
    from bot.crawl.service import CrawlService

    root_path = Path(root).resolve()
    try:
        qdrant = QdrantService.from_root(root_path)
    except QdrantServiceError:
        return 0
    qdrant.ensure_team_collections(team_id)
    crawl = CrawlService.for_team(root_path, team_id)
    snap_dir = crawl.snapshot_dir
    if not snap_dir.is_dir():
        return 0
    count = 0
    for md in snap_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue
        rel = str(md.relative_to(snap_dir))
        qdrant.upsert(
            team_id,
            "background",
            text=text[:80_000] if len(text) > 80_000 else text,
            payload={"path": rel, "source": "crawl"},
            point_id=_stable_point_id("crawl", rel),
        )
        count += 1
    return count
