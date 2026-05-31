"""Agent-Tools: Dateien, Git, Qdrant, Browser, Story — aus dem Agent-Loop aufrufbar."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from bot.runtime.context import HandlerContext

TOOL_NAMES = frozenset(
    {
        "read_file",
        "write_file",
        "list_files",
        "git_status",
        "git_commit",
        "qdrant_search",
        "browser_open",
        "story_read_scene",
        "story_write_scene",
        "index_workspace",
    }
)

_TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".json",
    ".txt",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
    ".sql",
    ".ini",
    ".cfg",
}


class ToolExecutionError(Exception):
    pass


@dataclass
class ToolResult:
    ok: bool
    output: str
    data: dict[str, Any] | None = None


class AgentToolkit:
    def __init__(self, ctx: HandlerContext) -> None:
        self.ctx = ctx

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        if name not in TOOL_NAMES:
            return ToolResult(False, f"Unbekanntes Tool: {name}")
        try:
            handler = getattr(self, f"_tool_{name}")
            return handler(args)
        except ToolExecutionError as exc:
            return ToolResult(False, str(exc))
        except Exception as exc:
            return ToolResult(False, f"{name}: {exc}")

    def _tool_read_file(self, args: dict[str, Any]) -> ToolResult:
        from bot.files.service import FileService, FileServiceError

        path = str(args.get("path", ""))
        try:
            content = FileService.for_team(self.ctx.root, self.ctx.team_id).read_file(path)
        except FileServiceError as exc:
            raise ToolExecutionError(str(exc)) from exc
        if len(content) > 12000:
            content = content[:12000] + "\n… (gekürzt)"
        return ToolResult(True, content, {"path": path})

    def _tool_write_file(self, args: dict[str, Any]) -> ToolResult:
        from bot.files.service import FileService, FileServiceError

        path = str(args.get("path", ""))
        content = str(args.get("content", ""))
        try:
            FileService.for_team(self.ctx.root, self.ctx.team_id).write_file(path, content)
        except FileServiceError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return ToolResult(True, f"Geschrieben: {path}", {"path": path, "bytes": len(content)})

    def _tool_list_files(self, args: dict[str, Any]) -> ToolResult:
        from bot.files.service import FileService, FileServiceError

        rel = str(args.get("path", ""))
        try:
            entries = FileService.for_team(self.ctx.root, self.ctx.team_id).list_dir(rel)
        except FileServiceError as exc:
            raise ToolExecutionError(str(exc)) from exc
        lines = [
            f"{'[dir]' if e.is_dir else '[file]'} {e.path}"
            + (f" ({e.size} B)" if e.size is not None else "")
            for e in entries
        ]
        return ToolResult(True, "\n".join(lines) or "(leer)", {"count": len(entries)})

    def _tool_git_status(self, args: dict[str, Any]) -> ToolResult:
        from bot.git_svc.service import GitService, GitServiceError

        try:
            out = GitService.for_team(self.ctx.root, self.ctx.team_id).status()
        except GitServiceError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return ToolResult(True, out or "(clean)")

    def _tool_git_commit(self, args: dict[str, Any]) -> ToolResult:
        from bot.git_svc.service import GitService, GitServiceError

        message = str(args.get("message", "Agent commit"))
        try:
            out = GitService.for_team(self.ctx.root, self.ctx.team_id).commit(message)
        except GitServiceError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return ToolResult(True, out)

    def _tool_qdrant_search(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query", ""))
        collection_raw = str(args.get("collection", "project"))
        limit = int(args.get("limit", 5))
        if not query.strip():
            raise ToolExecutionError("query fehlt")
        from bot.runtime.agent_tools import validate_qdrant_collection

        try:
            collection = validate_qdrant_collection(self.ctx.agent, collection_raw)
        except ValueError as exc:
            raise ToolExecutionError(str(exc)) from exc
        try:
            from bot.channel.satellite import channel_rpc, is_satellite_root

            if is_satellite_root(self.ctx.root):
                data = channel_rpc(
                    self.ctx.root,
                    "qdrant.search",
                    {
                        "team_id": self.ctx.team_id,
                        "query": query,
                        "collection": collection,
                        "limit": limit,
                    },
                )
                hits = data.get("hits", [])
            else:
                from bot.qdrant.service import QdrantService

                service = QdrantService.from_root(self.ctx.root)
                hits = service.search(
                    self.ctx.team_id, collection, query, limit=limit
                )
        except Exception as exc:
            raise ToolExecutionError(str(exc)) from exc
        lines = []
        for h in hits:
            text = (h.get("payload") or {}).get("text", "")[:400]
            lines.append(f"score={h.get('score', 0):.3f} {text}")
        return ToolResult(True, "\n---\n".join(lines) or "(keine Treffer)", {"hits": len(hits)})

    def _tool_browser_open(self, args: dict[str, Any]) -> ToolResult:
        url = str(args.get("url", ""))
        if not url.startswith(("http://", "https://")):
            raise ToolExecutionError("url muss mit http(s) beginnen")
        try:
            from bot.channel.satellite import channel_rpc, is_satellite_root

            if is_satellite_root(self.ctx.root):
                data = channel_rpc(
                    self.ctx.root,
                    "browser.open",
                    {
                        "team_id": self.ctx.team_id,
                        "url": url,
                        "max_chars": 8000,
                    },
                    timeout_seconds=180.0,
                )
                info = data.get("info", {})
                text = str(data.get("body_text", ""))
            else:
                from bot.browser.service import BrowserService

                info = BrowserService.for_team(self.ctx.root, self.ctx.team_id).open_url_with_body(
                    url
                )
                text = str(info.get("body_text", ""))
        except Exception as exc:
            raise ToolExecutionError(str(exc)) from exc
        body = f"title={info.get('title')}\nurl={info.get('url')}\n\n{text}"
        return ToolResult(True, body, info)

    def _tool_story_read_scene(self, args: dict[str, Any]) -> ToolResult:
        from bot.story.db import StoryDB, StoryDBError

        chapter_id = str(args.get("chapter_id", ""))
        scene_id = str(args.get("scene_id", ""))
        try:
            meta, body = StoryDB(self.ctx.root, self.ctx.team_id).get_scene(
                chapter_id, scene_id
            )
        except StoryDBError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return ToolResult(
            True,
            f"version={meta.get('version')}\nstatus={meta.get('status')}\n\n{body}",
            meta,
        )

    def _tool_story_write_scene(self, args: dict[str, Any]) -> ToolResult:
        from bot.story.db import StoryDB, StoryDBError

        chapter_id = str(args.get("chapter_id", ""))
        scene_id = str(args.get("scene_id", ""))
        content = str(args.get("content", ""))
        version = int(args.get("expected_version", args.get("version", 1)))
        try:
            info = StoryDB(self.ctx.root, self.ctx.team_id).update_scene(
                chapter_id,
                scene_id,
                content,
                expected_version=version,
            )
        except StoryDBError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return ToolResult(
            True,
            f"Szene gespeichert, neue Version {info.version}",
            info.to_dict(),
        )

    def _tool_index_workspace(self, args: dict[str, Any]) -> ToolResult:
        try:
            from bot.channel.satellite import channel_rpc, is_satellite_root

            if is_satellite_root(self.ctx.root):
                data = channel_rpc(
                    self.ctx.root,
                    "qdrant.index_workspace",
                    {"team_id": self.ctx.team_id},
                )
                count = int(data.get("count", 0))
            else:
                from bot.qdrant.indexer import index_team_workspace

                count = index_team_workspace(self.ctx.root, self.ctx.team_id)
        except Exception as exc:
            raise ToolExecutionError(str(exc)) from exc
        return ToolResult(True, f"{count} Datei(en) in Qdrant (project) indexiert", {"count": count})


def tools_prompt_block(tool_names: frozenset[str] | None = None) -> str:
    names = tool_names or TOOL_NAMES
    lines = [
        "Verfügbare Tools (JSON, ein Tool pro Antwort wenn nötig):",
        '{"tool": "<name>", "args": {...}}',
        'Wenn fertig: {"done": true, "summary": "<Ergebnis>"}',
        "",
        "Tools:",
    ]
    docs = {
        "read_file": 'args: {"path": "rel/pfad"}',
        "write_file": 'args: {"path": "...", "content": "..."}',
        "list_files": 'args: {"path": ""}',
        "git_status": "args: {}",
        "git_commit": 'args: {"message": "..."}',
        "qdrant_search": 'args: {"query": "...", "collection": "project|background"}',
        "browser_open": 'args: {"url": "https://..."}',
        "story_read_scene": 'args: {"chapter_id": "...", "scene_id": "..."}',
        "story_write_scene": 'args: {"chapter_id", "scene_id", "content", "expected_version"}',
        "index_workspace": "args: {}",
    }
    for n in sorted(names):
        if n in docs:
            lines.append(f"- {n}: {docs[n]}")
    return "\n".join(lines)


_JSON_BLOCK = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL,
)
_JSON_LINE = re.compile(r"^\s*(\{.*\})\s*$", re.DOTALL)


def parse_agent_response(text: str) -> dict[str, Any] | None:
    """Extrahiert ein JSON-Objekt (Tool-Aufruf oder done) aus der LLM-Antwort."""
    text = text.strip()
    for pattern in (_JSON_BLOCK, _JSON_LINE):
        m = pattern.search(text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    if text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return None


def run_tool_loop(
    ctx: HandlerContext,
    *,
    system_prompt: str,
    user_content: str,
    task_category: str,
    tools: frozenset[str] | None = None,
    max_steps: int = 6,
) -> str:
    """LLM-Schleife mit Tool-Ausführung; gibt finale Zusammenfassung zurück."""
    toolkit = AgentToolkit(ctx)
    allowed = tools or TOOL_NAMES
    sys = f"{system_prompt}\n\n{tools_prompt_block(allowed)}"
    messages: list[dict[str, str]] = [
        {"role": "system", "content": sys},
        {"role": "user", "content": user_content},
    ]
    category = task_category
    model = ctx.llm_stack.router.resolve(category, role=ctx.role)
    fallbacks = ctx.llm_stack.router.fallbacks(category, role=ctx.role)

    for _step in range(max_steps):
        raw = ctx.llm_stack.client.complete(
            model, messages, fallbacks=fallbacks or None
        )
        parsed = parse_agent_response(raw)
        if parsed is None:
            return raw
        if parsed.get("done"):
            summary = str(parsed.get("summary", raw))
            return summary
        tool_name = parsed.get("tool")
        if not tool_name:
            return raw
        if tool_name not in allowed:
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"Tool '{tool_name}' nicht erlaubt. Nutze ein anderes Tool oder done.",
                }
            )
            continue
        args = parsed.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        result = toolkit.execute(str(tool_name), args)
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Tool-Ergebnis ({tool_name}, ok={result.ok}):\n{result.output[:10000]}"
                ),
            }
        )

    return messages[-1]["content"] if messages else ""
