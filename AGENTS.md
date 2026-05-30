# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Multi-Agent-Runtime (`bot`) mit Team-Runner, file-basierter Message-Queue und Web-Panel. `src/`-Layout. Siehe `README.md`.

### Development environment

- **Python >=3.11** (VM: 3.12).
- Virtual environment: `.venv/` — `pip install -e ".[dev]"`.
- Aktivieren: `source .venv/bin/activate`
- Umgebungsvariablen: `.env.example` → `.env` (nicht committen).

### Key commands

| Task | Command |
|------|---------|
| Config prüfen | `bot config validate` |
| Team-Runner | `bot run` |
| Web-Panel | `bot web` |
| Passwort hashen | `bot auth hash-password` |
| Tests | `pytest` |
| Lint (optional) | `ruff check src tests` |

### Gotchas

- `python3.12-venv` wird für `python3 -m venv` benötigt.
- `config/users.json`: Demo-Passwörter nur lokal; Produktion bcrypt (`bot auth hash-password`).
- `BOT_SESSION_SECRET` in Produktion setzen.
- Tests deaktivieren CSRF nicht standardmäßig — `TestClient` nach `GET /login` nutzen, damit CSRF-Cookie gesetzt ist.
- Optionale Extras: `pip install -e ".[playwright]"` / `".[crawl]"`.
