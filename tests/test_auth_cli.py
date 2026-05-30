"""CLI auth hash-password."""

from bot.web.auth import hash_password, verify_password


def test_hash_password_roundtrip() -> None:
    hashed = hash_password("geheim")
    assert hashed.startswith("$2")
    assert verify_password("geheim", hashed)
    assert not verify_password("falsch", hashed)
