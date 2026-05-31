"""Tests für Admin-Medien-Konfiguration."""

from pathlib import Path

from bot.config.media_admin import load_media_global, save_media_global
from bot.config.models import MediaGlobalConfig


def test_save_media_global_roundtrip(runtime_project: Path) -> None:
    media = MediaGlobalConfig()
    media.stt.endpoint = "http://stt.example/transcribe"
    media.tts.endpoint = "http://tts.example/synth"
    media.image_generation.url = "http://img.example/gen"
    save_media_global(runtime_project, media)
    loaded = load_media_global(runtime_project)
    assert loaded.stt.endpoint == "http://stt.example/transcribe"
    assert loaded.image_generation.url == "http://img.example/gen"


def test_admin_media_page(web_project: Path) -> None:
    from fastapi.testclient import TestClient

    from bot.web import create_app

    client = TestClient(create_app(web_project))
    client.get("/login")
    client.post("/login", data={"username": "admin", "password": "secret"})
    r = client.get("/admin/media")
    assert r.status_code == 200
    assert "STT" in r.text
