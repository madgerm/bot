import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot.config import load_runtime_config
from bot.config.models import TaskModelsConfig
from bot.llm import LiteLLMClient, ModelRouter, StubLlmClient, build_llm_stack
from bot.llm.client import LlmError


def test_model_router_resolve_override() -> None:
    task_models = TaskModelsConfig.model_validate(
        {
            "task_models": {
                "coding": {"default": "model-a", "alternatives": ["model-b"]},
            }
        }
    )
    router = ModelRouter(task_models)
    assert router.resolve("coding", role="worker") == "model-a"
    assert router.resolve("coding", role="worker", override="custom/x") == "custom/x"
    assert router.fallbacks("coding", role="worker") == ["model-b"]


def test_stub_client() -> None:
    client = StubLlmClient()
    out = client.complete("test-model", [{"role": "user", "content": "Hi"}])
    assert "[llm-stub" in out


def test_litellm_client_retry_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_completion(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "primary":
            raise RuntimeError("primary down")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="OK from fallback"))]
        )

    monkeypatch.setattr("litellm.completion", fake_completion)

    client = LiteLLMClient(
        api_base="http://127.0.0.1:4000",
        secret_ref=None,
        max_retries=1,
        retry_backoff_seconds=0,
        timeout_seconds=5,
    )
    result = client.complete(
        "primary",
        [{"role": "user", "content": "test"}],
        fallbacks=["fallback-model"],
    )
    assert result == "OK from fallback"
    assert "primary" in calls
    assert "fallback-model" in calls


def test_litellm_all_fail_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "litellm.completion",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
    )
    client = LiteLLMClient(
        api_base=None,
        secret_ref=None,
        max_retries=1,
        retry_backoff_seconds=0,
        timeout_seconds=5,
    )
    with pytest.raises(LlmError):
        client.complete("m1", [{"role": "user", "content": "x"}])


def test_build_llm_stack_disabled(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "system.json").write_text(
        json.dumps({"system": {"name": "t", "llm": {"enabled": False}}}),
        encoding="utf-8",
    )
    config = load_runtime_config(tmp_path)
    stack = build_llm_stack(config)
    from bot.llm import StubLlmClient

    assert isinstance(stack.client, StubLlmClient)


def test_handlers_use_stub_in_pipeline(runtime_project: Path) -> None:
    from bot.messages import MessageService
    from bot.runtime import Supervisor

    service = MessageService(runtime_project)
    service.send(
        team_id="alpha",
        from_agent="orchestrator",
        to_agent="orchestrator",
        subject="LLM Stub Test",
        content="Inhalt",
    )
    supervisor = Supervisor(runtime_project)
    supervisor.run_until_idle(team_ids=["alpha"])

    inbox = service.list_inbox("alpha", "orchestrator")
    result = next(m for m in inbox if m.type == "delegation_result")
    assert "[llm-stub" in result.content or "--- Review ---" in result.content
