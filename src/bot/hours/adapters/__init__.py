"""Quellen für Website- und Google-Snapshots."""

from bot.hours.adapters.google import fetch_google_snapshot
from bot.hours.adapters.website import fetch_website_snapshot

__all__ = ["fetch_website_snapshot", "fetch_google_snapshot"]
