"""CLI: Story (dateibasierter StoryDB)."""

from __future__ import annotations

import argparse
import json
import sys


def register_story_commands(sub, add_root) -> None:
    p = sub.add_parser("story", help="Story-Team (Dateien unter data/<team>/story/)")
    add_root(p)
    story_sub = p.add_subparsers(dest="story_command", required=True)

    init = story_sub.add_parser("init", help="Story-Struktur anlegen")
    add_root(init)
    init.add_argument("--team", required=True)
    init.add_argument("--title", required=True)
    init.set_defaults(func=_cmd_init)

    ls = story_sub.add_parser("list", help="Übersicht")
    add_root(ls)
    ls.add_argument("--team", required=True)
    ls.set_defaults(func=_cmd_list)

    export = story_sub.add_parser("export", help="Story als EPUB/PDF/ZIP exportieren")
    add_root(export)
    export.add_argument("--team", required=True)
    export.add_argument(
        "--format", dest="fmt", choices=["epub", "pdf", "mdzip"], default="epub"
    )
    export.set_defaults(func=_cmd_export)


def _cmd_init(args: argparse.Namespace) -> int:
    from bot.story import StoryDB

    db = StoryDB(args.root, args.team)
    db.ensure_story(title=args.title)
    print(db.path)
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    from bot.story.export import StoryExportError, export_story

    try:
        path = export_story(args.root, args.team, args.fmt)
    except StoryExportError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from bot.story import StoryDB

    db = StoryDB(args.root, args.team)
    print(
        json.dumps(
            {
                "meta": db.get_meta(),
                "characters": db.list_characters(),
                "chapters": db.list_chapters(),
                "scenes": [s.to_dict() for s in db.list_scenes()],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0
