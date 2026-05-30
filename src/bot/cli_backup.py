"""CLI: bot backup create|restore|list"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bot.backup import BackupError, create_backup, list_team_databases, restore_backup


def _cmd_create(args: argparse.Namespace) -> int:
    teams = args.team if args.team else None
    try:
        out = create_backup(
            args.root,
            team_ids=teams,
            include_teams_config=not args.data_only,
            output=args.output,
        )
    except BackupError as exc:
        print(f"Backup fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    print(out)
    return 0


def _cmd_restore(args: argparse.Namespace) -> int:
    try:
        restored = restore_backup(
            args.root,
            args.archive,
            team_ids=args.team,
            dry_run=args.dry_run,
        )
    except BackupError as exc:
        print(f"Restore fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"Dry-run: {len(restored)} Datei(en) würden wiederhergestellt")
    else:
        print(f"Wiederhergestellt: {len(restored)} Datei(en)")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    data = Path(args.root) / "data"
    if not data.is_dir():
        print("Keine data/-Verzeichnisse")
        return 0
    for team_dir in sorted(data.iterdir()):
        if not team_dir.is_dir() or team_dir.name.startswith("_"):
            continue
        dbs = list_team_databases(Path(args.root), team_dir.name)
        print(f"{team_dir.name}: {len(dbs)} SQLite — {', '.join(p.name for p in dbs) or '—'}")
    backups = sorted((data / "_backups").glob("*.tar.gz")) if (data / "_backups").is_dir() else []
    if backups:
        print("\nArchive:")
        for b in backups[-10:]:
            print(f"  {b.name}")
    return 0


def register_backup_commands(sub: argparse._SubParsersAction, add_root) -> None:
    backup = sub.add_parser("backup", help="Team-Daten sichern und wiederherstellen")
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)

    create = backup_sub.add_parser("create", help="tar.gz-Backup erstellen")
    add_root(create)
    create.add_argument("--team", action="append", help="Nur dieses Team (mehrfach)")
    create.add_argument("--output", type=Path, default=None, help="Zielpfad der .tar.gz")
    create.add_argument(
        "--data-only",
        action="store_true",
        help="Nur data/<team>/, ohne teams/<team>/ Konfiguration",
    )
    create.set_defaults(func=_cmd_create)

    restore = backup_sub.add_parser("restore", help="Backup einspielen")
    add_root(restore)
    restore.add_argument("archive", type=Path, help="Pfad zur .tar.gz")
    restore.add_argument("--team", action="append", help="Nur diese Teams aus dem Archiv")
    restore.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nicht schreiben")
    restore.set_defaults(func=_cmd_restore)

    list_p = backup_sub.add_parser("list", help="SQLite-Dateien und Archive auflisten")
    add_root(list_p)
    list_p.set_defaults(func=_cmd_list)
