"""Crawl4AI über Panel-Kanal (Satellit)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bot.channel.panel_rpc import execute_panel_rpc


def test_panel_rpc_crawl_fetch_single(tmp_path: Path) -> None:
    page = {"url": "https://example.com", "markdown": "# Hi", "title": "Ex"}
    with patch("bot.crawl.CrawlService") as cls:
        inst = cls.for_team.return_value
        inst.crawl_url.return_value = page
        out = execute_panel_rpc(
            tmp_path,
            "crawl.fetch",
            {
                "team_id": "demo",
                "url": "https://example.com",
                "single_url": True,
                "index_qdrant": False,
            },
        )
    assert out["pages"] == [page]
    assert out["indexed"] == 0
    inst.crawl_url.assert_called_once_with("https://example.com")


def test_panel_rpc_crawl_index_snapshots(tmp_path: Path) -> None:
    with patch("bot.qdrant.indexer.index_crawl_snapshots", return_value=3) as fn:
        out = execute_panel_rpc(
            tmp_path,
            "crawl.index_snapshots",
            {"team_id": "demo"},
        )
    assert out["count"] == 3
    fn.assert_called_once_with(tmp_path, "demo")


def test_cli_crawl_run_satellite_uses_channel(tmp_path: Path) -> None:
    from bot.cli_crawl import _cmd_run

    args = MagicMock()
    args.root = tmp_path
    args.team = "demo"
    args.index = True

    with (
        patch("bot.channel.satellite.is_satellite_root", return_value=True),
        patch("bot.cli_crawl._satellite_crawl_rpc") as rpc,
    ):
        rpc.return_value = {"summary": {"https://a.test": 2}, "indexed": 2}
        assert _cmd_run(args) == 0
        rpc.assert_called_once_with(
            tmp_path,
            "demo",
            "crawl.run_all",
            {"index_qdrant": True},
        )
