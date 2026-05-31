"""System- und Task-Modell-Einstellungen (/admin/settings/system, /models)."""

from __future__ import annotations

from pathlib import Path

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.config.writers.system_admin import (
    SystemAdminError,
    load_system_config_admin,
    save_llm_section,
    save_playwright_section,
    save_polling_section,
    save_qdrant_section,
    save_webhooks_section,
    secret_status_map,
)
from bot.config.writers.task_models_admin import (
    TaskModelsAdminError,
    load_task_models_admin,
    parse_models_from_form,
    save_task_models_admin,
)
from bot.web.auth import CurrentUser, require_admin


def _form_dict(form) -> dict[str, str]:
    return {k: str(form[k]) for k in form.keys()}


def register_system_settings_routes(
    app,
    templates: Jinja2Templates,
    root_path: Path,
) -> None:
    def _system_ctx(cfg, *, error: str | None = None, saved: str | None = None):
        q = cfg.qdrant_global
        pw = cfg.playwright_global
        wh = cfg.webhooks_global
        return {
            "cfg": cfg,
            "llm": cfg.system.llm,
            "qdrant": q,
            "playwright": pw,
            "polling": cfg.system.polling,
            "webhooks": wh,
            "secret_status": secret_status_map(cfg),
            "error": error,
            "saved": saved,
            "settings_active": "system",
        }

    @app.get("/admin/settings/system", response_class=HTMLResponse)
    async def system_settings_page(
        request: Request,
        user: CurrentUser,
        saved: str | None = None,
    ):
        require_admin(user)
        try:
            cfg = load_system_config_admin(root_path)
        except SystemAdminError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        ctx = _system_ctx(cfg, saved=saved)
        ctx["user"] = user
        return templates.TemplateResponse(request, "admin_settings_system.html", ctx)

    @app.post("/admin/settings/system/llm")
    async def system_save_llm(
        request: Request,
        user: CurrentUser,
        llm_enabled: str | None = Form(None),
        llm_mode: str = Form("direct"),
        api_base: str = Form("http://127.0.0.1:4000"),
        secret_ref: str = Form(""),
        max_retries: int = Form(3),
        retry_backoff: float = Form(1.0),
        timeout_seconds: float = Form(120.0),
        proxy_base_url: str = Form(""),
        proxy_token_env: str = Form("BOT_LLM_PROXY_TOKEN"),
        hub_relay_url: str = Form(""),
        hub_relay_room: str = Form("default"),
        hub_token_env: str = Form("BOT_RELAY_TOKEN"),
        use_hub: str | None = Form(None),
    ):
        require_admin(user)
        mode = llm_mode if llm_mode in ("direct", "proxy", "channel") else "direct"
        try:
            save_llm_section(
                root_path,
                actor=user.username,
                enabled=llm_enabled == "on",
                mode=mode,  # type: ignore[arg-type]
                api_base=api_base,
                secret_ref=secret_ref or None,
                max_retries=max_retries,
                retry_backoff=retry_backoff,
                timeout_seconds=timeout_seconds,
                proxy_base_url=proxy_base_url,
                proxy_token_env=proxy_token_env,
                hub_relay_url=hub_relay_url,
                hub_relay_room=hub_relay_room,
                hub_token_env=hub_token_env,
                use_hub=use_hub == "on",
            )
        except SystemAdminError as exc:
            cfg = load_system_config_admin(root_path)
            ctx = _system_ctx(cfg, error=str(exc))
            ctx["user"] = user
            return templates.TemplateResponse(
                request, "admin_settings_system.html", ctx, status_code=400
            )
        return RedirectResponse("/admin/settings/system?saved=llm", status_code=302)

    @app.post("/admin/settings/system/qdrant")
    async def system_save_qdrant(
        request: Request,
        user: CurrentUser,
        qdrant_enabled: str | None = Form(None),
        url: str = Form("http://127.0.0.1:6333"),
        secret_ref: str = Form(""),
        embedding_provider: str = Form("hash"),
        embedding_model: str = Form(""),
        vector_size: int = Form(384),
        timeout_seconds: float = Form(30.0),
        reindex_enabled: str | None = Form(None),
        reindex_interval: float = Form(3600.0),
        watch_workspace: str | None = Form(None),
        watch_interval: float = Form(30.0),
        debounce_seconds: float = Form(90.0),
        include_crawl: str | None = Form(None),
    ):
        require_admin(user)
        prov = embedding_provider if embedding_provider in ("hash", "litellm") else "hash"
        try:
            save_qdrant_section(
                root_path,
                actor=user.username,
                enabled=qdrant_enabled == "on",
                url=url,
                secret_ref=secret_ref or None,
                embedding_provider=prov,  # type: ignore[arg-type]
                embedding_model=embedding_model or None,
                vector_size=vector_size,
                timeout_seconds=timeout_seconds,
                reindex_enabled=reindex_enabled == "on",
                reindex_interval=reindex_interval,
                watch_workspace=watch_workspace == "on",
                watch_interval=watch_interval,
                debounce_seconds=debounce_seconds,
                include_crawl=include_crawl == "on",
            )
        except SystemAdminError as exc:
            cfg = load_system_config_admin(root_path)
            ctx = _system_ctx(cfg, error=str(exc))
            ctx["user"] = user
            return templates.TemplateResponse(
                request, "admin_settings_system.html", ctx, status_code=400
            )
        return RedirectResponse("/admin/settings/system?saved=qdrant", status_code=302)

    @app.post("/admin/settings/system/playwright")
    async def system_save_playwright(
        request: Request,
        user: CurrentUser,
        mode: str = Form("local"),
        headless: str | None = Form(None),
        timeout_seconds: float = Form(60.0),
        ws_endpoints: str = Form(""),
        secret_ref: str = Form(""),
    ):
        require_admin(user)
        pw_mode = mode if mode in ("local", "remote") else "local"
        endpoints = [ln.strip() for ln in ws_endpoints.splitlines() if ln.strip()]
        try:
            save_playwright_section(
                root_path,
                actor=user.username,
                mode=pw_mode,  # type: ignore[arg-type]
                headless=headless == "on",
                timeout_seconds=timeout_seconds,
                ws_endpoints=endpoints,
                secret_ref=secret_ref or None,
            )
        except SystemAdminError as exc:
            cfg = load_system_config_admin(root_path)
            ctx = _system_ctx(cfg, error=str(exc))
            ctx["user"] = user
            return templates.TemplateResponse(
                request, "admin_settings_system.html", ctx, status_code=400
            )
        return RedirectResponse("/admin/settings/system?saved=playwright", status_code=302)

    @app.post("/admin/settings/system/polling")
    async def system_save_polling(
        request: Request,
        user: CurrentUser,
        interval_seconds: float = Form(5.0),
        inbox_watch_seconds: float = Form(0.5),
        worker_mode: str = Form("process"),
    ):
        require_admin(user)
        wm = worker_mode if worker_mode in ("thread", "process") else "process"
        try:
            save_polling_section(
                root_path,
                actor=user.username,
                interval_seconds=interval_seconds,
                inbox_watch_seconds=inbox_watch_seconds,
                worker_mode=wm,  # type: ignore[arg-type]
            )
        except SystemAdminError as exc:
            cfg = load_system_config_admin(root_path)
            ctx = _system_ctx(cfg, error=str(exc))
            ctx["user"] = user
            return templates.TemplateResponse(
                request, "admin_settings_system.html", ctx, status_code=400
            )
        return RedirectResponse("/admin/settings/system?saved=polling", status_code=302)

    @app.post("/admin/settings/system/webhooks")
    async def system_save_webhooks(
        request: Request,
        user: CurrentUser,
        enabled: str | None = Form(None),
        secret_ref: str = Form("BOT_WEBHOOK_SECRET"),
        path_prefix: str = Form("/api/v1/webhooks"),
    ):
        require_admin(user)
        try:
            save_webhooks_section(
                root_path,
                actor=user.username,
                enabled=enabled == "on",
                secret_ref=secret_ref,
                path_prefix=path_prefix,
            )
        except SystemAdminError as exc:
            cfg = load_system_config_admin(root_path)
            ctx = _system_ctx(cfg, error=str(exc))
            ctx["user"] = user
            return templates.TemplateResponse(
                request, "admin_settings_system.html", ctx, status_code=400
            )
        return RedirectResponse("/admin/settings/system?saved=webhooks", status_code=302)

    @app.get("/admin/settings/models", response_class=HTMLResponse)
    async def task_models_page(
        request: Request,
        user: CurrentUser,
        saved: str | None = None,
    ):
        require_admin(user)
        try:
            models = load_task_models_admin(root_path)
        except TaskModelsAdminError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return templates.TemplateResponse(
            request,
            "admin_settings_models.html",
            {
                "user": user,
                "task_models": models.task_models,
                "saved": saved,
                "error": None,
                "settings_active": "models",
            },
        )

    @app.post("/admin/settings/models")
    async def task_models_save(request: Request, user: CurrentUser):
        require_admin(user)
        form = await request.form()
        try:
            parsed = parse_models_from_form(_form_dict(form))
            save_task_models_admin(root_path, parsed, actor=user.username)
        except TaskModelsAdminError as exc:
            try:
                models = load_task_models_admin(root_path)
            except TaskModelsAdminError:
                models = None
            return templates.TemplateResponse(
                request,
                "admin_settings_models.html",
                {
                    "user": user,
                    "task_models": models.task_models if models else {},
                    "saved": None,
                    "error": str(exc),
                    "settings_active": "models",
                },
                status_code=400,
            )
        return RedirectResponse("/admin/settings/models?saved=1", status_code=302)
