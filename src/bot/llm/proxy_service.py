"""LLM-Completion über lokales LiteLLM (Panel-Seite des Proxys)."""

from __future__ import annotations

from bot.config.models import RuntimeConfig
from bot.llm.client import LiteLLMClient, LlmError


def complete_via_local_llm(
    config: RuntimeConfig,
    *,
    model: str,
    messages: list[dict[str, str]],
    fallbacks: list[str] | None = None,
) -> str:
    """Panel-Host: direkter LiteLLM-Aufruf (Ollama/LiteLLM im LAN)."""
    llm_cfg = config.system.system.llm
    if not llm_cfg.enabled:
        raise LlmError(
            "LLM auf dem Panel deaktiviert (system.llm.enabled=false). "
            "Aktivieren und api_base auf erreichbares LiteLLM/Ollama setzen."
        )
    if llm_cfg.mode == "proxy":
        raise LlmError(
            "Panel darf für den LLM-Proxy nicht mode=proxy nutzen — bitte mode=direct."
        )
    client = LiteLLMClient(
        api_base=llm_cfg.api_base,
        secret_ref=llm_cfg.secret_ref,
        max_retries=llm_cfg.max_retries,
        retry_backoff_seconds=llm_cfg.retry_backoff_seconds,
        timeout_seconds=llm_cfg.timeout_seconds,
    )
    return client.complete(model, messages, fallbacks=fallbacks)
