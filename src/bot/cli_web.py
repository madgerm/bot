"""CLI: Web-Panel starten (`bot web`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_web(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("uvicorn nicht installiert. pip install -e '.[dev]'", file=sys.stderr)
        return 1

    from bot.web import create_app

    app = create_app(args.root)
    ssl_kwargs = {}
    if args.ssl_cert and args.ssl_key:
        ssl_kwargs["ssl_certfile"] = str(args.ssl_cert)
        ssl_kwargs["ssl_keyfile"] = str(args.ssl_key)

    print(f"Web-Panel: http{'s' if ssl_kwargs else ''}://{args.host}:{args.port}/")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="debug" if args.verbose else "info",
        **ssl_kwargs,
    )
    return 0


def register_web_commands(
    sub: argparse._SubParsersAction,
    add_root,
) -> None:
    web_parser = sub.add_parser("web", help="Web-Panel starten (FastAPI)")
    add_root(web_parser)
    web_parser.add_argument("--host", default="127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8080)
    web_parser.add_argument("--ssl-cert", type=Path, default=None, help="TLS-Zertifikat (HTTPS)")
    web_parser.add_argument("--ssl-key", type=Path, default=None, help="TLS-Schlüssel (HTTPS)")
    web_parser.add_argument("-v", "--verbose", action="store_true")
    web_parser.set_defaults(func=cmd_web)
