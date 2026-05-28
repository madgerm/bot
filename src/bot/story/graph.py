"""Beziehungs-Graph als Mermaid-Diagramm."""

from __future__ import annotations

from bot.story.db import StoryDB


def relationships_mermaid(db: StoryDB) -> str:
    graph = db.build_relationship_graph()
    lines = ["flowchart LR"]
    for node in graph["nodes"]:
        nid = _mermaid_id(node["id"])
        label = node["label"].replace('"', "'")
        role = node.get("role", "")
        lines.append(f'  {nid}["{label}"')
        if role:
            lines[-1] = lines[-1][:-1] + f"<br/><small>{role}</small>\"]"
        else:
            lines[-1] += '"]'
    for edge in graph["edges"]:
        fr = _mermaid_id(edge["from"])
        to = _mermaid_id(edge["to"])
        lbl = edge.get("label", "").replace('"', "'")
        if lbl:
            lines.append(f"  {fr} -->|{lbl}| {to}")
        else:
            lines.append(f"  {fr} --> {to}")
    if len(graph["nodes"]) == 0:
        lines.append('  empty["Noch keine Charaktere"]')
    return "\n".join(lines)


def _mermaid_id(raw: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in raw)
