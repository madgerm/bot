"""StoryDB — dateibasierter Data Layer (wie im Story-Plan)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class StoryDBError(Exception):
    pass


@dataclass
class SceneInfo:
    chapter_id: str
    scene_id: str
    title: str
    path: Path
    version: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "chapter_id": self.chapter_id,
            "scene_id": self.scene_id,
            "title": self.title,
            "path": str(self.path),
            "version": self.version,
            "status": self.status,
        }


class StoryDB:
    """
    data/<team>/story/
      AGENTS.md
      meta.json
      world/orte.md, regeln.md, timeline.md
      characters/<id>.json
      chapters/kapitel-NNN/szene-NNN.md
      reviews/issues.jsonl
    """

    def __init__(self, root: Path | str, team_id: str) -> None:
        self.root = Path(root).resolve()
        self.team_id = team_id
        self.path = self.root / "data" / team_id / "story"
        self.path.mkdir(parents=True, exist_ok=True)

    def ensure_story(
        self,
        *,
        title: str,
        genre: str = "",
        setting: str = "",
        tone: str = "",
        main_characters: list[str] | None = None,
    ) -> None:
        meta = {
            "title": title,
            "genre": genre,
            "setting": setting,
            "tone": tone,
            "main_characters": main_characters or [],
            "created_at": datetime.now(UTC).isoformat(),
            "target_word_count": 80000,
        }
        self._write_json(self.path / "meta.json", meta)
        agents_md = self.path / "AGENTS.md"
        if not agents_md.is_file():
            chars = ", ".join(main_characters or [])
            agents_md.write_text(
                f"# {title}\n\n"
                f"- **Genre:** {genre}\n"
                f"- **Setting:** {setting}\n"
                f"- **Ton:** {tone}\n"
                f"- **Hauptfiguren:** {chars}\n",
                encoding="utf-8",
            )
        (self.path / "world").mkdir(exist_ok=True)
        (self.path / "characters").mkdir(exist_ok=True)
        (self.path / "chapters").mkdir(exist_ok=True)
        (self.path / "reviews").mkdir(exist_ok=True)
        for fname, default in [
            ("orte.md", "# Orte\n\n"),
            ("regeln.md", "# World-Regeln\n\n"),
            ("timeline.md", "# Timeline\n\n"),
        ]:
            p = self.path / "world" / fname
            if not p.is_file():
                p.write_text(default, encoding="utf-8")
        issues = self.path / "reviews" / "issues.jsonl"
        if not issues.is_file():
            issues.write_text("", encoding="utf-8")
        (self.path / "plot").mkdir(exist_ok=True)
        plot_path = self.path / "plot" / "outline.json"
        if not plot_path.is_file():
            self._write_json(
                plot_path,
                {
                    "structure": "three_act",
                    "acts": [],
                    "notes": "",
                },
            )

    def get_meta(self) -> dict[str, Any]:
        p = self.path / "meta.json"
        if not p.is_file():
            return {}
        return json.loads(p.read_text(encoding="utf-8"))

    def update_meta(self, **fields: Any) -> dict[str, Any]:
        meta = self.get_meta()
        meta.update(fields)
        meta["updated_at"] = datetime.now(UTC).isoformat()
        self._write_json(self.path / "meta.json", meta)
        return meta

    def list_characters(self) -> list[dict[str, Any]]:
        chars_dir = self.path / "characters"
        if not chars_dir.is_dir():
            return []
        result = []
        for p in sorted(chars_dir.glob("*.json")):
            data = json.loads(p.read_text(encoding="utf-8"))
            char = data.get("character", data)
            char.setdefault("id", p.stem)
            result.append(char)
        return result

    def get_character(self, char_id: str) -> dict[str, Any] | None:
        p = self.path / "characters" / f"{char_id}.json"
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        char = data.get("character", data)
        char.setdefault("id", char_id)
        return char

    def save_character(self, char_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        payload["id"] = char_id
        payload.setdefault("status", "active")
        payload["updated_at"] = datetime.now(UTC).isoformat()
        self._write_json(
            self.path / "characters" / f"{char_id}.json",
            {"character": payload},
        )
        return payload

    def delete_character(self, char_id: str) -> None:
        p = self.path / "characters" / f"{char_id}.json"
        if p.is_file():
            p.unlink()

    def read_world_file(self, name: str) -> str:
        allowed = {"orte.md", "regeln.md", "timeline.md"}
        if name not in allowed:
            raise StoryDBError(f"Unbekannte World-Datei: {name}")
        p = self.path / "world" / name
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    def write_world_file(self, name: str, content: str) -> None:
        allowed = {"orte.md", "regeln.md", "timeline.md"}
        if name not in allowed:
            raise StoryDBError(f"Unbekannte World-Datei: {name}")
        (self.path / "world").mkdir(exist_ok=True)
        (self.path / "world" / name).write_text(content, encoding="utf-8")

    def list_chapters(self) -> list[str]:
        ch = self.path / "chapters"
        if not ch.is_dir():
            return []
        return sorted(d.name for d in ch.iterdir() if d.is_dir())

    def list_scenes(self, chapter_id: str | None = None) -> list[SceneInfo]:
        scenes: list[SceneInfo] = []
        chapters = [chapter_id] if chapter_id else self.list_chapters()
        for ch_id in chapters:
            ch_dir = self.path / "chapters" / ch_id
            if not ch_dir.is_dir():
                continue
            for md in sorted(ch_dir.glob("szene-*.md")):
                content = md.read_text(encoding="utf-8")
                meta, body = self._parse_frontmatter(content)
                scenes.append(
                    SceneInfo(
                        chapter_id=ch_id,
                        scene_id=md.stem,
                        title=meta.get("title", md.stem),
                        path=md,
                        version=int(meta.get("version", 1)),
                        status=meta.get("status", "draft"),
                    )
                )
        return scenes

    def get_scene(self, chapter_id: str, scene_id: str) -> tuple[dict[str, Any], str]:
        p = self.path / "chapters" / chapter_id / f"{scene_id}.md"
        if not p.is_file():
            raise StoryDBError(f"Szene nicht gefunden: {chapter_id}/{scene_id}")
        meta, body = self._parse_frontmatter(p.read_text(encoding="utf-8"))
        return meta, body

    def add_chapter(self, chapter_id: str | None = None) -> str:
        chapters = self.list_chapters()
        if chapter_id is None:
            n = len(chapters) + 1
            chapter_id = f"kapitel-{n:03d}"
        (self.path / "chapters" / chapter_id).mkdir(parents=True, exist_ok=True)
        return chapter_id

    def add_scene(
        self,
        chapter_id: str,
        scene_id: str | None = None,
        *,
        title: str = "",
        content: str = "",
        status: str = "draft",
    ) -> SceneInfo:
        ch_dir = self.path / "chapters" / chapter_id
        ch_dir.mkdir(parents=True, exist_ok=True)
        if scene_id is None:
            existing = list(ch_dir.glob("szene-*.md"))
            scene_id = f"szene-{len(existing) + 1:03d}"
        meta = {
            "title": title or scene_id,
            "version": 1,
            "status": status,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        p = ch_dir / f"{scene_id}.md"
        p.write_text(self._format_frontmatter(meta) + content, encoding="utf-8")
        return SceneInfo(chapter_id, scene_id, meta["title"], p, 1, status)

    def update_scene(
        self,
        chapter_id: str,
        scene_id: str,
        content: str,
        *,
        expected_version: int,
        status: str | None = None,
    ) -> SceneInfo:
        meta, _old = self.get_scene(chapter_id, scene_id)
        current = int(meta.get("version", 1))
        if current != expected_version:
            raise StoryDBError(
                f"Versionskonflikt: erwartet {expected_version}, aktuell {current}"
            )
        meta["version"] = current + 1
        meta["updated_at"] = datetime.now(UTC).isoformat()
        if status is not None:
            meta["status"] = status
        p = self.path / "chapters" / chapter_id / f"{scene_id}.md"
        p.write_text(self._format_frontmatter(meta) + content, encoding="utf-8")
        return SceneInfo(
            chapter_id,
            scene_id,
            meta.get("title", scene_id),
            p,
            meta["version"],
            meta.get("status", "draft"),
        )

    def list_review_issues(self, limit: int = 50) -> list[dict[str, Any]]:
        p = self.path / "reviews" / "issues.jsonl"
        if not p.is_file():
            return []
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        issues = [json.loads(ln) for ln in lines[-limit:]]
        return issues

    def get_plot(self) -> dict[str, Any]:
        p = self.path / "plot" / "outline.json"
        if not p.is_file():
            return {"structure": "three_act", "acts": [], "notes": ""}
        return json.loads(p.read_text(encoding="utf-8"))

    def save_plot(self, plot: dict[str, Any]) -> dict[str, Any]:
        plot["updated_at"] = datetime.now(UTC).isoformat()
        self._write_json(self.path / "plot" / "outline.json", plot)
        return plot

    def build_relationship_graph(self) -> dict[str, Any]:
        """Knoten und Kanten für Beziehungs-Graph (Mermaid/vis)."""
        nodes: list[dict[str, str]] = []
        edges: list[dict[str, str]] = []
        for char in self.list_characters():
            cid = char.get("id", "?")
            label = char.get("name", cid)
            nodes.append({"id": cid, "label": label, "role": char.get("role", "")})
            for rel in char.get("relationships") or []:
                to_id = rel.get("to")
                if not to_id:
                    continue
                edges.append(
                    {
                        "from": cid,
                        "to": to_id,
                        "label": rel.get("type", ""),
                        "dynamic": rel.get("dynamic", ""),
                    }
                )
        return {"nodes": nodes, "edges": edges}

    def gather_memory_documents(self) -> list[dict[str, Any]]:
        """Alle indexierbaren Story-Texte für Qdrant."""
        docs: list[dict[str, Any]] = []
        meta = self.get_meta()
        if meta:
            docs.append(
                {
                    "kind": "meta",
                    "id": "meta",
                    "text": json.dumps(meta, ensure_ascii=False),
                }
            )
        plot = self.get_plot()
        if plot.get("acts"):
            docs.append(
                {
                    "kind": "plot",
                    "id": "plot",
                    "text": json.dumps(plot, ensure_ascii=False),
                }
            )
        for char in self.list_characters():
            docs.append(
                {
                    "kind": "character",
                    "id": char["id"],
                    "text": json.dumps(char, ensure_ascii=False),
                }
            )
        for fname in ("orte.md", "regeln.md", "timeline.md"):
            text = self.read_world_file(fname)
            if text.strip():
                docs.append({"kind": "world", "id": fname, "text": text})
        for scene in self.list_scenes():
            meta_s, body = self.get_scene(scene.chapter_id, scene.scene_id)
            docs.append(
                {
                    "kind": "scene",
                    "id": f"{scene.chapter_id}/{scene.scene_id}",
                    "text": f"{meta_s.get('title', '')}\n{body}",
                    "chapter_id": scene.chapter_id,
                    "scene_id": scene.scene_id,
                }
            )
        return docs

    def add_review_issue(
        self,
        *,
        checker: str,
        severity: str,
        message: str,
        chapter_id: str | None = None,
        scene_id: str | None = None,
    ) -> dict[str, Any]:
        issue = {
            "id": datetime.now(UTC).strftime("%Y%m%d%H%M%S%f"),
            "checker": checker,
            "severity": severity,
            "message": message,
            "chapter_id": chapter_id,
            "scene_id": scene_id,
            "created_at": datetime.now(UTC).isoformat(),
            "resolved": False,
        }
        p = self.path / "reviews" / "issues.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(issue, ensure_ascii=False) + "\n")
        return issue

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        meta: dict[str, Any] = {}
        for line in parts[1].strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
        return meta, parts[2].lstrip("\n")

    @staticmethod
    def _format_frontmatter(meta: dict[str, Any]) -> str:
        lines = ["---"]
        for k, v in meta.items():
            lines.append(f"{k}: {v}")
        lines.append("---\n\n")
        return "\n".join(lines)
