"""Einfacher Domain-Crawler (httpx) + Qdrant-Upsert."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

from bot.crawl.config import CrawlConfig, CrawlConfigError, load_crawl_config


class CrawlServiceError(Exception):
    pass


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class CrawlService:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.cfg = load_crawl_config(root, team_id)

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> CrawlService:
        return cls(Path(root), team_id)

    def crawl_domain(self, domain_url: str, max_pages: int | None = None) -> list[dict]:
        if not self.cfg or not self.cfg.enabled:
            raise CrawlServiceError("Crawl nicht konfiguriert")
        limit = max_pages or 10
        parsed = urlparse(domain_url)
        base_host = parsed.netloc
        seen: set[str] = set()
        queue = [domain_url if domain_url.startswith("http") else f"https://{domain_url}"]
        pages: list[dict] = []
        headers = {"User-Agent": self.cfg.user_agent}

        while queue and len(pages) < limit:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            try:
                resp = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
                resp.raise_for_status()
            except httpx.HTTPError:
                continue
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type.lower():
                continue
            text = _strip_html(resp.text)[:8000]
            page = {
                "url": str(resp.url),
                "title": _extract_title(resp.text),
                "text": text,
                "crawled_at": datetime.now(UTC).isoformat(),
                "content_hash": hashlib.sha256(text.encode()).hexdigest()[:16],
            }
            pages.append(page)
            for link in re.findall(r'href=["\']([^"\']+)["\']', resp.text, re.I):
                full = urljoin(str(resp.url), link)
                p = urlparse(full)
                if p.netloc == base_host and full not in seen:
                    queue.append(full)

        self._save_snapshots(pages)
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
            text = f"{page.get('title', '')}\n{page['text']}"
            service.upsert(self.team_id, collection, text, payload=page)
            count += 1
        return count

    def _save_snapshots(self, pages: list[dict]) -> None:
        if not self.cfg:
            return
        snap_dir = (self.root / self.cfg.snapshot_dir).resolve()
        snap_dir.mkdir(parents=True, exist_ok=True)
        for page in pages:
            name = hashlib.sha256(page["url"].encode()).hexdigest()[:12]
            path = snap_dir / f"{name}.json"
            path.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return m.group(1).strip() if m else ""
