"""Lesen/Schreiben von team_hosts.json und team_api.json (Panel)."""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from bot.config import ConfigLoadError, load_runtime_config
from bot.config.writers import (
    ConfigWriterError,
    atomic_write_json,
    load_json_file,
    relative_config_path,
)
from bot.config.writers.audit import log_config_change
from bot.config.writers.system_admin import env_var_is_set, load_system_config_admin
from bot.hosts.models import TeamHostEntry, TeamHostsConfig
from bot.hosts.registry import load_team_hosts_config

_HOST_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,63}$")


class HostsAdminError(ConfigWriterError):
    pass


class TeamApiAdminConfig(BaseModel):
    token_env: str = "BOT_TEAM_API_TOKEN"
    teams: list[str] = Field(default_factory=list)


def team_hosts_path(root: Path) -> Path:
    return root / "config" / "team_hosts.json"


def team_api_path(root: Path) -> Path:
    return root / "config" / "team_api.json"


def validate_host_id(host_id: str) -> None:
    hid = host_id.strip()
    if not hid or not _HOST_ID_RE.match(hid):
        raise HostsAdminError(
            "Host-ID: 2–64 Zeichen, Buchstaben/Ziffern, optional . _ -"
        )


def load_hosts_admin(root: Path) -> TeamHostsConfig:
    try:
        return load_team_hosts_config(root)
    except Exception as exc:
        raise HostsAdminError(str(exc)) from exc


def _detach_teams_from_others(
    hosts: list[TeamHostEntry],
    *,
    keep_host_id: str,
    teams: list[str],
) -> list[TeamHostEntry]:
    """Entfernt Team-IDs von anderen Hosts (eindeutige Zuordnung)."""
    team_set = set(teams)
    if not team_set:
        return hosts
    out: list[TeamHostEntry] = []
    for h in hosts:
        if h.id == keep_host_id:
            out.append(h)
            continue
        remaining = [t for t in h.teams if t not in team_set]
        if remaining != h.teams:
            out.append(h.model_copy(update={"teams": remaining}))
        else:
            out.append(h)
    return out


def save_hosts_admin(root: Path, cfg: TeamHostsConfig, *, actor: str) -> None:
    try:
        cfg = TeamHostsConfig.model_validate(cfg.model_dump(mode="json"))
    except ValidationError as exc:
        raise HostsAdminError(str(exc)) from exc
    path = team_hosts_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, cfg.model_dump(mode="json"))
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, path),
        action="update",
        details={"hosts": len(cfg.hosts)},
    )


def get_host(cfg: TeamHostsConfig, host_id: str) -> TeamHostEntry | None:
    for h in cfg.hosts:
        if h.id == host_id:
            return h
    return None


def parse_teams_from_form(form: dict[str, str], team_ids: list[str]) -> list[str]:
    selected: list[str] = []
    for tid in team_ids:
        if form.get(f"team_{tid}") == "on":
            selected.append(tid)
    return selected


def entry_from_form(
    form: dict[str, str],
    *,
    team_ids: list[str],
    host_id: str | None = None,
) -> TeamHostEntry:
    hid = (host_id or form.get("host_id", "")).strip()
    validate_host_id(hid)
    mode_raw = form.get("mode", "local")
    mode: Literal["local", "remote"] = "remote" if mode_raw == "remote" else "local"
    label = form.get("label", hid).strip() or hid
    teams = parse_teams_from_form(form, team_ids)
    channel = form.get("channel") == "on"
    relay_url = form.get("relay_url", "").strip() or None
    relay_room = form.get("relay_room", "").strip() or None
    base_url = form.get("base_url", "").strip() or None
    token_env = form.get("token_env", "").strip() or None
    if mode == "local":
        base_url = None
        token_env = None
        channel = False
        relay_url = None
        relay_room = None
    try:
        return TeamHostEntry(
            id=hid,
            label=label,
            mode=mode,
            teams=teams,
            base_url=base_url,
            token_env=token_env,
            channel=channel,
            relay_url=relay_url,
            relay_room=relay_room,
        )
    except ValidationError as exc:
        raise HostsAdminError(str(exc)) from exc


def create_host(
    root: Path,
    entry: TeamHostEntry,
    *,
    actor: str,
) -> None:
    cfg = load_hosts_admin(root)
    if get_host(cfg, entry.id):
        raise HostsAdminError(f"Host '{entry.id}' existiert bereits")
    hosts = _detach_teams_from_others(cfg.hosts, keep_host_id=entry.id, teams=entry.teams)
    hosts.append(entry)
    save_hosts_admin(root, TeamHostsConfig(hosts=hosts), actor=actor)


def update_host(
    root: Path,
    host_id: str,
    entry: TeamHostEntry,
    *,
    actor: str,
) -> None:
    if entry.id != host_id:
        raise HostsAdminError("Host-ID darf beim Bearbeiten nicht geändert werden")
    cfg = load_hosts_admin(root)
    idx = next((i for i, h in enumerate(cfg.hosts) if h.id == host_id), None)
    if idx is None:
        raise HostsAdminError(f"Host '{host_id}' nicht gefunden")
    hosts = list(cfg.hosts)
    hosts[idx] = entry
    hosts = _detach_teams_from_others(hosts, keep_host_id=host_id, teams=entry.teams)
    save_hosts_admin(root, TeamHostsConfig(hosts=hosts), actor=actor)


def delete_host(root: Path, host_id: str, *, actor: str) -> None:
    cfg = load_hosts_admin(root)
    new_hosts = [h for h in cfg.hosts if h.id != host_id]
    if len(new_hosts) == len(cfg.hosts):
        raise HostsAdminError(f"Host '{host_id}' nicht gefunden")
    if not new_hosts:
        raise HostsAdminError("Mindestens ein Host muss verbleiben")
    save_hosts_admin(root, TeamHostsConfig(hosts=new_hosts), actor=actor)


def generate_team_token() -> str:
    return secrets.token_urlsafe(32)


def load_team_api_admin(root: Path) -> TeamApiAdminConfig:
    path = team_api_path(root)
    if not path.is_file():
        return TeamApiAdminConfig()
    try:
        data = load_json_file(path)
        return TeamApiAdminConfig.model_validate(data)
    except ValidationError as exc:
        raise HostsAdminError(str(exc)) from exc


def save_team_api_admin(root: Path, cfg: TeamApiAdminConfig, *, actor: str) -> None:
    path = team_api_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, cfg.model_dump(mode="json"))
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, path),
        action="update",
        details={"token_env": cfg.token_env, "teams": cfg.teams},
    )


def probe_host_connection(root: Path, entry: TeamHostEntry) -> dict[str, Any]:
    """Verbindungstest für einen Host-Eintrag."""
    if entry.mode == "local":
        try:
            load_runtime_config(root)
            return {
                "ok": True,
                "summary": f"Lokal OK — {root}",
            }
        except ConfigLoadError as exc:
            return {"ok": False, "summary": str(exc)}

    if not entry.token_env or not env_var_is_set(entry.token_env):
        return {
            "ok": False,
            "summary": f"Token-Env '{entry.token_env or '?'}' ist nicht gesetzt",
        }
    if not entry.base_url:
        return {"ok": False, "summary": "base_url fehlt"}

    token = os.environ.get(entry.token_env or "", "")
    url = f"{entry.base_url.rstrip('/')}/api/v1/health"
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()
            status = data.get("status", "ok")
            return {
                "ok": True,
                "summary": f"Remote OK ({status}) — {entry.base_url}",
                "detail": data,
            }
    except httpx.HTTPError as exc:
        return {"ok": False, "summary": f"Remote fehlgeschlagen: {exc}"}


def probe_qdrant(root: Path) -> dict[str, Any]:
    try:
        cfg = load_system_config_admin(root)
    except Exception as exc:
        return {"ok": False, "summary": str(exc), "enabled": False}
    q = cfg.qdrant_global
    if not q or not q.enabled:
        return {"ok": True, "summary": "Qdrant deaktiviert", "enabled": False}
    if q.url in (":memory:", "memory"):
        return {"ok": True, "summary": "Qdrant in-memory (lokal)", "enabled": True}
    try:
        with httpx.Client(timeout=10.0) as client:
            base = q.url.rstrip("/")
            response = client.get(f"{base}/collections")
            response.raise_for_status()
            return {
                "ok": True,
                "summary": f"Qdrant erreichbar — {q.url}",
                "enabled": True,
            }
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "summary": f"Qdrant nicht erreichbar: {exc}",
            "enabled": True,
        }


def probe_llm(root: Path) -> dict[str, Any]:
    try:
        cfg = load_system_config_admin(root)
    except Exception as exc:
        return {"ok": False, "summary": str(exc)}
    llm = cfg.system.llm
    if not llm.enabled:
        return {"ok": True, "summary": "LLM deaktiviert", "enabled": False}
    secret_ok = env_var_is_set(llm.secret_ref)
    parts = [f"Modus: {llm.mode}", f"API: {llm.api_base}"]
    if llm.secret_ref:
        parts.append(
            f"Secret {llm.secret_ref}: {'gesetzt' if secret_ok else 'fehlt'}"
        )
    ok = secret_ok if llm.secret_ref else True
    if llm.mode == "proxy" and llm.proxy:
        tok = env_var_is_set(llm.proxy.token_env)
        parts.append(f"Proxy-Token {llm.proxy.token_env}: {'gesetzt' if tok else 'fehlt'}")
        ok = ok and tok
    return {
        "ok": ok,
        "summary": " · ".join(parts),
        "enabled": True,
    }


def probe_llm_http(root: Path) -> dict[str, Any]:
    """Schneller HTTP-Check der LLM-API (ohne Chat-Completion)."""
    base = probe_llm(root)
    if not base.get("enabled"):
        return {**base, "ping_ok": None, "ping_summary": "LLM deaktiviert — kein HTTP-Ping"}
    if not base.get("ok"):
        return {
            **base,
            "ping_ok": False,
            "ping_summary": "HTTP-Ping übersprungen (Konfiguration unvollständig)",
        }
    try:
        cfg = load_system_config_admin(root)
    except Exception as exc:
        return {**base, "ping_ok": False, "ping_summary": str(exc)}

    llm = cfg.system.llm
    api_base = (llm.api_base or "").rstrip("/")
    if not api_base:
        return {**base, "ping_ok": False, "ping_summary": "api_base fehlt"}

    headers: dict[str, str] = {}
    if llm.secret_ref and env_var_is_set(llm.secret_ref):
        token = os.environ.get(str(llm.secret_ref).strip(), "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

    paths = ("/health", "/v1/models", "/models")
    last_error: str | None = None
    for path in paths:
        url = f"{api_base}{path}"
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(url, headers=headers or None)
            if response.status_code < 400:
                return {
                    **base,
                    "ping_ok": True,
                    "ping_summary": f"HTTP {response.status_code} — GET {path}",
                }
            last_error = f"HTTP {response.status_code} — {url}"
        except httpx.HTTPError as exc:
            last_error = str(exc)

    return {
        **base,
        "ping_ok": False,
        "ping_summary": f"HTTP-Ping fehlgeschlagen: {last_error or 'keine Antwort'}",
    }


def probe_llm_live(root: Path) -> dict[str, Any]:
    """Kurzer Live-Request ans konfigurierte LLM (nicht nur Env-Check)."""
    base = probe_llm(root)
    if not base.get("enabled"):
        return {**base, "live_ok": None, "live_summary": "LLM deaktiviert — kein Live-Test"}
    if not base.get("ok"):
        return {
            **base,
            "live_ok": False,
            "live_summary": "Live-Test übersprungen (Konfiguration unvollständig)",
        }
    try:
        from bot.config import load_runtime_config
        from bot.llm import build_llm_stack

        config = load_runtime_config(root)
        stack = build_llm_stack(config)
        model = stack.router.resolve("planning", role="orchestrator")
        fallbacks = stack.router.fallbacks("planning", role="orchestrator")
        reply = stack.client.complete(
            model,
            [
                {"role": "user", "content": "Antworte nur mit: ok"},
            ],
            fallbacks=fallbacks or None,
        )
        snippet = (reply or "").strip()[:80]
        return {
            **base,
            "live_ok": True,
            "live_summary": f"Live-Antwort OK — {snippet!r}",
        }
    except Exception as exc:
        return {
            **base,
            "live_ok": False,
            "live_summary": f"Live-Test fehlgeschlagen: {exc}",
        }


def collect_settings_status(root: Path, *, live_llm: bool = False) -> dict[str, Any]:
    """Aggregiert Status für /admin/settings/status."""
    hosts_cfg = load_hosts_admin(root)
    host_rows: list[dict[str, Any]] = []
    for entry in hosts_cfg.hosts:
        probe = probe_host_connection(root, entry)
        host_rows.append(
            {
                "id": entry.id,
                "label": entry.label,
                "mode": entry.mode,
                "teams": entry.teams,
                "channel": entry.channel,
                "connection": entry.base_url or f"lokal ({root})",
                **probe,
            }
        )
    api_cfg = load_team_api_admin(root)
    return {
        "hosts": host_rows,
        "team_api": {
            "token_env": api_cfg.token_env,
            "token_set": env_var_is_set(api_cfg.token_env),
            "teams": api_cfg.teams,
        },
        "llm": probe_llm_live(root) if live_llm else probe_llm(root),
        "qdrant": probe_qdrant(root),
        "channel_hosts": [
            h.id for h in hosts_cfg.hosts if h.mode == "remote" and h.channel
        ],
    }
