"""CLI: Domain-Crawl."""

from __future__ import annotations

import argparse
import json
import sys


def register_crawl_commands(sub, add_root) -> None:
    p = sub.add_parser("crawl", help="Domain-Crawl + Qdrant-Index")
    add_root(p)
    crawl_sub = p.add_subparsers(dest="crawl_command", required=True)

    run = crawl_sub.add_parser("run", help="Alle konfigurierten Domains crawlen")
    add_root(run)
    run.add_argument("--team", required=True)
    run.add_argument("--index", action="store_true", help="In Qdrant indexieren")
    run.set_defaults(func=_cmd_run)

    one = crawl_sub.add_parser("fetch", help="Eine URL crawlen")
    add_root(one)
    one.add_argument("--team", required=True)
    one.add_argument("--url", required=True)
    one.add_argument("--max-pages", type=int, default=10)
    one.add_argument("--index", action="store_true")
    one.set_defaults(func=_cmd_fetch)


def _satellite_crawl_rpc(
    root, team: str, kind: str, payload: dict, *, timeout: float = 3600.0
) -> dict:
    from bot.channel.satellite import channel_rpc

    return channel_rpc(root, kind, {"team_id": team, **payload}, timeout_seconds=timeout)


def _cmd_run(args: argparse.Namespace) -> int:
    from bot.channel.satellite import is_satellite_root
    from bot.crawl import CrawlService

    try:
        if is_satellite_root(args.root):
            data = _satellite_crawl_rpc(
                args.root,
                args.team,
                "crawl.run_all",
                {"index_qdrant": args.index},
            )
            print(json.dumps(data.get("summary", {}), indent=2))
            if args.index:
                print(f"Qdrant indexiert: {data.get('indexed', 0)}", file=sys.stderr)
            return 0
        svc = CrawlService.for_team(args.root, args.team)
        results = svc.crawl_all_configured()
        if args.index:
            for pages in results.values():
                svc.index_to_qdrant(pages)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({k: len(v) for k, v in results.items()}, indent=2))
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    from bot.channel.satellite import is_satellite_root
    from bot.crawl import CrawlService

    try:
        if is_satellite_root(args.root):
            data = _satellite_crawl_rpc(
                args.root,
                args.team,
                "crawl.fetch",
                {
                    "url": args.url,
                    "max_pages": args.max_pages,
                    "index_qdrant": args.index,
                    "single_url": False,
                },
            )
            pages = data.get("pages", [])
            print(json.dumps(pages, indent=2, ensure_ascii=False))
            return 0
        svc = CrawlService.for_team(args.root, args.team)
        pages = svc.crawl_domain(args.url, args.max_pages)
        if args.index:
            svc.index_to_qdrant(pages)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(pages, indent=2, ensure_ascii=False))
    return 0
