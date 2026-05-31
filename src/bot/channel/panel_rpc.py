"""RPC-Ausführung auf dem Panel (Qdrant, Medien, …)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bot.crawl.config import CrawlConfigError


def execute_panel_rpc(panel_root: Path, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "qdrant.search":
        from bot.qdrant.service import QdrantService

        team_id = str(payload["team_id"])
        collection = str(payload.get("collection", "project"))
        query = str(payload.get("query", ""))
        limit = int(payload.get("limit", 5))
        service = QdrantService.from_root(panel_root)
        hits = service.search(team_id, collection, query, limit=limit)
        return {"hits": hits}

    if kind == "qdrant.index_workspace":
        from bot.qdrant.indexer import index_team_workspace

        team_id = str(payload["team_id"])
        count = index_team_workspace(panel_root, team_id)
        return {"count": count}

    if kind == "media.generate_image":
        from bot.media import MediaService, MediaServiceError

        team_id = str(payload["team_id"])
        prompt = str(payload.get("prompt", ""))
        try:
            result = MediaService.for_team(panel_root, team_id).generate_image(prompt)
        except MediaServiceError as exc:
            raise RuntimeError(str(exc)) from exc
        return {"result": result}

    if kind == "crawl.fetch":
        from bot.crawl import CrawlService, CrawlServiceError

        team_id = str(payload["team_id"])
        url = str(payload.get("url", ""))
        max_pages = int(payload.get("max_pages", 10))
        index_qdrant = bool(payload.get("index_qdrant", False))
        try:
            svc = CrawlService.for_team(panel_root, team_id)
            if payload.get("single_url"):
                pages = [svc.crawl_url(url)]
            else:
                pages = svc.crawl_domain(url, max_pages)
            indexed = 0
            if index_qdrant and pages:
                indexed = svc.index_to_qdrant(pages)
        except (CrawlServiceError, CrawlConfigError) as exc:
            raise RuntimeError(str(exc)) from exc
        return {"pages": pages, "indexed": indexed}

    if kind == "crawl.run_all":
        from bot.crawl import CrawlService, CrawlServiceError

        team_id = str(payload["team_id"])
        index_qdrant = bool(payload.get("index_qdrant", True))
        try:
            svc = CrawlService.for_team(panel_root, team_id)
            results = svc.crawl_all_configured()
            indexed = 0
            if index_qdrant:
                for pages in results.values():
                    indexed += svc.index_to_qdrant(pages)
        except (CrawlServiceError, CrawlConfigError) as exc:
            raise RuntimeError(str(exc)) from exc
        summary = {domain: len(pages) for domain, pages in results.items()}
        return {"summary": summary, "indexed": indexed, "results": results}

    if kind == "crawl.index_snapshots":
        from bot.qdrant.indexer import index_crawl_snapshots

        team_id = str(payload["team_id"])
        count = index_crawl_snapshots(panel_root, team_id)
        return {"count": count}

    if kind == "browser.open":
        from bot.browser.service import BrowserService, BrowserServiceError

        team_id = str(payload["team_id"])
        url = str(payload.get("url", ""))
        max_chars = int(payload.get("max_chars", 8000))
        if not url.startswith(("http://", "https://")):
            raise ValueError("url muss mit http(s) beginnen")
        try:
            info = BrowserService.for_team(panel_root, team_id).open_url_with_body(
                url, max_chars=max_chars
            )
        except BrowserServiceError as exc:
            raise RuntimeError(str(exc)) from exc
        return {"info": info, "body_text": info.get("body_text", "")}

    if kind == "media.describe_image":
        from bot.media import MediaService, MediaServiceError

        team_id = str(payload["team_id"])
        path = Path(str(payload.get("path", "")))
        prompt = str(payload.get("prompt", "Beschreibe das Bild."))
        try:
            text = MediaService.for_team(panel_root, team_id).describe_image(path, prompt)
        except MediaServiceError as exc:
            raise RuntimeError(str(exc)) from exc
        return {"text": text}

    raise ValueError(f"Unbekannte Panel-RPC: {kind}")
