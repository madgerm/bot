"""System- und Task-Models Admin."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bot.config.writers.system_admin import (
    SystemAdminError,
    load_system_config_admin,
    save_llm_section,
)
from bot.config.writers.task_models_admin import (
    load_task_models_admin,
    parse_models_from_form,
    save_task_models_admin,
)


@pytest.fixture
def cfg_root(tmp_path: Path) -> Path:
    src = Path(__file__).resolve().parents[1] / "config" / "system.json"
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "system.json").write_text(src.read_text(encoding="utf-8"))
    (tmp_path / "config" / "task_models.json").write_text(
        json.dumps(
            {
                "task_models": {
                    "planning": {"default": "m1", "alternatives": []},
                    "coding": {"default": "m2", "alternatives": ["m3"]},
                }
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_save_llm_proxy_requires_base(cfg_root: Path) -> None:
    with pytest.raises(SystemAdminError):
        save_llm_section(
            cfg_root,
            actor="admin",
            enabled=True,
            mode="proxy",
            api_base="http://127.0.0.1:4000",
            secret_ref=None,
            max_retries=3,
            retry_backoff=1.0,
            timeout_seconds=120.0,
            proxy_base_url="",
            proxy_token_env="BOT_LLM_PROXY_TOKEN",
            hub_relay_url="",
            hub_relay_room="default",
            hub_token_env="BOT_RELAY_TOKEN",
            use_hub=False,
        )


def test_save_llm_proxy_ok(cfg_root: Path) -> None:
    save_llm_section(
        cfg_root,
        actor="admin",
        enabled=True,
        mode="proxy",
        api_base="http://127.0.0.1:4000",
        secret_ref="LITELLM_API_KEY",
        max_retries=3,
        retry_backoff=1.0,
        timeout_seconds=120.0,
        proxy_base_url="http://panel:8080",
        proxy_token_env="BOT_LLM_PROXY_TOKEN",
        hub_relay_url="",
        hub_relay_room="default",
        hub_token_env="BOT_RELAY_TOKEN",
        use_hub=False,
    )
    cfg = load_system_config_admin(cfg_root)
    assert cfg.system.llm.mode == "proxy"
    assert cfg.system.llm.proxy is not None
    assert cfg.system.llm.proxy.base_url == "http://panel:8080"


def test_task_models_roundtrip(cfg_root: Path) -> None:
    parsed = parse_models_from_form(
        {
            "model_planning": "ollama/a",
            "alt_planning": "",
            "model_coding": "ollama/b",
            "alt_coding": "x, y",
        }
    )
    save_task_models_admin(cfg_root, parsed, actor="admin")
    loaded = load_task_models_admin(cfg_root)
    assert loaded.task_models["coding"].alternatives == ["x", "y"]
