"""API: Team-Runner → Web-Panel → LiteLLM/Ollama."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from bot.config import ConfigLoadError, load_runtime_config
from bot.llm.client import LlmError
from bot.llm.proxy_service import complete_via_local_llm
from bot.team_api.auth import auth_dependency


class LlmCompleteRequest(BaseModel):
    model: str
    messages: list[dict[str, str]]
    fallbacks: list[str] = Field(default_factory=list)


class LlmCompleteResponse(BaseModel):
    content: str
    model_used: str | None = None


def register_llm_proxy_routes(app: FastAPI, root: Path) -> None:
    """POST /api/v1/llm/complete — Bearer-Token (wie Team-API)."""
    require_auth = auth_dependency(root)

    @app.post("/api/v1/llm/complete", response_model=LlmCompleteResponse)
    def llm_complete(body: LlmCompleteRequest, _: None = Depends(require_auth)):
        try:
            config = load_runtime_config(root)
        except ConfigLoadError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        llm = config.system.system.llm
        if llm.mode == "proxy":
            raise HTTPException(
                status_code=500,
                detail=(
                    "Panel-LLM ist auf mode=proxy — für den Proxy muss das Panel "
                    "llm.mode=direct nutzen (Ollama/LiteLLM lokal erreichbar)."
                ),
            )

        try:
            content = complete_via_local_llm(
                config,
                model=body.model,
                messages=body.messages,
                fallbacks=body.fallbacks or None,
            )
        except LlmError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return LlmCompleteResponse(content=content, model_used=body.model)
