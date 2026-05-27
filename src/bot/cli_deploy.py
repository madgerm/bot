"""CLI: Deployment (Linux-User pro Team)."""

from __future__ import annotations

import argparse


def register_deploy_commands(sub, add_root) -> None:
    p = sub.add_parser("deploy", help="Deployment-Artefakte (systemd)")
    add_root(p)
    deploy_sub = p.add_subparsers(dest="deploy_command", required=True)

    gen = deploy_sub.add_parser("generate", help="systemd + Provision-Skript")
    add_root(gen)
    gen.add_argument("--team", required=True)
    gen.add_argument("--output", type=str, default=None)
    gen.set_defaults(func=_cmd_generate)


def _cmd_generate(args: argparse.Namespace) -> int:
    from pathlib import Path

    from bot.deploy import DeployService

    out = Path(args.output) if args.output else None
    paths = DeployService(args.root).write_artifacts(args.team, out)
    for k, v in paths.items():
        print(f"{k}: {v}")
    return 0
