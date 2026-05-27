"""HTTP-API des Team-Runners (für Remote-Zugriff durch das Web-Panel)."""

from bot.team_api.app import create_team_api_app

__all__ = ["create_team_api_app"]
