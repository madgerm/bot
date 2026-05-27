"""CLI: Story (Charaktere, Welten, Szenen)."""

from __future__ import annotations

import argparse
import json


def register_story_commands(sub, add_root) -> None:
    p = sub.add_parser("story", help="Story-Team (Charaktere, Welten, Szenen)")
    add_root(p)
    story_sub = p.add_subparsers(dest="story_command", required=True)

    ls = story_sub.add_parser("list", help="Alles auflisten")
    add_root(ls)
    ls.add_argument("--team", required=True)
    ls.set_defaults(func=_cmd_list)

    char = story_sub.add_parser("character", help="Charakter anlegen")
    add_root(char)
    char.add_argument("--team", required=True)
    char.add_argument("--name", required=True)
    char.add_argument("--bio", default="")
    char.set_defaults(func=_cmd_character)


def _cmd_list(args: argparse.Namespace) -> int:
    from bot.story import StoryService

    svc = StoryService.for_team(args.root, args.team)
    print(
        json.dumps(
            {
                "characters": [c.to_dict() for c in svc.store.list_characters()],
                "worlds": [w.to_dict() for w in svc.store.list_worlds()],
                "scenes": [s.to_dict() for s in svc.store.list_scenes()],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_character(args: argparse.Namespace) -> int:
    from bot.story import StoryService

    c = StoryService.for_team(args.root, args.team).store.save_character(
        args.name, args.bio
    )
    print(json.dumps(c.to_dict(), indent=2, ensure_ascii=False))
    return 0
