# bot

Python-Projekt mit `src/`-Layout und Ordner **`plans/`** für Entwürfe und technische Planung.

## Voraussetzungen

- Python 3.11+

## Einrichtung

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Nutzung

```bash
bot --help
bot config validate          # Konfiguration prüfen
bot config show              # Geladene Config als JSON
bot config watch             # Hot-Reload (Änderungen an config/ und teams/)

# oder
python -m bot config validate
```

Konfigurationsdateien:

| Pfad | Inhalt |
|------|--------|
| `config/system.json` | System (LLM, Polling, Auth, …) |
| `config/task_models.json` | Optional: Model-Routing pro Task-Kategorie |
| `teams/<id>/team.json` | Team-Metadaten |
| `teams/<id>/agents/<agent>/agent.json` | Agent-Definition |

## Tests

```bash
pytest
```

## Ordner

| Pfad | Zweck |
|------|--------|
| `src/bot/` | Anwendungscode |
| `tests/` | Tests |
| `plans/` | Pläne, Roadmaps, Architektur-Skizzen (`plans/README.md`, `plans/TEMPLATE.md`) |

## Paket umbenennen

Paketname und Projektname stehen in `pyproject.toml` (`name`, `[project.scripts]`, Import `bot`). Bei Umbenennung diese Stellen und den Ordner `src/bot/` anpassen.
