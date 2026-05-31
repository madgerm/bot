"""Internet-Relay-Hub."""

from __future__ import annotations

from bot.relay.hub import RelayHub


def test_relay_hub_forwards_panel_to_runner() -> None:
    import asyncio

    hub = RelayHub(token="secret")

    class FakeWS:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send_text(self, text: str) -> None:
            self.sent.append(text)

    runner = FakeWS()
    room = hub._room("test")
    room.runner = runner

    asyncio.run(
        hub._forward(room, "panel", '{"type":"llm.request","id":"1"}')
    )
    assert runner.sent == ['{"type":"llm.request","id":"1"}']


def test_build_relay_ws_url() -> None:
    from bot.channel.urls import build_relay_ws_url

    url = build_relay_ws_url(
        "wss://relay.example.com:9000/ws",
        role="panel",
        room="home",
        token="tok",
    )
    assert "role=panel" in url
    assert "room=home" in url
    assert "token=tok" in url
