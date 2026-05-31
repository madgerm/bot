"""Ein Befehl: Team-Runner + Web-Panel (`bot up`)."""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
import threading
import time
from pathlib import Path


def _ensure_session_secret(root: Path) -> None:
    if os.environ.get("BOT_SESSION_SECRET"):
        return
    for env_path in (root / ".env", Path.home() / ".config/bot/env"):
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("BOT_SESSION_SECRET=") and len(line) > 20:
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        os.environ["BOT_SESSION_SECRET"] = val
                        return
    secret = secrets.token_hex(32)
    os.environ["BOT_SESSION_SECRET"] = secret
    home_env = Path.home() / ".config/bot/env"
    home_env.parent.mkdir(parents=True, exist_ok=True)
    if home_env.is_file():
        text = home_env.read_text(encoding="utf-8")
        if "BOT_SESSION_SECRET=" not in text:
            home_env.write_text(
                text.rstrip() + f"\nBOT_SESSION_SECRET={secret}\n",
                encoding="utf-8",
            )
    else:
        home_env.write_text(f"BOT_SESSION_SECRET={secret}\n", encoding="utf-8")


def cmd_up(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn fehlt: pip install -e '.[dev]'", file=sys.stderr)
        return 1

    from bot.config import ConfigLoadError
    from bot.runtime import Supervisor
    from bot.web import create_app

    root = Path(args.root).resolve()
    _ensure_session_secret(root)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    try:
        supervisor = Supervisor(root)
    except ConfigLoadError as exc:
        print(f"Konfiguration ungültig: {exc}", file=sys.stderr)
        return 1

    team_ids = args.team if args.team else None
    if args.watch_config:
        supervisor.enable_config_watch(interval_seconds=args.config_interval)

    supervisor.start(team_ids=team_ids)
    teams = ", ".join(supervisor._teams) or "(keine)"

    stop_event = threading.Event()

    def _run_supervisor_loop() -> None:
        try:
            while not stop_event.is_set():
                time.sleep(1)
        finally:
            supervisor.stop_config_watch()
            supervisor.stop()

    runner_thread = threading.Thread(
        target=_run_supervisor_loop,
        name="bot-supervisor",
        daemon=True,
    )
    runner_thread.start()

    host = args.host
    port = args.port
    print("")
    print("══════════════════════════════════════════════════")
    print(f"  Bot läuft — Panel: http://{host}:{port}/")
    print(f"  Login: admin / changeme  (config/users.json)")
    print(f"  Teams (Agents): {teams}")
    print("  Strg+C beendet Panel und Runner.")
    print("══════════════════════════════════════════════════")
    print("")

    app = create_app(root)
    ssl_kwargs: dict = {}
    if args.ssl_cert and args.ssl_key:
        ssl_kwargs["ssl_certfile"] = str(args.ssl_cert)
        ssl_kwargs["ssl_keyfile"] = str(args.ssl_key)

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="debug" if args.verbose else "info",
            **ssl_kwargs,
        )
    except KeyboardInterrupt:
        print("\nBeenden …")
    finally:
        stop_event.set()
        supervisor.stop_config_watch()
        supervisor.stop()
        runner_thread.join(timeout=15)

    return 0


def register_up_commands(
    sub: argparse._SubParsersAction,
    add_root,
) -> None:
    up = sub.add_parser(
        "up",
        help="Alles starten: Agents (bot run) + Web-Panel auf 0.0.0.0:8080",
    )
    add_root(up)
    up.add_argument(
        "--host",
        default="0.0.0.0",
        help="Panel-Host (Standard: 0.0.0.0 = im Netz erreichbar)",
    )
    up.add_argument("--port", type=int, default=8080)
    up.add_argument("--team", action="append", default=None, help="Nur diese Team(s)")
    up.add_argument("--ssl-cert", type=Path, default=None)
    up.add_argument("--ssl-key", type=Path, default=None)
    up.add_argument("-v", "--verbose", action="store_true")
    up.add_argument("--watch-config", action="store_true")
    up.add_argument("--config-interval", type=float, default=2.0)
    up.set_defaults(func=cmd_up)
