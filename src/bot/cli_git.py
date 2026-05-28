"""CLI: Git."""

from __future__ import annotations

import argparse
import sys


def register_git_commands(sub, add_root) -> None:
    p = sub.add_parser("git", help="Git-Integration pro Team")
    add_root(p)
    git_sub = p.add_subparsers(dest="git_command", required=True)

    for name, help_text in [
        ("status", "git status"),
        ("log", "git log"),
        ("commit", "git commit"),
        ("push", "git push"),
        ("pull", "git pull"),
    ]:
        cmd = git_sub.add_parser(name, help=help_text)
        add_root(cmd)
        cmd.add_argument("--team", required=True)
        if name == "commit":
            cmd.add_argument("-m", "--message", required=True)
        if name == "log":
            cmd.add_argument("-n", type=int, default=10)
        cmd.set_defaults(func=_make_handler(name))


def _make_handler(command: str):
    def handler(args: argparse.Namespace) -> int:
        from bot.git_svc import GitService, GitServiceError

        try:
            svc = GitService.for_team(args.root, args.team)
            if command == "status":
                print(svc.status())
            elif command == "log":
                print(svc.log(args.n))
            elif command == "commit":
                print(svc.commit(args.message))
            elif command == "push":
                print(svc.push())
            elif command == "pull":
                print(svc.pull())
        except GitServiceError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    return handler
