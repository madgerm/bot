"""LLM-Auflösung pro Agent (Override vor Rollen-Routing)."""

from __future__ import annotations

from bot.config.models import AgentBlock
from bot.llm import LlmStack


def resolve_agent_model(
    llm_stack: LlmStack,
    *,
    role: str,
    task_category: str,
    agent: AgentBlock | None = None,
    message_model_override: str | None = None,
) -> tuple[str, list[str]]:
    """Modell + Fallbacks: Agent.llm_model > Agent.task_categories[0] > Kategorie > Rolle."""
    if message_model_override and message_model_override.strip():
        return message_model_override.strip(), []

    if agent is not None and agent.llm_model and agent.llm_model.strip():
        return agent.llm_model.strip(), []

    router = llm_stack.router
    if agent is not None and agent.task_categories:
        cat = agent.task_categories[0].strip()
        if cat:
            return router.resolve(cat, role=role), router.fallbacks(cat, role=role)

    return router.resolve(task_category, role=role), router.fallbacks(task_category, role=role)
