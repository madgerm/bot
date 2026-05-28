"""teams/<id>/crawl.json"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class CrawlDomain(BaseModel):
    url: str
    max_pages: int = Field(default=10, ge=1, le=500)
    enabled: bool = True


class CrawlConfig(BaseModel):
    enabled: bool = True
    domains: list[CrawlDomain] = Field(default_factory=list)
    snapshot_dir: str = "data/{team_id}/crawl"
    qdrant_collection: str = "web"
    prune_threshold: float = Field(default=0.48, ge=0.0, le=1.0)
    """Crawl4AI PruningContentFilter — höher = aggressiveres Entfernen von Menüs/Nav."""


class CrawlConfigError(Exception):
    pass


def load_crawl_config(root: Path, team_id: str) -> CrawlConfig | None:
    path = root / "teams" / team_id / "crawl.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    cfg = CrawlConfig.model_validate(data.get("crawl", data))
    if "{team_id}" in cfg.snapshot_dir:
        cfg = cfg.model_copy(update={"snapshot_dir": cfg.snapshot_dir.format(team_id=team_id)})
    return cfg
