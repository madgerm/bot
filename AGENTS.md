# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Python skeleton project (`bot`) using `src/` layout. See `README.md` for full docs.

### Development environment

- **Python >=3.11** required (VM has 3.12).
- Virtual environment lives at `.venv/`. The update script handles creation and `pip install -e ".[dev]"`.
- Activate before running commands: `source .venv/bin/activate`

### Key commands

| Task | Command |
|------|---------|
| Run app | `bot` or `python -m bot` |
| Run tests | `pytest` (or `pytest -v`) |

### Gotchas

- The `python3.12-venv` system package must be installed for `python3 -m venv` to work. The update script guards this automatically.
- No linter is configured yet; only `pytest` is available for validation.
- No runtime dependencies exist — only `pytest>=8.0` as a dev dependency.
