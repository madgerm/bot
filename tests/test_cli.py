from pathlib import Path

import pytest

from bot.cli import main


def test_cli_config_validate_ok() -> None:
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(SystemExit) as exc:
        main(["config", "validate", "--root", str(root)])
    assert exc.value.code == 0
