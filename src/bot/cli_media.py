"""CLI: Medien."""

from __future__ import annotations

import argparse
import json
import sys


def register_media_commands(sub, add_root) -> None:
    p = sub.add_parser("media", help="Vision, STT, TTS, Bildgenerierung")
    add_root(p)
    media_sub = p.add_subparsers(dest="media_command", required=True)

    img = media_sub.add_parser("image", help="Bild generieren")
    add_root(img)
    img.add_argument("--team", required=True)
    img.add_argument("--prompt", required=True)
    img.set_defaults(func=_cmd_image)


def _cmd_image(args: argparse.Namespace) -> int:
    from bot.media import MediaService, MediaServiceError

    try:
        result = MediaService.for_team(args.root, args.team).generate_image(args.prompt)
    except MediaServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
