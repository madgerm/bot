"""Domain-Crawl mit Crawl4AI — sauberes Markdown (fit_markdown, ohne Menü/Boilerplate)."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from bot.crawl.config import CrawlConfig, CrawlConfigError, load_crawl_config


class CrawlServiceError(Exception):
    pass


def _markdown_from_result(result: Any) -> str:
    """Bevorzugt gefiltertes Markdown (ohne Navigation/Menüs)."""
    md = getattr(result, "markdown", None)
    if md is None:
        return ""
    if hasattr(md, "fit_markdown") and md.fit_markdown:
        return str(md.fit_markdown)
    if hasattr(md, "raw_markdown") and md.raw_markdown:
        return str(md.raw_markdown)
    if isinstance(md, str):
        return md
    return str(md)


async def _crawl_url_crawl4ai(url: str, *, prune_threshold: float = 0.48) -> dict[str, Any]:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    except ImportError as exc:
        raise CrawlServiceError(
            "crawl4ai nicht installiert — pip install -e '.[crawl]' und "
            "playwright install chromium"
        ) from exc

    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(
            threshold=prune_threshold,
            threshold_type="fixed",
            min_word_threshold=5,
        )
    )
    run_config = CrawlerRunConfig(markdown_generator=md_generator)
    browser_config = BrowserConfig(headless=True, verbose=False)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    if not getattr(result, "success", True):
        err = getattr(result, "error_message", "Crawl fehlgeschlagen")
        raise CrawlServiceError(str(err))

    markdown = _markdown_from_result(result).strip()
    title = ""
    meta = getattr(result, "metadata", None) or {}
    if isinstance(meta, dict):
        title = meta.get("title", "") or ""
    return {
        "url": str(getattr(result, "url", url) or url),
        "title": title,
        "markdown": markdown,
        "crawled_at": datetime.now(UTC).isoformat(),
        "content_hash": hashlib.sha256(markdown.encode()).hexdigest()[:16],
        "engine": "crawl4ai",
    }


def crawl_url_sync(url: str, *, prune_threshold: float = 0.48) -> dict[str, Any]:
    return asyncio.run(_crawl_url_crawl4ai(url, prune_threshold=prune_threshold))


class CrawlService:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.cfg = load_crawl_config(root, team_id)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> CrawlService:
        return cls(Path(root), team_id)

    @property
    def snapshot_dir(self) -> Path:
        if not self.cfg:
            return self.root / "data" / self.team_id / "crawl"
        return (self.root / self.cfg.snapshot_dir).resolve()

    def crawl_url(self, url: str) -> dict[str, Any]:
        threshold = 0.48
        if self.cfg and hasattr(self.cfg, "prune_threshold"):
            threshold = getattr(self.cfg, "prune_threshold", 0.48)
        page = crawl_url_sync(url, prune_threshold=threshold)
        self._save_markdown_snapshot(page)
        return page

    def crawl_domain(self, domain_url: str, max_pages: int | None = None) -> list[dict]:
        if not self.cfg or not self.cfg.enabled:
            raise CrawlServiceError("Crawl nicht konfiguriert")
        limit = max_pages or 10
        start = domain_url if domain_url.startswith("http") else f"https://{domain_url}"
        pages: list[dict] = []
        seen: set[str] = set()
        queue = [start]

        while queue and len(pages) < limit:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                page = self.crawl_url(url)
                pages.append(page)
            except CrawlServiceError:
                continue
            base_host = urlparse(start).netloc
            for link in self._extract_links_from_markdown(page.get("markdown", ""), url):
                p = urlparse(link)
                if p.netloc == base_host and link not in seen:
                    queue.append(link)

        return pages

    def crawl_all_configured(self) -> dict[str, list[dict]]:
        if not self.cfg:
            raise CrawlConfigError("crawl.json fehlt")
        results: dict[str, list[dict]] = {}
        for domain in self.cfg.domains:
            if domain.enabled:
                results[domain.url] = self.crawl_domain(domain.url, domain.max_pages)
        return results

    def index_to_qdrant(self, pages: list[dict]) -> int:
        from bot.qdrant import QdrantService, QdrantServiceError

        try:
            service = QdrantService.from_root(self.root)
        except QdrantServiceError as exc:
            raise CrawlServiceError(str(exc)) from exc
        collection = self.cfg.qdrant_collection if self.cfg else "web"
        count = 0
        for page in pages:
            text = page.get("markdown") or ""
            if not text.strip():
                continue
            title = page.get("title", "")
            payload = {k: v for k, v in page.items() if k != "markdown"}
            service.upsert(
                self.team_id,
                collection,
                f"{title}\n{text}" if title else text,
                payload=payload,
            )
            count += 1
        return count

    def _save_markdown_snapshot(self, page: dict[str, Any]) -> Path:
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        url = page["url"]
        host = urlparse(url).netloc.replace(".", "_")
        name = hashlib.sha256(url.encode()).hexdigest()[:12]
        host_dir = self.snapshot_dir / host
        host_dir.mkdir(parents=True, exist_ok=True)
        md_path = host_dir / f"{name}.md"
        meta_path = host_dir / f"{name}.meta.json"
        frontmatter = (
            f"---\nurl: {page['url']}\n"
            f"title: {json.dumps(page.get('title', ''), ensure_ascii=False)}\n"
            f"crawled_at: {page['crawled_at']}\n"
            f"content_hash: {page['content_hash']}\n"
            f"engine: crawl4ai\n---\n\n"
        )
        md_path.write_text(frontmatter + page.get("markdown", ""), encoding="utf-8")
        meta_path.write_text(
            json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return md_path

    @staticmethod
    def _extract_links_from_markdown(markdown: str, base_url: str) -> list[str]:
        import re
        from urllib.parse import urljoin

        links: list[str] = []
        for m in re.finditer(r"\]\((https?://[^)]+)\)", markdown):
            links.append(m.group(1))
        for m in re.finditer(r"https?://[^\s\])<>\"']+", markdown):
            links.append(m.group(0).rstrip(".,;"))
        return list({urljoin(base_url, u) for u in links})
