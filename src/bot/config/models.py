"""Pydantic-Modelle für system.json, Teams und Agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AuthUser(BaseModel):
    username: str
    password: str


class AuthConfig(BaseModel):
    enabled: bool = False
    users: list[AuthUser] = Field(default_factory=list)


class CommunicationConfig(BaseModel):
    mode: Literal["direct", "broker"] = "direct"
    inbox_base: str = "teams/{team_id}/agents/{agent_id}/inbox"


class PollingConfig(BaseModel):
    interval_seconds: float = Field(default=5.0, gt=0)


class LlmConfig(BaseModel):
    enabled: bool = False
    provider: str = "litellm"
    api_base: str = "http://127.0.0.1:4000"
    secret_ref: str | None = None
    max_retries: int = Field(default=3, ge=1)
    retry_backoff_seconds: float = Field(default=1.0, ge=0)
    timeout_seconds: float = Field(default=120.0, gt=0)


class SystemBlock(BaseModel):
    name: str
    host: str = "127.0.0.1"
    auth: AuthConfig = Field(default_factory=AuthConfig)
    communication: CommunicationConfig = Field(default_factory=CommunicationConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    llm: LlmConfig = Field(default_factory=LlmConfig)


class EmbeddingConfig(BaseModel):
    provider: Literal["hash", "litellm"] = "hash"
    model: str | None = None
    vector_size: int = Field(default=384, ge=8)


class QdrantGlobalConfig(BaseModel):
    enabled: bool = False
    url: str = "http://127.0.0.1:6333"
    secret_ref: str | None = None
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    timeout_seconds: float = Field(default=30.0, gt=0)


class PlaywrightGlobalConfig(BaseModel):
    mode: Literal["local", "remote"] = "local"
    ws_endpoints: list[str] = Field(default_factory=list)
    base_host: str | None = None
    secret_ref: str | None = None
    headless: bool = True
    timeout_seconds: float = Field(default=60.0, gt=0)


class SystemConfig(BaseModel):
    """Inhalt von config/system.json."""

    system: SystemBlock
    qdrant_global: QdrantGlobalConfig | None = None
    playwright_global: PlaywrightGlobalConfig | None = None


class TaskModelEntry(BaseModel):
    default: str
    alternatives: list[str] = Field(default_factory=list)


class TaskModelsConfig(BaseModel):
    """Inhalt von config/task_models.json."""

    task_models: dict[str, TaskModelEntry]

    @field_validator("task_models")
    @classmethod
    def non_empty(cls, value: dict[str, TaskModelEntry]) -> dict[str, TaskModelEntry]:
        if not value:
            raise ValueError("task_models darf nicht leer sein")
        return value


class TeamBlock(BaseModel):
    id: str
    name: str
    orchestrator_id: str
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not all(c.isalnum() or c in "-_" for c in normalized):
            raise ValueError(
                f"Ungültige Team-ID '{value}' (erlaubt: Buchstaben, Ziffern, -, _)"
            )
        return normalized


class TeamConfig(BaseModel):
    """Inhalt von teams/<slug>/team.json."""

    team: TeamBlock


class AgentBlock(BaseModel):
    id: str
    role: Literal["orchestrator", "worker", "reviewer"] = "worker"
    enabled: bool = True
    interval_seconds: float | None = None

    @field_validator("id")
    @classmethod
    def non_empty_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("agent.id darf nicht leer sein")
        return normalized


class AgentConfig(BaseModel):
    """Inhalt von teams/<slug>/agents/<id>/agent.json."""

    agent: AgentBlock


class RuntimeConfig(BaseModel):
    """Zusammengeführte Laufzeit-Konfiguration."""

    system: SystemConfig
    task_models: TaskModelsConfig | None
    teams: dict[str, TeamBundle]


class TeamBundle(BaseModel):
    team: TeamConfig
    agents: dict[str, AgentConfig]

    def orchestrator(self) -> AgentConfig | None:
        orch_id = self.team.team.orchestrator_id
        return self.agents.get(orch_id)
