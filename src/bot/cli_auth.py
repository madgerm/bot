"""CLI: Passwort-Hash für config/users.json."""

from __future__ import annotations

import argparse
import getpass
import sys

from bot.web.auth import hash_password


def _cmd_hash_password(args: argparse.Namespace) -> int:
    plain = args.password
    if plain is None:
        plain = getpass.getpass("Passwort: ")
        confirm = getpass.getpass("Passwort (Wiederholung): ")
        if plain != confirm:
            print("Passwörter stimmen nicht überein.", file=sys.stderr)
            return 1
    if not plain:
        print("Leeres Passwort nicht erlaubt.", file=sys.stderr)
        return 1
    print(hash_password(plain))
    return 0


def register_auth_commands(sub: argparse._SubParsersAction, add_root) -> None:
    auth = sub.add_parser("auth", help="Authentifizierung (Web-Panel)")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)

    hp = auth_sub.add_parser(
        "hash-password",
        help="bcrypt-Hash für users.json ausgeben",
    )
    hp.add_argument(
        "--password",
        default=None,
        help="Passwort (sonst interaktiv; nicht in Shell-History)",
    )
    hp.set_defaults(func=_cmd_hash_password)
