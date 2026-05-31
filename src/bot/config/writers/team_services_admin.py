"""Team-Dienste: crawl, email, hours, integrations, git, playwright (Panel)."""

from __future__ import annotations

from pathlib import Path

from bot.browser.config import TeamPlaywrightOverride
from bot.config.writers import (
    ConfigWriterError,
    atomic_write_json,
    load_json_file,
    relative_config_path,
)
from bot.config.writers.audit import log_config_change
from bot.config.writers.system_admin import env_var_is_set
from bot.crawl.config import CrawlConfig, CrawlDomain
from bot.git_svc.config import GitConfig
from bot.hours.config import (
    HoursConfig,
    HoursTeamConfig,
    WebsiteFileConfig,
    WebsiteHttpConfig,
    WebsitePageConfig,
)
from bot.hours.master import HoursMaster, save_master
from bot.integrations.config import IntegrationsConfig
from bot.mail.config import EmailConfig, EmailTeamConfig


class TeamServicesAdminError(ConfigWriterError):
    pass


def _team_path(root: Path, team_id: str, name: str) -> Path:
    return root / "teams" / team_id / name


def _log(root: Path, team_id: str, actor: str, action: str, filename: str) -> None:
    log_config_change(
        root,
        actor=actor,
        config_path=relative_config_path(root, _team_path(root, team_id, filename)),
        action=action,
        team_id=team_id,
    )


def env_status_refs(*refs: str | None) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for ref in refs:
        if ref and ref not in out:
            out[ref] = env_var_is_set(ref)
    return out


# --- Crawl ---


def load_crawl_admin(root: Path, team_id: str) -> CrawlConfig:
    path = _team_path(root, team_id, "crawl.json")
    if not path.is_file():
        return CrawlConfig()
    data = load_json_file(path)
    cfg = CrawlConfig.model_validate(data.get("crawl", data))
    if "{team_id}" in cfg.snapshot_dir:
        cfg = cfg.model_copy(update={"snapshot_dir": cfg.snapshot_dir.format(team_id=team_id)})
    return cfg


def parse_crawl_domains_from_form(form: dict[str, str]) -> list[CrawlDomain]:
    domains: list[CrawlDomain] = []
    i = 0
    while f"domain_url_{i}" in form:
        url = form.get(f"domain_url_{i}", "").strip()
        if url:
            max_p = int(form.get(f"domain_max_{i}", "10") or "10")
            enabled = form.get(f"domain_enabled_{i}") == "on"
            domains.append(CrawlDomain(url=url, max_pages=max_p, enabled=enabled))
        i += 1
    return domains


def save_crawl_admin(
    root: Path,
    team_id: str,
    *,
    actor: str,
    cfg: CrawlConfig,
) -> None:
    snap = cfg.snapshot_dir
    if "{team_id}" in snap:
        snap = snap.format(team_id=team_id)
    out = cfg.model_copy(update={"snapshot_dir": snap})
    atomic_write_json(_team_path(root, team_id, "crawl.json"), {"crawl": out.model_dump(mode="json")})
    _log(root, team_id, actor, "crawl_save", "crawl.json")


# --- Email ---


def load_email_admin(root: Path, team_id: str) -> EmailTeamConfig | None:
    path = _team_path(root, team_id, "email.json")
    if not path.is_file():
        return None
    data = load_json_file(path)
    return EmailConfig.model_validate(data).email


def save_email_admin(
    root: Path,
    team_id: str,
    *,
    actor: str,
    cfg: EmailTeamConfig,
) -> None:
    atomic_write_json(_team_path(root, team_id, "email.json"), {"email": cfg.model_dump(mode="json")})
    _log(root, team_id, actor, "email_save", "email.json")


# --- Hours ---


def load_hours_admin(root: Path, team_id: str) -> HoursTeamConfig | None:
    path = _team_path(root, team_id, "hours.json")
    if not path.is_file():
        return None
    data = load_json_file(path)
    cfg = HoursConfig.model_validate(data).hours
    cfg = cfg.model_copy(update={"master_file": cfg.master_file.replace("{team_id}", team_id)})
    return cfg


def build_website_from_form(
    form: dict[str, str],
) -> WebsiteFileConfig | WebsiteHttpConfig | WebsitePageConfig:
    wtype = form.get("website_type", "page")
    if wtype == "file":
        return WebsiteFileConfig(path=form.get("website_path", "").strip())
    if wtype == "http":
        return WebsiteHttpConfig(
            url=form.get("website_url", "").strip(),
            secret_ref=form.get("website_secret_ref") or None,
        )
    engine = form.get("website_crawl_engine", "auto")
    if engine not in ("auto", "httpx", "crawl4ai"):
        engine = "auto"
    return WebsitePageConfig(
        url=form.get("website_url", "").strip(),
        crawl_engine=engine,  # type: ignore[arg-type]
    )


def build_publish_from_form(form: dict[str, str]) -> WebsiteFileConfig | WebsiteHttpConfig | None:
    ptype = form.get("publish_type", "").strip()
    if not ptype or ptype == "none":
        return None
    if ptype == "file":
        path = form.get("publish_path", "").strip()
        return WebsiteFileConfig(path=path) if path else None
    return WebsiteHttpConfig(
        url=form.get("publish_url", "").strip(),
        secret_ref=form.get("publish_secret_ref") or None,
    )


def save_hours_admin(
    root: Path,
    team_id: str,
    *,
    actor: str,
    cfg: HoursTeamConfig,
) -> None:
    mf = cfg.master_file
    if "{team_id}" in mf:
        mf = mf.replace("{team_id}", team_id)
    out = cfg.model_copy(update={"master_file": mf})
    atomic_write_json(_team_path(root, team_id, "hours.json"), {"hours": out.model_dump(mode="json")})
    _log(root, team_id, actor, "hours_save", "hours.json")


def load_hours_master_admin(root: Path, master_relative: str) -> HoursMaster:
    from bot.hours.master import load_master

    return load_master(root, master_relative)


def save_hours_master_admin(
    root: Path,
    master_relative: str,
    master: HoursMaster,
    *,
    team_id: str,
    actor: str,
) -> None:
    save_master(root, master_relative, master)
    _log(root, team_id, actor, "hours_master_save", master_relative.split("/")[-1])


# --- Integrations ---


def load_integrations_admin(root: Path, team_id: str) -> IntegrationsConfig:
    path = _team_path(root, team_id, "integrations.json")
    if not path.is_file():
        return IntegrationsConfig()
    data = load_json_file(path)
    return IntegrationsConfig.model_validate(data.get("integrations", data))


def save_integrations_admin(
    root: Path,
    team_id: str,
    *,
    actor: str,
    cfg: IntegrationsConfig,
) -> None:
    atomic_write_json(
        _team_path(root, team_id, "integrations.json"),
        {"integrations": cfg.model_dump(mode="json")},
    )
    _log(root, team_id, actor, "integrations_save", "integrations.json")


# --- Git ---


def load_git_admin(root: Path, team_id: str) -> GitConfig:
    path = _team_path(root, team_id, "git.json")
    if not path.is_file():
        return GitConfig(repo_path=f"data/{team_id}/workspace")
    data = load_json_file(path)
    cfg = GitConfig.model_validate(data.get("git", data))
    if "{team_id}" in cfg.repo_path:
        cfg = cfg.model_copy(update={"repo_path": cfg.repo_path.format(team_id=team_id)})
    return cfg


def save_git_admin(root: Path, team_id: str, *, actor: str, cfg: GitConfig) -> None:
    atomic_write_json(_team_path(root, team_id, "git.json"), {"git": cfg.model_dump(mode="json")})
    _log(root, team_id, actor, "git_save", "git.json")


# --- Playwright ---


def load_playwright_admin(root: Path, team_id: str) -> TeamPlaywrightOverride | None:
    path = _team_path(root, team_id, "playwright.json")
    if not path.is_file():
        return None
    data = load_json_file(path)
    return TeamPlaywrightOverride.model_validate(data.get("playwright", data))


def save_playwright_admin(
    root: Path,
    team_id: str,
    *,
    actor: str,
    cfg: TeamPlaywrightOverride | None,
) -> None:
    path = _team_path(root, team_id, "playwright.json")
    if cfg is None or cfg.source == "global":
        if path.is_file():
            path.unlink()
    else:
        atomic_write_json(path, {"playwright": cfg.model_dump(mode="json", exclude_none=True)})
    _log(root, team_id, actor, "playwright_save", "playwright.json")
