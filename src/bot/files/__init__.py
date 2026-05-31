"""Sicherer Datei-Browser für Team-Workspaces."""

from bot.files.service import FileEntry, FileService, FileServiceError

__all__ = ["FileService", "FileServiceError", "FileEntry"]
