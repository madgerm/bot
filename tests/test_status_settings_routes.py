"""HTMX-Status-Fragmente (/admin/settings/status)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bot.web import create_app


@pytest.fixture
def web_project(runtime_project: Path) -> Path:
    (runtime_project / "config" / "users.json").write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "admin",
                        "password": "secret",
                        "role": "admin",
                        "teams": ["alpha"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return runtime_project


@pytest.fixture
def client(web_project: Path) -> TestClient:
    return TestClient(create_app(web_project))


def _login(client: TestClient) -> None:
    client.get("/login")
    client.post(
        "/login",
        data={"username": "admin", "password": "secret"},
        follow_redirects=False,
    )


def test_status_page_htmx_shell(client: TestClient) -> None:
    _login(client)
    r = client.get("/admin/settings/status")
    assert r.status_code == 200
    assert "hx-get=\"/admin/settings/status/fragment\"" in r.text
    assert "status-live" in r.text


def test_status_fragment_hosts(client: TestClient) -> None:
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment/hosts",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "status-hosts" in r.text
    assert "Erneut testen" in r.text


def test_status_fragment_single_host(client: TestClient) -> None:
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment/hosts/local",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert 'id="host-local"' in r.text


def test_status_fragment_full(client: TestClient) -> None:
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "status-llm" in r.text
    assert "status-qdrant" in r.text


def test_status_fragment_requires_admin(client: TestClient) -> None:
    assert client.get("/admin/settings/status/fragment").status_code == 401


def test_llm_http_ping(monkeypatch: pytest.MonkeyPatch, runtime_project: Path) -> None:
    from bot.config.writers.hosts_admin import probe_llm_http

    (runtime_project / "config" / "system.json").write_text(
        (
            (runtime_project / "config" / "system.json").read_text()
            if (runtime_project / "config" / "system.json").is_file()
            else "{}"
        ),
        encoding="utf-8",
    )
    # Ensure LLM enabled with api_base
    import json

    sys_path = runtime_project / "config" / "system.json"
    data = json.loads(sys_path.read_text())
    data.setdefault("system", {})["llm"] = {
        "enabled": True,
        "api_base": "http://llm.test:4000",
        "secret_ref": None,
    }
    sys_path.write_text(json.dumps(data), encoding="utf-8")

    class _Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url: str, headers=None):
            assert "http://llm.test:4000" in url
            return _Resp()

    monkeypatch.setattr("bot.config.writers.hosts_admin.httpx.Client", _Client)
    result = probe_llm_http(runtime_project)
    assert result["ping_ok"] is True
    assert "HTTP 200" in result["ping_summary"]


def test_status_fragment_llm_ping(client: TestClient) -> None:
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment/llm?ping=1",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "API-Ping" in r.text or "ping" in r.text.lower()


def test_status_fragment_mail(client: TestClient, web_project: Path) -> None:
    from tests.test_mail_status import _write_email

    _write_email(web_project)
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment/mail",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "status-mail" in r.text
    assert "alpha" in r.text


def test_status_fragment_includes_mail(client: TestClient, web_project: Path) -> None:
    from tests.test_mail_status import _write_email

    _write_email(web_project)
    _login(client)
    r = client.get(
        "/admin/settings/status/fragment",
        headers={"HX-Request": "true"},
    )
    assert r.status_code == 200
    assert "status-mail" in r.text
