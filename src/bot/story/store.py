"""Story-Daten in SQLite (data/<team>/story.sqlite)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class StoryStoreError(Exception):
    pass


@dataclass
class Character:
    id: str
    name: str
    bio: str
    traits: dict[str, Any]
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "bio": self.bio,
            "traits": self.traits,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class World:
    id: str
    name: str
    description: str
    rules: dict[str, Any]
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "rules": self.rules,
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Scene:
    id: str
    title: str
    content: str
    characters: list[str]
    world_id: str | None
    version: int
    updated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "characters": self.characters,
            "world_id": self.world_id,
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
        }


class StoryStore:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.db_path = self.root / "data" / team_id / "story.sqlite"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS characters (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    bio TEXT NOT NULL DEFAULT '',
                    traits TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS worlds (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    rules TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scenes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    characters TEXT NOT NULL DEFAULT '[]',
                    world_id TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def list_characters(self) -> list[Character]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM characters ORDER BY name").fetchall()
        return [self._char_row(r) for r in rows]

    def save_character(self, name: str, bio: str = "", traits: dict | None = None) -> Character:
        now = datetime.now(UTC)
        cid = str(uuid.uuid4())
        traits_json = json.dumps(traits or {})
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO characters (id, name, bio, traits, updated_at) VALUES (?,?,?,?,?)",
                (cid, name, bio, traits_json, now.isoformat()),
            )
        return Character(cid, name, bio, traits or {}, now)

    def list_worlds(self) -> list[World]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM worlds ORDER BY name").fetchall()
        return [self._world_row(r) for r in rows]

    def save_world(self, name: str, description: str = "", rules: dict | None = None) -> World:
        now = datetime.now(UTC)
        wid = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO worlds (id, name, description, rules, updated_at) VALUES (?,?,?,?,?)",
                (wid, name, description, json.dumps(rules or {}), now.isoformat()),
            )
        return World(wid, name, description, rules or {}, now)

    def list_scenes(self) -> list[Scene]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM scenes ORDER BY updated_at DESC").fetchall()
        return [self._scene_row(r) for r in rows]

    def save_scene(
        self,
        title: str,
        content: str,
        *,
        characters: list[str] | None = None,
        world_id: str | None = None,
    ) -> Scene:
        now = datetime.now(UTC)
        sid = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scenes (id, title, content, characters, world_id, version, updated_at)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    title,
                    content,
                    json.dumps(characters or []),
                    world_id,
                    1,
                    now.isoformat(),
                ),
            )
        return Scene(sid, title, content, characters or [], world_id, 1, now)

    def update_scene(self, scene_id: str, content: str, expected_version: int) -> Scene:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,)).fetchone()
            if not row:
                raise StoryStoreError("Szene nicht gefunden")
            if row["version"] != expected_version:
                raise StoryStoreError("Versionskonflikt — Szene wurde zwischenzeitlich geändert")
            new_version = expected_version + 1
            now = datetime.now(UTC)
            conn.execute(
                "UPDATE scenes SET content = ?, version = ?, updated_at = ? WHERE id = ?",
                (content, new_version, now.isoformat(), scene_id),
            )
        scenes = [s for s in self.list_scenes() if s.id == scene_id]
        return scenes[0]

    def _char_row(self, row: sqlite3.Row) -> Character:
        return Character(
            row["id"],
            row["name"],
            row["bio"],
            json.loads(row["traits"]),
            datetime.fromisoformat(row["updated_at"]),
        )

    def _world_row(self, row: sqlite3.Row) -> World:
        return World(
            row["id"],
            row["name"],
            row["description"],
            json.loads(row["rules"]),
            datetime.fromisoformat(row["updated_at"]),
        )

    def _scene_row(self, row: sqlite3.Row) -> Scene:
        return Scene(
            row["id"],
            row["title"],
            row["content"],
            json.loads(row["characters"]),
            row["world_id"],
            row["version"],
            datetime.fromisoformat(row["updated_at"]),
        )
