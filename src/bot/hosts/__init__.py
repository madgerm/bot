"""Team-Host-Registry: lokal oder Remote-API."""

from bot.hosts.client import LocalTeamHost, RemoteTeamHost, TeamHostClient
from bot.hosts.registry import HostRegistry, TeamHostError

__all__ = [
    "HostRegistry",
    "LocalTeamHost",
    "RemoteTeamHost",
    "TeamHostClient",
    "TeamHostError",
]
