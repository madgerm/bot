"""Einstiegspunkt für die CLI (`bot` oder `python -m bot`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bot import __version__
from bot.cli_browser import register_browser_commands
from bot.cli_chat import register_chat_commands
from bot.cli_hours import register_hours_commands
from bot.cli_mail import register_mail_commands
from bot.cli_llm import register_llm_commands
from bot.cli_msg import register_msg_commands
from bot.cli_qdrant import register_qdrant_commands
from bot.cli_run import register_run_commands
from bot.cli_team import register_team_commands
from bot.cli_web import register_web_commands
from bot.config import ConfigLoadError, ConfigStore, load_runtime_config


def _default_root() -> Path:
    return Path.cwd()


def _cmd_config_validate(args: argparse.Namespace) -> int:
    try:
        config = load_runtime_config(args.root)
    except ConfigLoadError as exc:
        print(f"Konfiguration ungültig: {exc}", file=sys.stderr)
        return 1

    team_count = len(config.teams)
    agent_count = sum(len(bundle.agents) for bundle in config.teams.values())
    print(f"OK — System '{config.system.system.name}', {team_count} Team(s), {agent_count} Agent(s)")
    return 0


def _cmd_config_show(args: argparse.Namespace) -> int:
    try:
        config = load_runtime_config(args.root)
    except ConfigLoadError as exc:
        print(f"Konfiguration ungültig: {exc}", file=sys.stderr)
        return 1

    payload = {
        "system": config.system.model_dump(),
        "task_models": config.task_models.model_dump() if config.task_models else None,
        "teams": {
            team_id: {
                "team": bundle.team.model_dump(),
                "agents": {
                    agent_id: agent.model_dump()
                    for agent_id, agent in bundle.agents.items()
                },
            }
            for team_id, bundle in config.teams.items()
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _cmd_config_watch(args: argparse.Namespace) -> int:
    store = ConfigStore(args.root)

    def _on_reload(config) -> None:
        names = ", ".join(sorted(config.teams)) or "(keine)"
        print(f"[reload] Teams: {names}")

    store.on_reload(_on_reload)

    try:
        config = store.reload()
    except ConfigLoadError as exc:
        print(f"Konfiguration ungültig: {exc}", file=sys.stderr)
        return 1

    names = ", ".join(sorted(config.teams)) or "(keine)"
    print(f"Watch aktiv unter {store.root} — Teams: {names}")
    print("Strg+C zum Beenden.")

    store.start_watching(interval_seconds=args.interval)
    try:
        while True:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nWatch beendet.")
    finally:
        store.stop_watching()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bot", description="Agent-Runtime (MVP)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command")

    config_parser = sub.add_parser("config", help="Konfiguration prüfen und anzeigen")
    config_sub = config_parser.add_subparsers(dest="config_command", required=True)

    def add_root(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--root",
            type=Path,
            default=None,
            help="Projektroot (Standard: aktuelles Verzeichnis)",
        )

    validate = config_sub.add_parser("validate", help="Konfiguration validieren")
    add_root(validate)
    validate.set_defaults(func=_cmd_config_validate)

    show = config_sub.add_parser("show", help="Konfiguration als JSON ausgeben")
    add_root(show)
    show.set_defaults(func=_cmd_config_show)

    watch = config_sub.add_parser("watch", help="Hot-Reload (Dateiänderungen beobachten)")
    add_root(watch)
    watch.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling-Intervall in Sekunden (Standard: 1.0)",
    )
    watch.set_defaults(func=_cmd_config_watch)

    register_msg_commands(sub, add_root)
    register_run_commands(sub, add_root)
    register_llm_commands(sub, add_root)
    register_web_commands(sub, add_root)
    register_qdrant_commands(sub, add_root)
    register_chat_commands(sub, add_root)
    register_browser_commands(sub, add_root)
    register_team_commands(sub, add_root)
    register_mail_commands(sub, add_root)
    register_hours_commands(sub, add_root)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    if hasattr(args, "root") and args.root is None:
        args.root = _default_root()

    if args.command in (
        "config",
        "msg",
        "run",
        "llm",
        "web",
        "team",
        "qdrant",
        "chat",
        "browser",
        "mail",
        "hours",
    ):
        raise SystemExit(args.func(args))

    parser.error(f"Unbekannter Befehl: {args.command}")


if __name__ == "__main__":
    main()
