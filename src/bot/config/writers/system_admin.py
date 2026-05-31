"""Lesen/Schreiben von config/system.json (Panel)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from bot.config.models import (
    ChannelHubConfig,
    LlmConfig,
    LlmProxyConfig,
    PlaywrightGlobalConfig,
    PollingConfig,
    QdrantGlobalConfig,
    QdrantReindexConfig,
    SystemConfig,
    WebhooksGlobalConfig,
)
from bot.config.writers import (
    ConfigWriterError,
    atomic_write_json,
    load_json_file,
    relative_config_path,
)
from bot.config.writers.audit import log_config_change


class SystemAdminError(ConfigWriterError):
    pass


def system_config_path(root: Path) -> Path:
    return root / "config" / "system.json"


def env_var_is_set(name: str | None) -> bool:
    if not name or not str(name).strip():
        return False
    return bool(os.environ.get(str(name).strip()))


def load_system_config_admin(root: Path) -> SystemConfig:
    try:
        return SystemConfig.model_validate(load_json_file(system_config_path(root)))
    except ValidationError as exc:
        raise SystemAdminError(str(exc)) from exc


def save_system_config_admin(root: Path, cfg: SystemConfig, *, actor: str, section: str) -> None:
    try:
        SystemConfig.model_validate(cfg.model_dump(mode="json"))
    except ValidationError as exc:
        raise SystemAdminError(str(exc)) from exc
    atomic_write_json(
        system_config_path(root),
        cfg.model_dump(mode="json", exclude_none=True),
    )
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, system_config_path(root)),
        action=f"system_{section}",
        details={"section": section},
    )


def _merge(root: Path, mutator) -> SystemConfig:
    cfg = load_system_config_admin(root)
    try:
        return mutator(cfg)
    except ValidationError as exc:
        raise SystemAdminError(str(exc)) from exc


def save_llm_section(
    root: Path,
    *,
    actor: str,
    enabled: bool,
    mode: Literal["direct", "proxy", "channel"],
    api_base: str,
    secret_ref: str | None,
    max_retries: int,
    retry_backoff: float,
    timeout_seconds: float,
    proxy_base_url: str,
    proxy_token_env: str,
    hub_relay_url: str,
    hub_relay_room: str,
    hub_token_env: str,
    use_hub: bool,
) -> None:
    def mut(cfg: SystemConfig) -> SystemConfig:
        proxy = None
        if mode == "proxy" and proxy_base_url.strip():
            proxy = LlmProxyConfig(
                base_url=proxy_base_url.strip(),
                token_env=proxy_token_env.strip() or "BOT_LLM_PROXY_TOKEN",
            )
        hub = None
        if use_hub and hub_relay_url.strip():
            hub = ChannelHubConfig(
                relay_url=hub_relay_url.strip(),
                relay_room=hub_relay_room.strip() or "default",
                token_env=hub_token_env.strip() or "BOT_RELAY_TOKEN",
            )
        llm = LlmConfig(
            enabled=enabled,
            mode=mode,
            api_base=api_base.strip() or "http://127.0.0.1:4000",
            secret_ref=(secret_ref or "").strip() or None,
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff,
            timeout_seconds=timeout_seconds,
            proxy=proxy,
            hub=hub,
        )
        block = cfg.system.model_copy(update={"llm": llm})
        return cfg.model_copy(update={"system": block})

    cfg = _merge(root, mut)
    save_system_config_admin(root, cfg, actor=actor, section="llm")


def save_qdrant_section(
    root: Path,
    *,
    actor: str,
    enabled: bool,
    url: str,
    secret_ref: str | None,
    embedding_provider: Literal["hash", "litellm"],
    embedding_model: str | None,
    vector_size: int,
    timeout_seconds: float,
    reindex_enabled: bool,
    reindex_interval: float,
    watch_workspace: bool,
    watch_interval: float,
    debounce_seconds: float,
    include_crawl: bool,
) -> None:
    def mut(cfg: SystemConfig) -> SystemConfig:
        from bot.config.models import EmbeddingConfig

        qdrant = QdrantGlobalConfig(
            enabled=enabled,
            url=url.strip() or "http://127.0.0.1:6333",
            secret_ref=(secret_ref or "").strip() or None,
            embedding=EmbeddingConfig(
                provider=embedding_provider,
                model=embedding_model.strip() or None,
                vector_size=vector_size,
            ),
            timeout_seconds=timeout_seconds,
            reindex=QdrantReindexConfig(
                enabled=reindex_enabled,
                interval_seconds=reindex_interval,
                watch_workspace=watch_workspace,
                watch_interval_seconds=watch_interval,
                debounce_seconds=debounce_seconds,
                include_crawl=include_crawl,
            ),
        )
        return cfg.model_copy(update={"qdrant_global": qdrant})

    cfg = _merge(root, mut)
    save_system_config_admin(root, cfg, actor=actor, section="qdrant")


def save_playwright_section(
    root: Path,
    *,
    actor: str,
    mode: Literal["local", "remote"],
    headless: bool,
    timeout_seconds: float,
    ws_endpoints: list[str],
    secret_ref: str | None,
) -> None:
    def mut(cfg: SystemConfig) -> SystemConfig:
        pw = PlaywrightGlobalConfig(
            mode=mode,
            headless=headless,
            timeout_seconds=timeout_seconds,
            ws_endpoints=ws_endpoints,
            secret_ref=(secret_ref or "").strip() or None,
        )
        return cfg.model_copy(update={"playwright_global": pw})

    cfg = _merge(root, mut)
    save_system_config_admin(root, cfg, actor=actor, section="playwright")


def save_polling_section(
    root: Path,
    *,
    actor: str,
    interval_seconds: float,
    inbox_watch_seconds: float,
    worker_mode: Literal["thread", "process"],
) -> None:
    def mut(cfg: SystemConfig) -> SystemConfig:
        polling = PollingConfig(
            interval_seconds=interval_seconds,
            inbox_watch_seconds=inbox_watch_seconds,
            worker_mode=worker_mode,
        )
        block = cfg.system.model_copy(update={"polling": polling})
        return cfg.model_copy(update={"system": block})

    cfg = _merge(root, mut)
    save_system_config_admin(root, cfg, actor=actor, section="polling")


def save_webhooks_section(
    root: Path,
    *,
    actor: str,
    enabled: bool,
    secret_ref: str,
    path_prefix: str,
) -> None:
    def mut(cfg: SystemConfig) -> SystemConfig:
        wh = WebhooksGlobalConfig(
            enabled=enabled,
            secret_ref=secret_ref.strip() or "BOT_WEBHOOK_SECRET",
            path_prefix=path_prefix.strip() or "/api/v1/webhooks",
        )
        return cfg.model_copy(update={"webhooks_global": wh})

    cfg = _merge(root, mut)
    save_system_config_admin(root, cfg, actor=actor, section="webhooks")


def secret_status_map(cfg: SystemConfig) -> dict[str, bool]:
    refs: list[str | None] = [
        cfg.system.llm.secret_ref,
        cfg.qdrant_global.secret_ref if cfg.qdrant_global else None,
        cfg.playwright_global.secret_ref if cfg.playwright_global else None,
        cfg.webhooks_global.secret_ref if cfg.webhooks_global else None,
    ]
    if cfg.system.llm.proxy:
        refs.append(cfg.system.llm.proxy.token_env)
    if cfg.system.llm.hub:
        refs.append(cfg.system.llm.hub.token_env)
    out: dict[str, bool] = {}
    for ref in refs:
        if ref and ref not in out:
            out[ref] = env_var_is_set(ref)
    return out
