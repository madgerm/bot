"""LLM-Stack aus Runtime-Config erzeugen."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot.config.models import RuntimeConfig
from bot.llm.channel_client import ChannelLlmClient
from bot.llm.client import LiteLLMClient, LlmClient, StubLlmClient
from bot.llm.panel_proxy_client import PanelProxyLlmClient
from bot.llm.router import ModelRouter


@dataclass
class LlmStack:
    router: ModelRouter
    client: LlmClient


def build_llm_stack(config: RuntimeConfig, *, root: Path | str | None = None) -> LlmStack:
    router = ModelRouter(config.task_models)
    llm_cfg = config.system.system.llm

    if not llm_cfg.enabled:
        return LlmStack(router=router, client=StubLlmClient())

    if llm_cfg.mode == "channel":
        if root is None:
            raise ValueError("build_llm_stack: root erforderlich für llm.mode=channel")
        client: LlmClient = ChannelLlmClient(
            root=root,
            timeout_seconds=llm_cfg.timeout_seconds,
        )
    elif llm_cfg.mode == "proxy":
        assert llm_cfg.proxy is not None
        client = PanelProxyLlmClient(
            base_url=llm_cfg.proxy.base_url,
            token_env=llm_cfg.proxy.token_env,
            max_retries=llm_cfg.max_retries,
            retry_backoff_seconds=llm_cfg.retry_backoff_seconds,
            timeout_seconds=llm_cfg.timeout_seconds,
        )
    else:
        client = LiteLLMClient(
            api_base=llm_cfg.api_base,
            secret_ref=llm_cfg.secret_ref,
            max_retries=llm_cfg.max_retries,
            retry_backoff_seconds=llm_cfg.retry_backoff_seconds,
            timeout_seconds=llm_cfg.timeout_seconds,
        )
    return LlmStack(router=router, client=client)
