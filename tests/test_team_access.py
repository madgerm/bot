
import pytest
from fastapi import HTTPException

from bot.web.auth import SessionUser, UserRecord, _team_access_map
from bot.web.team_access import require_team_write


def test_team_access_map_operator_and_reader() -> None:
    record = UserRecord(
        username="u",
        password="x",
        teams=["demo"],
        team_access=[
            {"team_id": "story", "access": "reader"},
        ],
    )
    m = _team_access_map(record)
    assert m["demo"] == "operator"
    assert m["story"] == "reader"


def test_reader_cannot_write() -> None:
    user = SessionUser(
        username="reader",
        role="user",
        teams=["story"],
        team_access={"story": "reader"},
    )
    with pytest.raises(HTTPException) as exc:
        require_team_write("story", user)
    assert exc.value.status_code == 403


def test_operator_can_write() -> None:
    user = SessionUser(
        username="op",
        role="user",
        teams=["demo"],
        team_access={"demo": "operator"},
    )
    require_team_write("demo", user)
