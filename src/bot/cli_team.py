"""CLI: Team-Runner API und Token (`bot team`)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from bot.team_api.auth import generate_api_token


def cmd_team_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn nicht installiert.", file=sys.stderr)
        return 1

    from bot.team_api import create_team_api_app

    if not os.environ.get(args.token_env):
        print(
            f"Warnung: {args.token_env} ist nicht gesetzt.\n"
            f"Erzeuge einen Token mit: bot team token",
            file=sys.stderr,
        )

    app = create_team_api_app(args.root)
    ssl_kwargs = {}
    if args.ssl_cert and args.ssl_key:
        ssl_kwargs["ssl_certfile"] = str(args.ssl_cert)
        ssl_kwargs["ssl_keyfile"] = str(args.ssl_key)

    scheme = "https" if ssl_kwargs else "http"
    print(f"Team-Runner API: {scheme}://{args.host}:{args.port}/api/v1/health")
    print(f"Token-Env: {args.token_env}")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="debug" if args.verbose else "info",
        **ssl_kwargs,
    )
    return 0


def cmd_team_token(args: argparse.Namespace) -> int:
    token = generate_api_token()
    env_name = args.env_name

    print(f"export {env_name}={token}")
    print()
    print("Auf dem Team-Runner-Rechner (Shell/systemd) setzen, dann:")
    print(f"  bot team serve --root {args.root}")
    print()
    print("Im Web-Panel-Rechner für Remote-Host:")
    print(f"  export {env_name}={token}")
    print("  (gleicher Wert in team_hosts.json als token_env referenzieren)")

    if args.write_config:
        config_dir = args.root / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        api_path = config_dir / "team_api.json"
        api_path.write_text(
            json.dumps({"token_env": env_name, "teams": ["demo"]}, indent=2) + "\n",
            encoding="utf-8",
        )
        example = config_dir / "team_api.json.example"
        if not example.is_file():
            example.write_text(
                json.dumps({"token_env": env_name, "teams": ["demo"]}, indent=2) + "\n",
                encoding="utf-8",
            )
        print(f"\nGeschrieben: {api_path} (ohne Klartext-Token — nur token_env)")

    return 0


def register_team_commands(
    sub: argparse._SubParsersAction,
    add_root,
) -> None:
    team_parser = sub.add_parser("team", help="Team-Runner (API für Remote-Zugriff)")
    team_sub = team_parser.add_subparsers(dest="team_command", required=True)

    serve = team_sub.add_parser("serve", help="Team-Runner-HTTP-API starten")
    add_root(serve)
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8443)
    serve.add_argument(
        "--token-env",
        default="BOT_TEAM_API_TOKEN",
        help="Umgebungsvariable mit API-Token",
    )
    serve.add_argument("--ssl-cert", type=Path, default=None)
    serve.add_argument("--ssl-key", type=Path, default=None)
    serve.add_argument("-v", "--verbose", action="store_true")
    serve.set_defaults(func=cmd_team_serve)

    token = team_sub.add_parser("token", help="Neuen API-Token erzeugen (Ausgabe für export)")
    add_root(token)
    token.add_argument("--env-name", default="BOT_TEAM_API_TOKEN")
    token.add_argument(
        "--write-config",
        action="store_true",
        help="config/team_api.json mit token_env anlegen",
    )
    token.set_defaults(func=cmd_team_token)

    init_cmd = team_sub.add_parser(
        "init", help="Qdrant-Collections + Chat-DB anlegen"
    )
    add_root(init_cmd)
    init_cmd.add_argument("team_id")
    init_cmd.set_defaults(func=cmd_team_init)


def cmd_team_init(args: argparse.Namespace) -> int:
    from bot.team_init import init_team_resources

    results = init_team_resources(args.root, args.team_id)
    for key, value in results.items():
        print(f"{key}: {value}")
    return 0
