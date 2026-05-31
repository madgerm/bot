"""CLI: Internet-Relay (`bot relay serve`)."""

from __future__ import annotations

import argparse
import sys


def register_relay_commands(sub, add_root) -> None:
    relay = sub.add_parser(
        "relay",
        help="Internet-Relay (Panel und Runner verbinden sich hierhin)",
    )
    relay_sub = relay.add_subparsers(dest="relay_command", required=True)

    serve = relay_sub.add_parser("serve", help="Relay-Server starten")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=9000)
    serve.add_argument(
        "--token-env",
        default="BOT_RELAY_TOKEN",
        help="Umgebungsvariable für Zugangstoken (optional, aber empfohlen)",
    )
    serve.set_defaults(func=cmd_relay_serve)


def cmd_relay_serve(args: argparse.Namespace) -> int:
    import os

    import uvicorn

    from bot.relay.app import create_relay_app

    token_env = args.token_env
    if token_env and not os.environ.get(token_env):
        print(
            f"Hinweis: {token_env} nicht gesetzt — Relay ohne Token (nur für Tests).",
            file=sys.stderr,
        )

    app = create_relay_app()
    print(f"Bot-Relay: ws://{args.host}:{args.port}/ws  (Raum + role per Query)")
    print("  Panel:  ?role=panel&room=<id>&token=...")
    print("  Runner: ?role=runner&room=<id>&token=...")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0
