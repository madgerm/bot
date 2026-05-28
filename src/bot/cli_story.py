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

    review = story_sub.add_parser("review", help="Paralleles Szene-Review")
    add_root(review)
    review.add_argument("--team", required=True)
    review.add_argument("--chapter", required=True)
    review.add_argument("--scene", required=True)
    review.set_defaults(func=_cmd_review)

    mem = story_sub.add_parser("memory", help="Qdrant Story-Memory")
    add_root(mem)
    mem_sub = mem.add_subparsers(dest="memory_command", required=True)
    reindex = mem_sub.add_parser("reindex", help="Alles indexieren")
    add_root(reindex)
    reindex.add_argument("--team", required=True)
    reindex.set_defaults(func=_cmd_memory_reindex)
    search = mem_sub.add_parser("search", help="Semantische Suche")
    add_root(search)
    search.add_argument("--team", required=True)
    search.add_argument("--query", required=True)
    search.set_defaults(func=_cmd_memory_search)


def _cmd_init(args: argparse.Namespace) -> int:
    from bot.story import StoryDB

    db = StoryDB(args.root, args.team)
    db.ensure_story(title=args.title)
    print(db.path)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from bot.story import StoryDB

    db = StoryDB(args.root, args.team)
    print(
        json.dumps(
            {
                "meta": db.get_meta(),
                "plot": db.get_plot(),
                "characters": db.list_characters(),
                "chapters": db.list_chapters(),
                "scenes": [s.to_dict() for s in db.list_scenes()],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    from bot.story import StoryReviewError, StoryReviewRunner

    try:
        results = StoryReviewRunner.for_team(args.root, args.team).review_scene_parallel(
            args.chapter, args.scene
        )
    except StoryReviewError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False))
    return 0


def _cmd_memory_reindex(args: argparse.Namespace) -> int:
    from bot.story import StoryMemoryError, StoryMemoryService

    try:
        counts = StoryMemoryService.for_team(args.root, args.team).reindex_all()
    except StoryMemoryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(counts, indent=2))
    return 0


def _cmd_memory_search(args: argparse.Namespace) -> int:
    from bot.story import StoryMemoryError, StoryMemoryService

    try:
        results = StoryMemoryService.for_team(args.root, args.team).search(args.query)
    except StoryMemoryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0
