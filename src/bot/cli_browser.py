"""CLI: Playwright (`bot browser`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_browser_open(args: argparse.Namespace) -> int:
    from bot.browser import BrowserService, BrowserServiceError

    try:
        service = BrowserService.for_team(args.root, args.team)
        info = service.connect()
        result = service.open_url(args.url)
        if args.screenshot:
            shot = service.screenshot(args.screenshot)
            result["screenshot"] = str(shot)
        service.close()
    except BrowserServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"session": info.__dict__, **result}, indent=2, ensure_ascii=False))
    return 0


def cmd_browser_config(args: argparse.Namespace) -> int:
    from bot.browser.config import resolve_playwright_config

    cfg = resolve_playwright_config(args.root, args.team)
    print(json.dumps(cfg.model_dump(), indent=2, ensure_ascii=False))
    return 0


def register_browser_commands(sub, add_root) -> None:
    browser = sub.add_parser("browser", help="Playwright-Browser")
    browser_sub = browser.add_subparsers(dest="browser_command", required=True)

    open_cmd = browser_sub.add_parser("open", help="URL im Browser öffnen")
    add_root(open_cmd)
    open_cmd.add_argument("--team", required=True)
    open_cmd.add_argument("--url", required=True)
    open_cmd.add_argument("--screenshot", type=Path, default=None)
    open_cmd.set_defaults(func=cmd_browser_open)

    cfg = browser_sub.add_parser("config", help="Aufgelöste Playwright-Config")
    add_root(cfg)
    cfg.add_argument("--team", required=True)
    cfg.set_defaults(func=cmd_browser_config)
