"""Team-Dienste: Crawl, E-Mail, Hours, … unter /teams/<id>/settings/."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from bot.browser.config import TeamPlaywrightOverride
from bot.config.writers.team_admin import list_agent_ids
from bot.config.writers.team_services_admin import (
    TeamServicesAdminError,
    build_publish_from_form,
    build_website_from_form,
    env_status_refs,
    load_crawl_admin,
    load_email_admin,
    load_git_admin,
    load_hours_admin,
    load_hours_master_admin,
    load_integrations_admin,
    load_playwright_admin,
    parse_crawl_domains_from_form,
    save_crawl_admin,
    save_email_admin,
    save_git_admin,
    save_hours_admin,
    save_hours_master_admin,
    save_integrations_admin,
    save_playwright_admin,
)
from bot.crawl.config import CrawlConfig
from bot.git_svc.config import GitConfig
from bot.hours.config import GoogleBusinessConfig, HoursSchedule, HoursTeamConfig, WebsiteHttpConfig
from bot.hours.master import DayHours, HoursMaster
from bot.integrations.config import IntegrationsConfig, MatrixConfig, TelegramConfig
from bot.mail.config import EmailRules, EmailTeamConfig, ImapConfig, SmtpConfig
from bot.web.auth import CurrentUser, require_team_access
from bot.web.team_access import require_team_write


def _form_dict(form) -> dict[str, str]:
    return {k: str(form[k]) for k in form.keys()}


def _svc_ctx(team_id: str, user: CurrentUser, active: str, **extra):
    return {"user": user, "team_id": team_id, "settings_active": active, **extra}


def register_team_services_settings_routes(
    app,
    templates: Jinja2Templates,
    root_path: Path,
) -> None:
    @app.get("/teams/{team_id}/settings/crawl", response_class=HTMLResponse)
    async def team_settings_crawl(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_crawl_admin(root_path, team_id)
        extra_slots = max(2, 5 - len(cfg.domains))
        return templates.TemplateResponse(
            request,
            "team_settings_crawl.html",
            _svc_ctx(
                team_id,
                user,
                "crawl",
                crawl=cfg,
                domains=cfg.domains,
                extra_slots=extra_slots,
            ),
        )

    @app.post("/teams/{team_id}/settings/crawl")
    async def team_settings_crawl_save(request: Request, team_id: str, user: CurrentUser):
        require_team_write(team_id, user)
        form = await request.form()
        fd = _form_dict(form)
        try:
            cfg = CrawlConfig(
                enabled=fd.get("crawl_enabled") == "on",
                domains=parse_crawl_domains_from_form(fd),
                snapshot_dir=fd.get("snapshot_dir", f"data/{team_id}/crawl"),
                qdrant_collection=fd.get("qdrant_collection", "web"),
                prune_threshold=float(fd.get("prune_threshold", "0.48")),
            )
            save_crawl_admin(root_path, team_id, actor=user.username, cfg=cfg)
        except (TeamServicesAdminError, ValueError) as exc:
            cfg = load_crawl_admin(root_path, team_id)
            return templates.TemplateResponse(
                request,
                "team_settings_crawl.html",
                _svc_ctx(
                    team_id,
                    user,
                    "crawl",
                    crawl=cfg,
                    domains=cfg.domains,
                    extra_slots=2,
                    error=str(exc),
                ),
                status_code=400,
            )
        return RedirectResponse(f"/teams/{team_id}/settings/crawl?saved=1", status_code=302)

    @app.get("/teams/{team_id}/settings/email", response_class=HTMLResponse)
    async def team_settings_email(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_email_admin(root_path, team_id)
        refs: list[str | None] = []
        if cfg:
            refs = [cfg.imap.secret_ref, cfg.smtp.secret_ref]
        return templates.TemplateResponse(
            request,
            "team_settings_email.html",
            _svc_ctx(team_id, user, "email", email=cfg, secret_status=env_status_refs(*refs)),
        )

    @app.post("/teams/{team_id}/settings/email")
    async def team_settings_email_save(request: Request, team_id: str, user: CurrentUser):
        require_team_write(team_id, user)
        form = await request.form()
        f = _form_dict(form)
        domains = [d.strip() for d in f.get("allowed_domains", "").split(",") if d.strip()]
        try:
            cfg = EmailTeamConfig(
                enabled=f.get("email_enabled") == "on",
                imap=ImapConfig(
                    host=f.get("imap_host", ""),
                    port=int(f.get("imap_port", "993")),
                    username=f.get("imap_user", ""),
                    secret_ref=f.get("imap_secret_ref", "FIRMA_IMAP_PASSWORD"),
                    mailbox=f.get("imap_mailbox", "INBOX"),
                    poll_interval_seconds=int(f.get("imap_poll", "120")),
                ),
                smtp=SmtpConfig(
                    host=f.get("smtp_host", ""),
                    port=int(f.get("smtp_port", "587")),
                    username=f.get("smtp_user", ""),
                    secret_ref=f.get("smtp_secret_ref", "FIRMA_SMTP_PASSWORD"),
                    from_display_name=f.get("smtp_from_name") or None,
                ),
                rules=EmailRules(
                    allowed_recipient_domains=domains,
                    require_approval=f.get("require_approval") == "on",
                ),
            )
            save_email_admin(root_path, team_id, actor=user.username, cfg=cfg)
        except (TeamServicesAdminError, ValueError) as exc:
            cfg = load_email_admin(root_path, team_id)
            refs = [cfg.imap.secret_ref, cfg.smtp.secret_ref] if cfg else []
            return templates.TemplateResponse(
                request,
                "team_settings_email.html",
                _svc_ctx(
                    team_id,
                    user,
                    "email",
                    email=cfg,
                    secret_status=env_status_refs(*refs),
                    error=str(exc),
                ),
                status_code=400,
            )
        return RedirectResponse(f"/teams/{team_id}/settings/email?saved=1", status_code=302)

    @app.get("/teams/{team_id}/settings/hours", response_class=HTMLResponse)
    async def team_settings_hours(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_hours_admin(root_path, team_id)
        agent_ids = list_agent_ids(root_path, team_id)
        refs: list[str | None] = []
        if cfg:
            refs.append(cfg.google_business.secret_ref)
            if isinstance(cfg.website, WebsiteHttpConfig):
                refs.append(cfg.website.secret_ref)
        return templates.TemplateResponse(
            request,
            "team_settings_hours.html",
            _svc_ctx(
                team_id,
                user,
                "hours",
                hours=cfg,
                agent_ids=agent_ids,
                secret_status=env_status_refs(*refs),
            ),
        )

    @app.post("/teams/{team_id}/settings/hours")
    async def team_settings_hours_save(request: Request, team_id: str, user: CurrentUser):
        require_team_write(team_id, user)
        form = await request.form()
        f = _form_dict(form)
        try:
            cfg = HoursTeamConfig(
                enabled=f.get("hours_enabled") == "on",
                master_file=f.get("master_file", f"teams/{team_id}/hours.master.json"),
                website=build_website_from_form(f),
                publish=build_publish_from_form(f),
                google_business=GoogleBusinessConfig(
                    enabled=f.get("gb_enabled") == "on",
                    page_url=f.get("gb_page_url") or None,
                    secret_ref=f.get("gb_secret_ref") or None,
                ),
                schedule=HoursSchedule(
                    check_cron=f.get("check_cron", "0 6 * * *"),
                    timezone=f.get("schedule_tz", "Europe/Berlin"),
                ),
                require_approval=f.get("hours_require_approval") == "on",
                checker_agent_id=f.get("checker_agent_id", "hours-checker"),
            )
            save_hours_admin(root_path, team_id, actor=user.username, cfg=cfg)
        except (TeamServicesAdminError, ValueError) as exc:
            cfg = load_hours_admin(root_path, team_id)
            return templates.TemplateResponse(
                request,
                "team_settings_hours.html",
                _svc_ctx(
                    team_id,
                    user,
                    "hours",
                    hours=cfg,
                    agent_ids=list_agent_ids(root_path, team_id),
                    error=str(exc),
                ),
                status_code=400,
            )
        return RedirectResponse(f"/teams/{team_id}/settings/hours?saved=1", status_code=302)

    @app.get("/teams/{team_id}/settings/hours/master", response_class=HTMLResponse)
    async def team_settings_hours_master(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        hours = load_hours_admin(root_path, team_id)
        if not hours:
            raise HTTPException(status_code=404, detail="hours.json fehlt")
        try:
            master = load_hours_master_admin(root_path, hours.master_file)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        return templates.TemplateResponse(
            request,
            "team_settings_hours_master.html",
            _svc_ctx(
                team_id,
                user,
                "hours",
                master=master,
                days=days,
                master_file=hours.master_file,
            ),
        )

    @app.post("/teams/{team_id}/settings/hours/master")
    async def team_settings_hours_master_save(
        request: Request, team_id: str, user: CurrentUser
    ):
        require_team_write(team_id, user)
        hours = load_hours_admin(root_path, team_id)
        if not hours:
            raise HTTPException(status_code=404, detail="hours.json fehlt")
        form = await request.form()
        f = _form_dict(form)
        weekly: dict[str, DayHours] = {}
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            weekly[day] = DayHours(
                open=f.get(f"{day}_open") or None,
                close=f.get(f"{day}_close") or None,
                closed=f.get(f"{day}_closed") == "on",
            )
        master = HoursMaster(
            timezone=f.get("timezone", "Europe/Berlin"),
            weekly=weekly,
            note=f.get("note") or None,
        )
        save_hours_master_admin(
            root_path,
            hours.master_file,
            master,
            team_id=team_id,
            actor=user.username,
        )
        return RedirectResponse(
            f"/teams/{team_id}/settings/hours/master?saved=1", status_code=302
        )

    @app.get("/teams/{team_id}/settings/integrations", response_class=HTMLResponse)
    async def team_settings_integrations(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_integrations_admin(root_path, team_id)
        return templates.TemplateResponse(
            request,
            "team_settings_integrations.html",
            _svc_ctx(
                team_id,
                user,
                "integrations",
                integrations=cfg,
                secret_status=env_status_refs(
                    cfg.telegram.bot_token_ref,
                    cfg.matrix.access_token_ref,
                ),
            ),
        )

    @app.post("/teams/{team_id}/settings/integrations")
    async def team_settings_integrations_save(
        request: Request, team_id: str, user: CurrentUser
    ):
        require_team_write(team_id, user)
        form = await request.form()
        f = _form_dict(form)
        cfg = IntegrationsConfig(
            telegram=TelegramConfig(
                enabled=f.get("tg_enabled") == "on",
                bot_token_ref=f.get("tg_token_ref", "TELEGRAM_BOT_TOKEN"),
                default_agent_id=f.get("tg_agent", "orchestrator"),
            ),
            matrix=MatrixConfig(
                enabled=f.get("mx_enabled") == "on",
                homeserver=f.get("mx_homeserver", "https://matrix.org"),
                access_token_ref=f.get("mx_token_ref", "MATRIX_ACCESS_TOKEN"),
                room_id=f.get("mx_room") or None,
                default_agent_id=f.get("mx_agent", "orchestrator"),
            ),
        )
        save_integrations_admin(root_path, team_id, actor=user.username, cfg=cfg)
        return RedirectResponse(
            f"/teams/{team_id}/settings/integrations?saved=1", status_code=302
        )

    @app.get("/teams/{team_id}/settings/git", response_class=HTMLResponse)
    async def team_settings_git(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_git_admin(root_path, team_id)
        return templates.TemplateResponse(
            request,
            "team_settings_git.html",
            _svc_ctx(team_id, user, "git", git=cfg),
        )

    @app.post("/teams/{team_id}/settings/git")
    async def team_settings_git_save(request: Request, team_id: str, user: CurrentUser):
        require_team_write(team_id, user)
        form = await request.form()
        f = _form_dict(form)
        cfg = GitConfig(
            enabled=f.get("git_enabled") == "on",
            repo_path=f.get("repo_path", f"data/{team_id}/workspace"),
            remote_name=f.get("remote_name", "origin"),
            default_branch=f.get("default_branch", "main"),
            user_name=f.get("user_name", "bot"),
            user_email=f.get("user_email", "bot@local"),
        )
        save_git_admin(root_path, team_id, actor=user.username, cfg=cfg)
        return RedirectResponse(f"/teams/{team_id}/settings/git?saved=1", status_code=302)

    @app.get("/teams/{team_id}/settings/playwright", response_class=HTMLResponse)
    async def team_settings_playwright(request: Request, team_id: str, user: CurrentUser):
        require_team_access(team_id, user)
        cfg = load_playwright_admin(root_path, team_id)
        return templates.TemplateResponse(
            request,
            "team_settings_playwright.html",
            _svc_ctx(team_id, user, "playwright", playwright=cfg),
        )

    @app.post("/teams/{team_id}/settings/playwright")
    async def team_settings_playwright_save(
        request: Request, team_id: str, user: CurrentUser
    ):
        require_team_write(team_id, user)
        form = await request.form()
        f = _form_dict(form)
        source = f.get("source", "global")
        if source == "global":
            save_playwright_admin(root_path, team_id, actor=user.username, cfg=None)
        else:
            endpoints = [ln.strip() for ln in f.get("ws_endpoints", "").splitlines() if ln.strip()]
            mode = f.get("pw_mode", "local")
            cfg = TeamPlaywrightOverride(
                source="custom",
                mode=mode if mode in ("local", "remote") else "local",
                ws_endpoints=endpoints,
                headless=f.get("headless") == "on",
            )
            save_playwright_admin(root_path, team_id, actor=user.username, cfg=cfg)
        return RedirectResponse(
            f"/teams/{team_id}/settings/playwright?saved=1", status_code=302
        )
