"""LLM-Proxy: Team-Runner → Web-Panel → LiteLLM."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from bot.config import load_runtime_config
from bot.llm import build_llm_stack
from bot.llm.panel_proxy_client import PanelProxyLlmClient
from bot.web import create_app


def _write_proxy_runner_config(tmp_path: Path, panel_url: str) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "system.json").write_text(
        json.dumps(
            {
                "system": {
                    "name": "runner",
                    "llm": {
                        "enabled": True,
                        "mode": "proxy",
                        "proxy": {
                            "base_url": panel_url,
                            "token_env": "BOT_LLM_PROXY_TOKEN",
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (config_dir / "task_models.json").write_text(
        json.dumps(
            {
                "task_models": {
                    "planning": {"default": "stub/p", "alternatives": []},
                }
            }
        ),
        encoding="utf-8",
    )


def test_build_llm_stack_proxy_mode(tmp_path: Path) -> None:
    _write_proxy_runner_config(tmp_path, "http://panel.local:8080")
    stack = build_llm_stack(load_runtime_config(tmp_path))
    assert isinstance(stack.client, PanelProxyLlmClient)


def test_panel_proxy_client_calls_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_LLM_PROXY_TOKEN", "test-token")
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"content": "Hallo vom Panel"}

    def fake_post(url, json, headers):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResponse()

    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.post = fake_post
    monkeypatch.setattr("httpx.Client", lambda **kwargs: fake_client)

    client = PanelProxyLlmClient(
        base_url="http://192.168.1.5:8080",
        token_env="BOT_LLM_PROXY_TOKEN",
        max_retries=1,
        retry_backoff_seconds=0,
        timeout_seconds=30,
    )
    out = client.complete("ollama/test", [{"role": "user", "content": "Hi"}])
    assert out == "Hallo vom Panel"
    assert captured["url"] == "http://192.168.1.5:8080/api/v1/llm/complete"
    assert captured["headers"]["Authorization"] == "Bearer test-token"


def test_llm_proxy_api_endpoint(web_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_LLM_PROXY_TOKEN", "proxy-secret")
    (web_project / "config" / "team_api.json").write_text(
        json.dumps({"token_env": "BOT_LLM_PROXY_TOKEN"}),
        encoding="utf-8",
    )
    system = json.loads((web_project / "config" / "system.json").read_text(encoding="utf-8"))
    system["system"]["llm"] = {
        "enabled": True,
        "mode": "direct",
        "api_base": "http://127.0.0.1:4000",
        "secret_ref": None,
        "max_retries": 1,
        "retry_backoff_seconds": 0,
        "timeout_seconds": 5,
    }
    (web_project / "config" / "system.json").write_text(
        json.dumps(system), encoding="utf-8"
    )

    def fake_complete(*args, **kwargs):
        return "Antwort über Panel"

    monkeypatch.setattr(
        "bot.web.llm_proxy_routes.complete_via_local_llm",
        lambda *a, **k: fake_complete(),
    )

    client = TestClient(create_app(web_project))
    r = client.post(
        "/api/v1/llm/complete",
        json={
            "model": "ollama/x",
            "messages": [{"role": "user", "content": "test"}],
            "fallbacks": [],
        },
        headers={"Authorization": "Bearer proxy-secret"},
    )
    assert r.status_code == 200
    assert r.json()["content"] == "Antwort über Panel"


def test_llm_proxy_api_rejects_bad_token(web_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOT_LLM_PROXY_TOKEN", "right")
    (web_project / "config" / "team_api.json").write_text(
        json.dumps({"token_env": "BOT_LLM_PROXY_TOKEN"}),
        encoding="utf-8",
    )
    client = TestClient(create_app(web_project))
    r = client.post(
        "/api/v1/llm/complete",
        json={"model": "m", "messages": [{"role": "user", "content": "x"}]},
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 403
