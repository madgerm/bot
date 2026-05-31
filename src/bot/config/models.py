"""Pydantic-Modelle für system.json, Teams und Agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AuthUser(BaseModel):
    username: str
    password: str


class AuthConfig(BaseModel):
    enabled: bool = False
    users: list[AuthUser] = Field(default_factory=list)


class MultiMachineConfig(BaseModel):
    """Multi-Machine nur über gemeinsame Datei-Inboxen (NFS/SSH-Mount), kein Redis."""

    enabled: bool = False
    shared_inbox_base: str | None = None
    """Optionaler Pfad-Template wenn Inboxen auf einem Shared Volume liegen."""


class CommunicationConfig(BaseModel):
    mode: Literal["direct"] = "direct"
    inbox_base: str = "teams/{team_id}/agents/{agent_id}/inbox"
    multi_machine: MultiMachineConfig = Field(default_factory=MultiMachineConfig)


class PollingConfig(BaseModel):
    interval_seconds: float = Field(default=5.0, gt=0)
    """Fallback-Intervall wenn die Inbox unverändert ist (Idle-Gesundheitscheck)."""
    inbox_watch_seconds: float = Field(default=0.5, gt=0)
    """Intervall des Inbox-Watch-Threads (mtime); weckt den Loop bei neuer Datei."""
    worker_mode: Literal["thread", "process"] = "process"
    """thread = ein Thread pro Agent; process = eigener OS-Prozess (empfohlen)."""


class ChannelHubConfig(BaseModel):
    """Internet-Relay: Panel und Runner verbinden sich ausgehend."""

    relay_url: str
    """WebSocket-URL des Relays, z. B. wss://relay.example.com:9000/ws"""
    relay_room: str = "default"
    """Gemeinsamer Raum (Installation) — Panel und Runner müssen übereinstimmen."""
    token_env: str = "BOT_RELAY_TOKEN"


class LlmProxyConfig(BaseModel):
    """Team-Runner (VPS) → Web-Panel (LAN) → Ollama/LiteLLM."""

    base_url: str
    """URL des Web-Panels, z. B. http://192.168.1.10:8080"""
    token_env: str = "BOT_LLM_PROXY_TOKEN"
    """Bearer-Token (gleicher Wert wie Panel-Seite in team_api.json / .env)."""


class LlmConfig(BaseModel):
    enabled: bool = False
    provider: str = "litellm"
    mode: Literal["direct", "proxy", "channel"] = "direct"
    """direct: lokal; proxy: HTTP zum Panel; channel: Panel verbindet sich (Queue)."""
    api_base: str = "http://127.0.0.1:4000"
    secret_ref: str | None = None
    proxy: LlmProxyConfig | None = None
    hub: ChannelHubConfig | None = None
    """Optional: Internet-Relay statt direktem Panel↔Runner-WebSocket."""
    max_retries: int = Field(default=3, ge=1)
    retry_backoff_seconds: float = Field(default=1.0, ge=0)
    timeout_seconds: float = Field(default=120.0, gt=0)

    @model_validator(mode="after")
    def _validate_proxy_mode(self) -> LlmConfig:
        if self.mode == "proxy" and self.proxy is None:
            raise ValueError("llm.proxy ist erforderlich, wenn llm.mode=proxy")
        return self


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


class QdrantReindexConfig(BaseModel):
    """Automatischer Qdrant-Index: periodisch + Workspace-Watch (Hook bei Dateiänderung)."""

    enabled: bool = False
    """Vollständiger Reindex aller Teams in diesem Intervall (0 = nur Watch/Hooks)."""
    interval_seconds: float = Field(default=3600.0, ge=0)
    watch_workspace: bool = True
    watch_interval_seconds: float = Field(default=30.0, ge=1)
    debounce_seconds: float = Field(default=90.0, ge=1)
    include_crawl: bool = True


class QdrantGlobalConfig(BaseModel):
    enabled: bool = False
    url: str = "http://127.0.0.1:6333"
    secret_ref: str | None = None
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    timeout_seconds: float = Field(default=30.0, gt=0)
    reindex: QdrantReindexConfig = Field(default_factory=QdrantReindexConfig)


class PlaywrightGlobalConfig(BaseModel):
    mode: Literal["local", "remote"] = "local"
    ws_endpoints: list[str] = Field(default_factory=list)
    base_host: str | None = None
    secret_ref: str | None = None
    headless: bool = True
    timeout_seconds: float = Field(default=60.0, gt=0)


class WebhooksGlobalConfig(BaseModel):
    enabled: bool = True
    secret_ref: str = "BOT_WEBHOOK_SECRET"
    path_prefix: str = "/api/v1/webhooks"


class MediaChannelConfig(BaseModel):
    source: Literal["global", "custom"] = "global"
    provider: str | None = None
    api_base: str | None = None
    model: str | None = None
    endpoint: str | None = None
    voice_id: str | None = None
    secret_ref: str | None = None
    timeout_seconds: float = Field(default=60.0, gt=0)


class ImageGenerationConfig(BaseModel):
    source: Literal["global", "custom"] = "global"
    type: Literal["webhook", "selfhosted", "minimax"] = "webhook"
    url: str | None = None
    api_base: str | None = None
    model: str | None = None
    secret_ref: str | None = None
    default_aspect: str = "16:9"
    max_parallel: int = Field(default=2, ge=1)
    timeout_seconds: float = Field(default=180.0, gt=0)


class MediaGlobalConfig(BaseModel):
    vision: MediaChannelConfig = Field(default_factory=MediaChannelConfig)
    stt: MediaChannelConfig = Field(default_factory=MediaChannelConfig)
    tts: MediaChannelConfig = Field(default_factory=MediaChannelConfig)
    image_generation: ImageGenerationConfig = Field(default_factory=ImageGenerationConfig)


class DeploymentConfig(BaseModel):
    topology: Literal["single_user", "linux_user_per_team"] = "single_user"
    team_agent_scope: Literal["system", "user", "hybrid"] = "system"
    team_user_prefix: str = "team_"
    systemd_template: str = "bot-team@.service"


class SystemConfig(BaseModel):
    """Inhalt von config/system.json."""

    system: SystemBlock
    qdrant_global: QdrantGlobalConfig | None = None
    playwright_global: PlaywrightGlobalConfig | None = None
    webhooks_global: WebhooksGlobalConfig | None = None
    media_global: MediaGlobalConfig | None = None
    deployment: DeploymentConfig | None = None


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


class PipelineConfig(BaseModel):
    """Agent-IDs für die Standard-Pipeline (überschreibt Preset-Defaults)."""

    execute: str | None = None
    review: str | None = None
    document: str | None = None


class TeamBlock(BaseModel):
    id: str
    name: str
    orchestrator_id: str
    enabled: bool = True
    preset: Literal["generic", "demo", "coding", "story"] = "generic"

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
    pipeline: PipelineConfig | None = None


class AgentBlock(BaseModel):
    id: str
    role: Literal[
        "orchestrator",
        "worker",
        "reviewer",
        "story_writer",
        "story_reviewer",
        "coder",
        "tester",
        "documenter",
        "hours_checker",
    ] = "worker"
    enabled: bool = True
    interval_seconds: float | None = None
    display_name: str | None = None

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
