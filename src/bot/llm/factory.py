"""LLM-Stack aus Runtime-Config erzeugen."""

from __future__ import annotations

from dataclasses import dataclass

from bot.config.models import RuntimeConfig
from bot.llm.client import LiteLLMClient, LlmClient, StubLlmClient
from bot.llm.router import ModelRouter


@dataclass
class LlmStack:
    router: ModelRouter
    client: LlmClient


def build_llm_stack(config: RuntimeConfig) -> LlmStack:
    router = ModelRouter(config.task_models)
    llm_cfg = config.system.system.llm

    if not llm_cfg.enabled:
        return LlmStack(router=router, client=StubLlmClient())

    client: LlmClient = LiteLLMClient(
        api_base=llm_cfg.api_base,
        secret_ref=llm_cfg.secret_ref,
        max_retries=llm_cfg.max_retries,
        retry_backoff_seconds=llm_cfg.retry_backoff_seconds,
        timeout_seconds=llm_cfg.timeout_seconds,
    )
    return LlmStack(router=router, client=client)
