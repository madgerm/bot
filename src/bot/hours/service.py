"""Öffnungszeiten: Agent-Check, Freigabe, Publish."""

from __future__ import annotations

import json
from pathlib import Path

from bot.approval.status import ApprovalError, assert_can_send
from bot.hours.adapters.google import fetch_google_snapshot, google_agent_report
from bot.hours.adapters.website import fetch_website_snapshot, publish_team_hours
from bot.hours.config import HoursConfigError, HoursTeamConfig, load_hours_config
from bot.hours.diff import compute_diff
from bot.hours.master import HoursMaster, load_master, save_master
from bot.hours.store import HoursDiffRecord, HoursStore, HoursStoreError
from bot.llm import LlmStack


class HoursServiceError(Exception):
    pass


class HoursService:
    def __init__(self, root: Path, team_id: str, cfg: HoursTeamConfig) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        self.cfg = cfg
        self.store = HoursStore(root, team_id)

    @classmethod
    def for_team(cls, root: Path, team_id: str) -> HoursService:
        try:
            cfg = load_hours_config(root, team_id)
        except HoursConfigError as exc:
            raise HoursServiceError(str(exc)) from exc
        return cls(root, team_id, cfg)

    def get_master(self) -> HoursMaster:
        try:
            return load_master(self.root, self.cfg.master_file)
        except HoursConfigError as exc:
            raise HoursServiceError(str(exc)) from exc

    def save_master(self, master: HoursMaster) -> Path:
        try:
            return save_master(self.root, self.cfg.master_file, master)
        except HoursConfigError as exc:
            raise HoursServiceError(str(exc)) from exc

    def check(self, *, llm_stack: LlmStack | None = None) -> HoursDiffRecord:
        master = self.get_master().normalized()
        try:
            website, website_report = fetch_website_snapshot(
                self.root, self.cfg, llm_stack=llm_stack
            )
        except HoursConfigError as exc:
            raise HoursServiceError(str(exc)) from exc

        agent_report = website_report
        if llm_stack and self.cfg.google_business.enabled:
            google_report = google_agent_report(self.cfg, llm_stack)
            if google_report:
                agent_report = (
                    {**website_report, "google": google_report}
                    if website_report
                    else {"google": google_report}
                )

        google = fetch_google_snapshot(
            self.root, self.team_id, self.cfg, llm_stack=llm_stack
        )
        diff = compute_diff(
            master,
            website,
            google,
            agent_report=agent_report,
        )
        return self.store.create_diff(diff)

    def approve(self, diff_id: str, approved_by: str) -> HoursDiffRecord:
        try:
            return self.store.approve(diff_id, approved_by)
        except HoursStoreError as exc:
            raise HoursServiceError(str(exc)) from exc

    def reject(self, diff_id: str) -> HoursDiffRecord:
        try:
            return self.store.reject(diff_id)
        except HoursStoreError as exc:
            raise HoursServiceError(str(exc)) from exc

    def publish(self, diff_id: str) -> HoursDiffRecord:
        record = self.store.get_diff(diff_id)
        if not record:
            raise HoursServiceError(f"Diff nicht gefunden: {diff_id}")
        try:
            assert_can_send(record.status)
        except ApprovalError as exc:
            raise HoursServiceError(str(exc)) from exc

        master = self.get_master().normalized()
        try:
            publish_team_hours(self.root, self.cfg, master)
            if self.cfg.google_business.enabled:
                google_path = self.root / "data" / self.team_id / "google_hours.snapshot.json"
                google_path.parent.mkdir(parents=True, exist_ok=True)
                google_path.write_text(
                    json.dumps({"hours": master}, indent=2) + "\n",
                    encoding="utf-8",
                )
        except HoursConfigError as exc:
            raise HoursServiceError(str(exc)) from exc

        return self.store.mark_published(diff_id)

    def format_check_summary(self, record: HoursDiffRecord) -> str:
        diff = record.diff_json
        lines = [
            f"Öffnungszeiten-Abgleich ({record.id})",
            f"Status: {record.status}",
            f"Modus: {diff.get('check_mode', 'snapshot')}",
        ]
        report = diff.get("agent_report")
        if isinstance(report, dict):
            if report.get("source_url"):
                lines.append(f"Quelle: {report['source_url']}")
            if report.get("extraction_method"):
                lines.append(f"Extraktion: {report['extraction_method']}")
            if report.get("agent_note"):
                lines.append(f"Hinweis: {report['agent_note']}")
        if diff.get("has_diff"):
            lines.append(f"Abweichungen: {diff.get('change_count', 0)}")
            for change in diff.get("changes", [])[:10]:
                lines.append(
                    f"  - {change.get('kind')}: {change.get('field')} "
                    f"(Master={change.get('master', '')}, Website={change.get('website', '')})"
                )
        else:
            lines.append("Keine Abweichungen — Website stimmt mit Master überein.")
        return "\n".join(lines)
