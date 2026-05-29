"""Workspace- und Crawl-Snapshots in Qdrant indexieren."""

from __future__ import annotations

from pathlib import Path

from bot.files.service import FileService
from bot.qdrant.service import QdrantService, QdrantServiceError

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
            text,
            payload={"path": rel, "source": "workspace"},
            point_id=f"ws:{rel}",
        )
        count += 1
    return count


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
            text[:80_000] if len(text) > 80_000 else text,
            payload={"path": rel, "source": "crawl"},
            point_id=f"crawl:{rel}",
        )
        count += 1
    return count
