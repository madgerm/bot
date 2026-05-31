"""Team-Dienste Admin."""

from __future__ import annotations

from pathlib import Path

from bot.config.writers.team_services_admin import (
    load_git_admin,
    parse_crawl_domains_from_form,
    save_crawl_admin,
    save_git_admin,
)
from bot.crawl.config import CrawlConfig


def test_save_crawl_and_git(runtime_project: Path) -> None:
    save_crawl_admin(
        runtime_project,
        "alpha",
        actor="admin",
        cfg=CrawlConfig(
            enabled=True,
            domains=parse_crawl_domains_from_form(
                {"domain_url_0": "https://example.com", "domain_max_0": "5", "domain_enabled_0": "on"}
            ),
        ),
    )
    loaded = load_git_admin(runtime_project, "alpha")
    save_git_admin(
        runtime_project,
        "alpha",
        actor="admin",
        cfg=loaded.model_copy(update={"default_branch": "develop"}),
    )
    assert load_git_admin(runtime_project, "alpha").default_branch == "develop"
