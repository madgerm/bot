"""Team-Einstellungen /teams/<id>/settings."""

from __future__ import annotations

from pathlib import Path

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.agents_mgmt import AgentManager, AgentManagerError
from bot.config.models import AgentBlock
from bot.config.writers.team_admin import (
    TeamAdminError,
    list_agent_ids,
    load_team_config,
    save_team_general,
    save_team_pipeline,
)
from bot.runtime.agent_tools import (
    KNOWLEDGE_CHOICES,
    TOOL_CHOICES,
    agent_knowledge_summary,
    agent_tools_summary,
    resolve_allowed_tools,
    role_default_tools,
)
from bot.runtime.pipeline import resolve_pipeline
from bot.runtime.tools import TOOL_NAMES
from bot.web.auth import CurrentUser, require_team_access
from bot.web.team_access import require_team_write


def _parse_tools_from_form(form, prefix: str = "tool_") -> list[str]:
    selected: list[str] = []
    for name in TOOL_NAMES:
        if form.get(f"{prefix}{name}") == "on":
            selected.append(name)
    return selected


def _parse_knowledge_from_form(form) -> list[str]:
    return [suffix for suffix, _ in KNOWLEDGE_CHOICES if form.get(f"know_{suffix}") == "on"]


def _parse_agent_tools_from_form(form) -> tuple[list[str], list[str]]:
    use_custom = form.get("use_custom_tools") == "on"
    tools_allow = _parse_tools_from_form(form, "tool_") if use_custom else []
    tools_deny = _parse_tools_from_form(form, "deny_tool_")
    return tools_allow, tools_deny


def _enrich_agent_rows(agents: list[dict]) -> list[dict]:
    for row in agents:
        block = AgentBlock(
            id=row["id"],
            role=row["role"],  # type: ignore[arg-type]
            enabled=row["enabled"],
            interval_seconds=row.get("interval_seconds"),
            display_name=row.get("display_name"),
            task_categories=row.get("task_categories") or [],
            system_prompt_extra=row.get("system_prompt_extra"),
            tools_allow=row.get("tools_allow") or [],
            tools_deny=row.get("tools_deny") or [],
            qdrant_collections=row.get("qdrant_collections") or [],
        )
        row["tools_summary"] = agent_tools_summary(block.role, block)
        row["knowledge_summary"] = agent_knowledge_summary(block)
    return agents


def _agent_form_extras(block: AgentBlock | None = None, *, role: str = "worker") -> dict:
    eff_role = block.role if block else role
    agent = block
    return {
        "tool_choices": TOOL_CHOICES,
        "knowledge_choices": KNOWLEDGE_CHOICES,
        "use_custom_tools": bool(block and block.tools_allow),
        "selected_tools": set(block.tools_allow) if block and block.tools_allow else set(),
        "selected_deny": set(block.tools_deny) if block and block.tools_deny else set(),
        "selected_knowledge": set(block.qdrant_collections)
        if block and block.qdrant_collections
        else set(),
        "role_default_tools": sorted(role_default_tools(eff_role)),
        "effective_tools": sorted(resolve_allowed_tools(eff_role, agent)),
    }


AGENT_ROLES = [
    "orchestrator",
    "worker",
    "reviewer",
    "story_writer",
    "story_reviewer",
    "coder",
    "tester",
    "documenter",
    "hours_checker",
]


def register_team_settings_routes(
    app,
    templates: Jinja2Templates,
    root_path: Path,
) -> None:
    def _ctx(team_id: str, user: CurrentUser, active: str, **extra):
        return {"user": user, "team_id": team_id, "settings_active": active, **extra}

    @app.get("/teams/{team_id}/settings", response_class=HTMLResponse)
    async def team_settings_index(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        try:
            cfg = load_team_config(root_path, team_id)
            agents = list_agent_ids(root_path, team_id)
            resolved = None
            try:
                from bot.config.loader import load_runtime_config

                bundle = load_runtime_config(root_path).teams.get(team_id)
                if bundle:
                    resolved = resolve_pipeline(bundle)
            except Exception:
                pass
        except TeamAdminError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return templates.TemplateResponse(
            request,
            "team_settings_index.html",
            _ctx(
                team_id,
                user,
                "index",
                team=cfg.team,
                pipeline=cfg.pipeline,
                agents=agents,
                resolved=resolved,
            ),
        )

    @app.get("/teams/{team_id}/settings/general", response_class=HTMLResponse)
    async def team_settings_general(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_team_config(root_path, team_id)
        return templates.TemplateResponse(
            request,
            "team_settings_general.html",
            _ctx(
                team_id,
                user,
                "general",
                team=cfg.team,
                agent_ids=list_agent_ids(root_path, team_id),
                error=None,
            ),
        )

    @app.post("/teams/{team_id}/settings/general")
    async def team_settings_general_save(
        request: Request,
        team_id: str,
        user: CurrentUser,
        name: str = Form(...),
        enabled: str | None = Form(None),
        preset: str = Form("generic"),
        orchestrator_id: str = Form(...),
    ):
        require_team_write(team_id, user)
        preset_val = preset if preset in ("generic", "demo", "coding", "story") else "generic"
        try:
            save_team_general(
                root_path,
                team_id,
                actor=user.username,
                name=name,
                enabled=enabled == "on",
                preset=preset_val,  # type: ignore[arg-type]
                orchestrator_id=orchestrator_id,
            )
        except TeamAdminError as exc:
            cfg = load_team_config(root_path, team_id)
            return templates.TemplateResponse(
                request,
                "team_settings_general.html",
                _ctx(
                    team_id,
                    user,
                    "general",
                    team=cfg.team,
                    agent_ids=list_agent_ids(root_path, team_id),
                    error=str(exc),
                ),
                status_code=400,
            )
        return RedirectResponse(
            f"/teams/{team_id}/settings/general?saved=1", status_code=302
        )

    @app.get("/teams/{team_id}/settings/pipeline", response_class=HTMLResponse)
    async def team_settings_pipeline(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_team_config(root_path, team_id)
        agent_ids = list_agent_ids(root_path, team_id)
        return templates.TemplateResponse(
            request,
            "team_settings_pipeline.html",
            _ctx(
                team_id,
                user,
                "pipeline",
                pipeline=cfg.pipeline,
                agent_ids=agent_ids,
                preset=cfg.team.preset,
                error=None,
            ),
        )

    @app.post("/teams/{team_id}/settings/pipeline")
    async def team_settings_pipeline_save(
        request: Request,
        team_id: str,
        user: CurrentUser,
        execute: str = Form(""),
        review: str = Form(""),
        document: str = Form(""),
    ):
        require_team_write(team_id, user)
        try:
            save_team_pipeline(
                root_path,
                team_id,
                actor=user.username,
                execute=execute,
                review=review,
                document=document,
            )
        except TeamAdminError as exc:
            cfg = load_team_config(root_path, team_id)
            return templates.TemplateResponse(
                request,
                "team_settings_pipeline.html",
                _ctx(
                    team_id,
                    user,
                    "pipeline",
                    pipeline=cfg.pipeline,
                    agent_ids=list_agent_ids(root_path, team_id),
                    preset=cfg.team.preset,
                    error=str(exc),
                ),
                status_code=400,
            )
        return RedirectResponse(
            f"/teams/{team_id}/settings/pipeline?saved=1", status_code=302
        )

    @app.get("/teams/{team_id}/settings/agents", response_class=HTMLResponse)
    async def team_settings_agents(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        mgr = AgentManager(root_path)
        try:
            agents = _enrich_agent_rows(mgr.list_agents(team_id))
            orch = load_team_config(root_path, team_id).team.orchestrator_id
        except (AgentManagerError, TeamAdminError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return templates.TemplateResponse(
            request,
            "team_settings_agents.html",
            _ctx(team_id, user, "agents", agents=agents, orchestrator_id=orch),
        )

    @app.get("/teams/{team_id}/settings/agents/new", response_class=HTMLResponse)
    async def team_settings_agent_new(request: Request, team_id: str, user: CurrentUser):
        require_team_write(team_id, user)
        return templates.TemplateResponse(
            request,
            "team_settings_agent_form.html",
            _ctx(
                team_id,
                user,
                "agents",
                mode="create",
                agent=None,
                roles=AGENT_ROLES,
                error=None,
                **_agent_form_extras(),
            ),
        )

    @app.get("/teams/{team_id}/settings/agents/{agent_id}", response_class=HTMLResponse)
    async def team_settings_agent_edit(
        request: Request, team_id: str, agent_id: str, user: CurrentUser
    ):
        require_team_access(team_id, user)
        mgr = AgentManager(root_path)
        try:
            block = mgr.get_agent_block(team_id, agent_id)
            orch = load_team_config(root_path, team_id).team.orchestrator_id
        except AgentManagerError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return templates.TemplateResponse(
            request,
            "team_settings_agent_form.html",
            _ctx(
                team_id,
                user,
                "agents",
                mode="edit",
                agent=block,
                agent_id=agent_id,
                roles=AGENT_ROLES,
                is_orchestrator=agent_id == orch,
                error=None,
                **_agent_form_extras(block),
            ),
        )

    @app.post("/teams/{team_id}/settings/agents/create")
    async def team_settings_agent_create(
        request: Request,
        team_id: str,
        user: CurrentUser,
        agent_id: str = Form(...),
        role: str = Form("worker"),
        display_name: str = Form(""),
        interval_seconds: str = Form(""),
        enabled: str | None = Form(None),
        task_categories: str = Form(""),
        system_prompt_extra: str = Form(""),
    ):
        require_team_write(team_id, user)
        form = await request.form()
        mgr = AgentManager(root_path)
        interval = float(interval_seconds) if interval_seconds.strip() else None
        cats = [c.strip() for c in task_categories.split(",") if c.strip()]
        tools_allow, tools_deny = _parse_agent_tools_from_form(form)
        knowledge = _parse_knowledge_from_form(form)
        try:
            mgr.create_agent(
                team_id,
                agent_id=agent_id.strip(),
                role=role,
                enabled=enabled == "on",
                interval_seconds=interval,
                display_name=display_name.strip() or None,
            )
            mgr.update_agent(
                team_id,
                agent_id.strip(),
                task_categories=cats,
                system_prompt_extra=system_prompt_extra.strip() or None,
                tools_allow=tools_allow,
                tools_deny=tools_deny,
                qdrant_collections=knowledge,
            )
        except AgentManagerError as exc:
            return templates.TemplateResponse(
                request,
                "team_settings_agent_form.html",
                _ctx(
                    team_id,
                    user,
                    "agents",
                    mode="create",
                    agent=None,
                    roles=AGENT_ROLES,
                    error=str(exc),
                    form_agent_id=agent_id,
                    **_agent_form_extras(role=role),
                ),
                status_code=400,
            )
        return RedirectResponse(
            f"/teams/{team_id}/settings/agents/{agent_id.strip()}?saved=created",
            status_code=302,
        )

    @app.post("/teams/{team_id}/settings/agents/{agent_id}/save")
    async def team_settings_agent_save(
        request: Request,
        team_id: str,
        agent_id: str,
        user: CurrentUser,
        role: str = Form("worker"),
        display_name: str = Form(""),
        interval_seconds: str = Form(""),
        enabled: str | None = Form(None),
        task_categories: str = Form(""),
        system_prompt_extra: str = Form(""),
    ):
        require_team_write(team_id, user)
        form = await request.form()
        mgr = AgentManager(root_path)
        cats = [c.strip() for c in task_categories.split(",") if c.strip()]
        interval = float(interval_seconds) if interval_seconds.strip() else None
        tools_allow, tools_deny = _parse_agent_tools_from_form(form)
        knowledge = _parse_knowledge_from_form(form)
        try:
            mgr.update_agent(
                team_id,
                agent_id,
                role=role,
                enabled=enabled == "on",
                display_name=display_name.strip() or None,
                interval_seconds=interval,
                task_categories=cats,
                system_prompt_extra=system_prompt_extra.strip() or None,
                tools_allow=tools_allow,
                tools_deny=tools_deny,
                qdrant_collections=knowledge,
            )
        except AgentManagerError as exc:
            block = mgr.get_agent_block(team_id, agent_id)
            orch = load_team_config(root_path, team_id).team.orchestrator_id
            return templates.TemplateResponse(
                request,
                "team_settings_agent_form.html",
                _ctx(
                    team_id,
                    user,
                    "agents",
                    mode="edit",
                    agent=block,
                    agent_id=agent_id,
                    roles=AGENT_ROLES,
                    is_orchestrator=agent_id == orch,
                    error=str(exc),
                    **_agent_form_extras(block),
                ),
                status_code=400,
            )
        return RedirectResponse(
            f"/teams/{team_id}/settings/agents/{agent_id}?saved=1", status_code=302
        )

    @app.post("/teams/{team_id}/settings/agents/{agent_id}/delete")
    async def team_settings_agent_delete(
        request: Request, team_id: str, agent_id: str, user: CurrentUser
    ):
        require_team_write(team_id, user)
        try:
            AgentManager(root_path).delete_agent(team_id, agent_id)
        except AgentManagerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            f"/teams/{team_id}/settings/agents?saved=deleted", status_code=302
        )

    from bot.web.team_services_settings_routes import register_team_services_settings_routes

    register_team_services_settings_routes(app, templates, root_path)
