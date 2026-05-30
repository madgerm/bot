"""CLI: Supervisor starten (`bot run`)."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from bot.config import ConfigLoadError
from bot.runtime import Supervisor


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def cmd_run(args: argparse.Namespace) -> int:
    _configure_logging(args.verbose)

    try:
        supervisor = Supervisor(args.root)
    except ConfigLoadError as exc:
        print(f"Konfiguration ungültig: {exc}", file=sys.stderr)
        return 1

    team_ids = args.team if args.team else None

    if args.once:
        processed = supervisor.run_until_idle(team_ids=team_ids, max_rounds=args.max_rounds)
        print(f"Fertig — {processed} Message(s) in diesem Lauf verarbeitet.")
        return 0

    if args.watch_config:
        supervisor.enable_config_watch(interval_seconds=args.config_interval)

    supervisor.start(team_ids=team_ids)
    teams = ", ".join(supervisor._teams) or "(keine)"
    mode = supervisor.config.system.system.polling.worker_mode
    watch = supervisor.config.system.system.polling.inbox_watch_seconds
    print(f"Supervisor läuft — Teams: {teams}")
    print(f"Agent-Worker: {mode} · Inbox-Watch: {watch}s · Idle-Poll: {supervisor.config.system.system.polling.interval_seconds}s")
    print("Strg+C zum Beenden.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSupervisor wird gestoppt …")
    finally:
        supervisor.stop_config_watch()
        supervisor.stop()

    return 0


def register_run_commands(
    sub: argparse._SubParsersAction,
    add_root,
) -> None:
    run_parser = sub.add_parser("run", help="Supervisor und Agent-Loops starten")
    add_root(run_parser)
    run_parser.add_argument(
        "--team",
        action="append",
        default=None,
        help="Nur diese Team-ID(s) starten (mehrfach möglich)",
    )
    run_parser.add_argument(
        "--once",
        action="store_true",
        help="Ein Durchlauf bis idle (für Tests/Cron)",
    )
    run_parser.add_argument(
        "--max-rounds",
        type=int,
        default=20,
        help="Max. Runden bei --once (Standard: 20)",
    )
    run_parser.add_argument(
        "--watch-config",
        action="store_true",
        help="Config Hot-Reload aktivieren",
    )
    run_parser.add_argument(
        "--config-interval",
        type=float,
        default=2.0,
        help="Config-Watch-Intervall in Sekunden",
    )
    run_parser.add_argument("-v", "--verbose", action="store_true")
    run_parser.set_defaults(func=cmd_run)
