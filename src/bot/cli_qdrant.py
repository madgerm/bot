"""CLI: Qdrant (`bot qdrant`)."""

from __future__ import annotations

import argparse
import json
import sys


def cmd_qdrant_init(args: argparse.Namespace) -> int:
    from bot.qdrant import QdrantService, QdrantServiceError

    try:
        service = QdrantService.from_root(args.root)
        names = service.ensure_team_collections(args.team)
    except QdrantServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    print(f"Collections für Team '{args.team}':")
    for suffix, name in names.items():
        print(f"  {suffix}: {name}")
    return 0


def cmd_qdrant_upsert(args: argparse.Namespace) -> int:
    from bot.qdrant import QdrantService, QdrantServiceError

    try:
        service = QdrantService.from_root(args.root)
        service.ensure_team_collections(args.team)
        point_id = service.upsert(
            args.team,
            args.collection,
            text=args.text,
            payload={"source": args.source} if args.source else None,
        )
    except QdrantServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    print(f"Upsert OK — point_id={point_id}")
    return 0


def cmd_qdrant_search(args: argparse.Namespace) -> int:
    from bot.qdrant import QdrantService, QdrantServiceError

    try:
        service = QdrantService.from_root(args.root)
        results = service.search(args.team, args.collection, args.query, limit=args.limit)
    except QdrantServiceError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


def register_qdrant_commands(sub, add_root) -> None:
    qdrant = sub.add_parser("qdrant", help="Qdrant-Vektorspeicher")
    qdrant_sub = qdrant.add_subparsers(dest="qdrant_command", required=True)

    init = qdrant_sub.add_parser("init", help="Team-Collections anlegen")
    add_root(init)
    init.add_argument("--team", required=True)
    init.set_defaults(func=cmd_qdrant_init)

    upsert = qdrant_sub.add_parser("upsert", help="Text in Collection speichern")
    add_root(upsert)
    upsert.add_argument("--team", required=True)
    upsert.add_argument("--collection", choices=["project", "background"], required=True)
    upsert.add_argument("--text", required=True)
    upsert.add_argument("--source", default=None)
    upsert.set_defaults(func=cmd_qdrant_upsert)

    search = qdrant_sub.add_parser("search", help="Ähnlichkeitssuche")
    add_root(search)
    search.add_argument("--team", required=True)
    search.add_argument("--collection", choices=["project", "background"], required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--limit", type=int, default=5)
    search.set_defaults(func=cmd_qdrant_search)
