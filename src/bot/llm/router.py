"""Task-basiertes Model-Routing aus config/task_models.json."""

from __future__ import annotations

from bot.config.models import TaskModelsConfig

ROLE_DEFAULT_CATEGORY: dict[str, str] = {
    "orchestrator": "planning",
    "worker": "coding",
    "reviewer": "review",
}


class ModelRouter:
    def __init__(self, task_models: TaskModelsConfig | None) -> None:
        self._models = task_models.task_models if task_models else {}

    def resolve(
        self,
        task_category: str | None,
        *,
        role: str,
        override: str | None = None,
    ) -> str:
        if override:
            return override
        category = task_category or ROLE_DEFAULT_CATEGORY.get(role, "planning")
        entry = self._models.get(category)
        if entry is None:
            if self._models:
                first = next(iter(self._models.values()))
                return first.default
            return "ollama/llama3.2"
        return entry.default

    def fallbacks(self, task_category: str | None, *, role: str) -> list[str]:
        category = task_category or ROLE_DEFAULT_CATEGORY.get(role, "planning")
        entry = self._models.get(category)
        if entry is None:
            return []
        return list(entry.alternatives)
