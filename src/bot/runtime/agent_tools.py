"""Tool- und Wissen-Auflösung pro Agent (agent.json + Rollen-Defaults)."""

from __future__ import annotations

from bot.config.models import AgentBlock
from bot.qdrant.collections import COLLECTION_SUFFIXES
from bot.runtime.tools import TOOL_NAMES

ROLE_DEFAULT_TOOLS: dict[str, frozenset[str]] = {
    "orchestrator": frozenset(
        {"read_file", "list_files", "qdrant_search", "index_workspace", "git_status"}
    ),
    "worker": frozenset(TOOL_NAMES),
    "reviewer": frozenset(
        {
            "read_file",
            "list_files",
            "qdrant_search",
            "story_read_scene",
            "git_status",
        }
    ),
    "documenter": frozenset(
        {"read_file", "write_file", "list_files", "git_status", "git_commit"}
    ),
    "story_writer": frozenset(TOOL_NAMES),
    "story_reviewer": frozenset(
        {
            "read_file",
            "list_files",
            "qdrant_search",
            "story_read_scene",
            "git_status",
        }
    ),
    "coder": frozenset(TOOL_NAMES),
    "tester": frozenset(
        {
            "read_file",
            "list_files",
            "qdrant_search",
            "story_read_scene",
            "git_status",
        }
    ),
    "hours_checker": frozenset({"browser_open"}),
}

# UI: (tool_id, deutsches Label)
TOOL_CHOICES: list[tuple[str, str]] = [
    ("read_file", "Dateien lesen"),
    ("write_file", "Dateien schreiben"),
    ("list_files", "Verzeichnis auflisten"),
    ("git_status", "Git-Status"),
    ("git_commit", "Git-Commit"),
    ("qdrant_search", "Wissenssuche (Qdrant)"),
    ("index_workspace", "Workspace indexieren"),
    ("browser_open", "Browser öffnen"),
    ("story_read_scene", "Story-Szene lesen"),
    ("story_write_scene", "Story-Szene schreiben"),
]

KNOWLEDGE_CHOICES: list[tuple[str, str]] = [
    ("project", "Projekt-Wissen"),
    ("background", "Hintergrund"),
    ("web", "Web-Crawl"),
]


def role_default_tools(role: str) -> frozenset[str]:
    return ROLE_DEFAULT_TOOLS.get(role, frozenset(TOOL_NAMES))


def resolve_allowed_tools(role: str, agent: AgentBlock | None) -> frozenset[str]:
    """Effektive Tool-Menge: Rollen-Default, optional eingeschränkt durch agent.json."""
    base = role_default_tools(role)
    if agent is None:
        return base
    if agent.tools_allow:
        allowed = frozenset(t for t in agent.tools_allow if t in TOOL_NAMES)
    else:
        allowed = base
    if agent.tools_deny:
        allowed = allowed - frozenset(agent.tools_deny)
    return allowed if allowed else base


def resolve_qdrant_collections(agent: AgentBlock | None) -> frozenset[str]:
    """Erlaubte Collection-Suffixe für qdrant_search."""
    if agent is None or not agent.qdrant_collections:
        return frozenset(COLLECTION_SUFFIXES)
    valid = frozenset(s for s in agent.qdrant_collections if s in COLLECTION_SUFFIXES)
    return valid if valid else frozenset(COLLECTION_SUFFIXES)


def agent_tools_summary(role: str, agent: AgentBlock | None) -> str:
    """Kurztext für Agent-Listen im Panel."""
    if agent is None:
        return "—"
    parts: list[str] = []
    if agent.tools_allow:
        parts.append(f"{len(agent.tools_allow)} erlaubt")
    else:
        parts.append("Rollen-Std.")
    if agent.tools_deny:
        parts.append(f"−{len(agent.tools_deny)}")
    eff = len(resolve_allowed_tools(role, agent))
    parts.append(f"{eff} aktiv")
    return " · ".join(parts)


def agent_knowledge_summary(agent: AgentBlock | None) -> str:
    if agent is None or not agent.qdrant_collections:
        return "alle"
    return ", ".join(agent.qdrant_collections)


def validate_qdrant_collection(agent: AgentBlock | None, collection: str) -> str:
    """Gibt Suffix zurück oder wirft ValueError."""
    suffix = collection.strip() or "project"
    allowed = resolve_qdrant_collections(agent)
    if suffix not in allowed:
        raise ValueError(
            f"Collection '{suffix}' nicht erlaubt (erlaubt: {', '.join(sorted(allowed))})"
        )
    return suffix
