"""Kontext für Agent-Handler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot.config.models import AgentBlock
from bot.llm import LlmStack


@dataclass
class HandlerContext:
    root: Path
    team_id: str
    agent_id: str
    role: str
    llm_stack: LlmStack
    agent: AgentBlock | None = None
