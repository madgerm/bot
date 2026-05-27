from pathlib import Path

import pytest

from bot.cli import main


def test_cli_msg_send_and_list(project_root: Path | None = None) -> None:
    root = project_root or Path(__file__).resolve().parents[1]

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "msg",
                "send",
                "--root",
                str(root),
                "--team",
                "demo",
                "--from",
                "orchestrator",
                "--to",
                "worker-exec",
                "--subject",
                "CLI-Test",
                "--content",
                "via pytest",
            ]
        )
    assert exc.value.code == 0

    with pytest.raises(SystemExit) as exc:
        main(
            [
                "msg",
                "list",
                "--root",
                str(root),
                "--team",
                "demo",
                "--agent",
                "worker-exec",
                "--status",
                "pending",
            ]
        )
    assert exc.value.code == 0
