"""FastAPI-App für den Team-Runner (Remote-API)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException

from bot.config import ConfigLoadError
from bot.health import collect_health
from bot.hosts.client import LocalTeamHost
from bot.team_api.auth import auth_dependency
from bot.team_api.channel_ws import router as channel_ws_router
from bot.team_api.serialize import dashboard_to_dict


def create_team_api_app(root: Path | str) -> FastAPI:
    root_path = Path(root).resolve()
    require_auth = auth_dependency(root_path)
    host = LocalTeamHost(host_id="api", label="Team-API", root=root_path)

    app = FastAPI(
        title="Bot Team-Runner API",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.root = root_path
    app.include_router(channel_ws_router)

    @app.get("/api/v1/health")
    def health(_: None = Depends(require_auth)):
        return collect_health(root_path)

    @app.get("/api/v1/info")
    def info(_: None = Depends(require_auth)):
        return {"system_name": host.system_name()}

    @app.get("/api/v1/teams")
    def list_teams(_: None = Depends(require_auth)):
        return {"teams": host.list_teams()}

    @app.get("/api/v1/teams/{team_id}/dashboard")
    def team_dashboard(team_id: str, _: None = Depends(require_auth)):
        try:
            dashboard = host.get_dashboard(team_id)
        except ConfigLoadError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return dashboard_to_dict(dashboard)

    return app
