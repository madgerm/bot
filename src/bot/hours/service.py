"""Öffnungszeiten: Check, Freigabe, Publish."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bot.approval.status import ApprovalError, assert_can_send
from bot.hours.adapters.google import fetch_google_snapshot
from bot.hours.adapters.website import fetch_website_snapshot, publish_website_snapshot
from bot.hours.config import HoursConfigError, HoursTeamConfig, load_hours_config
from bot.hours.diff import compute_diff
from bot.hours.master import HoursMaster, load_master, save_master
from bot.hours.store import HoursDiffRecord, HoursStore, HoursStoreError


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

    def check(self) -> HoursDiffRecord:
        master = self.get_master().normalized()
        try:
            website = fetch_website_snapshot(self.root, self.cfg)
        except HoursConfigError as exc:
            raise HoursServiceError(str(exc)) from exc
        google = fetch_google_snapshot(self.root, self.team_id, self.cfg)
        diff = compute_diff(master, website, google)
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
        hours_payload: dict[str, Any] = master

        try:
            publish_website_snapshot(self.root, self.cfg, hours_payload)
            if self.cfg.google_business.enabled:
                google_path = self.root / "data" / self.team_id / "google_hours.snapshot.json"
                google_path.parent.mkdir(parents=True, exist_ok=True)
                google_path.write_text(
                    json.dumps({"hours": hours_payload}, indent=2) + "\n",
                    encoding="utf-8",
                )
        except HoursConfigError as exc:
            raise HoursServiceError(str(exc)) from exc

        return self.store.mark_published(diff_id)
