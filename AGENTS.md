# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Multi-Agent-Runtime (`bot`): Team-Runner (file-Inbox, Agent-Subprozesse), Web-Panel, Qdrant, Story/Mail/Hours. Layout: `src/bot/`, `tests/`, `docs/OPERATIONS.md`.

### Development environment

- **Python >=3.11** (3.12 empfohlen)
- `python -m venv .venv && source .venv/bin/activate`
- `pip install -e ".[dev]"` — Runtime-Deps sind in `pyproject.toml` (kein Skeleton mehr)
- `.env.example` → `.env` (nicht committen)

### Key commands

| Task | Command |
|------|---------|
| Debian install | `bash scripts/install-debian.sh` (README: One-Liner) |
| Config | `bot config validate` |
| Runner | `bot run` / `bot run --once` |
| Web | `bot web` |
| Backup | `bot backup create` / `bot backup list` |
| Medien (Admin) | Panel `/admin/media` |
| Audit | Automatisch bei POST (`data/audit.sqlite`) |
| Tests | `pytest` |
| Lint | `ruff check src tests` |
| Types | `mypy src/bot` |

### Optional dependencies (nicht Standard-Deploy)

| Extra | Install |
|-------|---------|
| Dev-Tools | `pip install -e ".[dev]"` |
| Playwright | `pip install -e ".[playwright]"` + `playwright install chromium` |
| Crawl4AI | `pip install -e ".[crawl]"` |

### Gotchas

- `config/users.json`: Demo-Passwörter nur lokal; Produktion `bot auth hash-password`
- `BOT_SESSION_SECRET`, `BOT_TEAM_API_TOKEN` in Produktion setzen
- Web-Tests: zuerst `GET /login` (CSRF-Cookie)
- `bot run --once` erzwingt `worker_mode: thread`; Dauerbetrieb nutzt `process` aus `system.json`
- Qdrant-Reindex importiert Crawl **ohne** crawl4ai-Modul (nur `crawl.json` + Markdown-Dateien)
- CI: `requirements-lock.txt` + `pip install -e . --no-deps`; Lock aktualisieren: `./scripts/lock-deps.sh`
- Panel-Audit: alle erfolgreichen POSTs → `data/audit.sqlite` (Middleware)
