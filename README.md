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
| `teams/<id>/agents/<agent>/inbox/` | Eingehende Messages (`pending` → `processing` → `done`/`failed`) |
| `teams/<id>/agents/<agent>/outbox/` | Kopie gesendeter Messages |

### Nachrichten (MVP Schritt 2)

```bash
bot msg send --team demo --from orchestrator --to worker-exec \
  --subject "Aufgabe" --content "Bitte ausführen"
bot msg list --team demo --agent worker-exec --status pending
bot msg claim --team demo --agent worker-exec
bot msg done --team demo --agent worker-exec --id <message-id>
bot msg fail --team demo --agent worker-exec --id <message-id> --error "Grund"
bot msg retry --team demo --agent worker-exec --id <message-id>
```

Message-JSON: `id`, `schema_version`, `status`, `created_at`/`updated_at`, `from_agent`/`to_agent`, optional `task_category`, `retry_count`.

### Runtime / Supervisor (MVP Schritt 3)

```bash
# Dauerbetrieb: alle Teams, Agent-Loops mit Polling
bot run

# Nur Demo-Team, ein Durchlauf bis alle Queues leer (Tests/Cron)
bot run --team demo --once

# Mit Config Hot-Reload
bot run --watch-config
```

Ablauf (Demo-Team): Aufgabe an `orchestrator` → `worker-exec` → `worker-review` → Ergebnis zurück an `orchestrator`.

### LLM / LiteLLM (MVP Schritt 4)

In `config/system.json`: `"llm": { "enabled": true, "api_base": "…", … }` und `config/task_models.json` für Model-Routing.

```bash
# API-Key z. B. als Umgebungsvariable (Name aus secret_ref)
export LITELLM_API_KEY=sk-...

bot llm test --task-category coding --prompt "Kurz antworten"
bot run --team demo --once   # nutzt LLM in den Handlern, wenn enabled
```

- **Routing:** `task_category` oder Rollen-Default (`planning` / `coding` / `review`)
- **Override:** `model_override` in der Message
- **Retries + Fallback:** `max_retries`, Alternativen aus `task_models.json`
- **`enabled: false`:** Stub-Client (für lokale Tests ohne API)

### Web-Panel (MVP Schritt 5)

```bash
# Optional: sicheres Session-Secret setzen
export BOT_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

bot web                    # http://127.0.0.1:8080
bot web --ssl-cert cert.pem --ssl-key key.pem   # HTTPS

# Login: config/users.json (Demo: admin/changeme, demo/changeme)
```

- **Dashboard:** zugängliche Teams
- **Team-Ansicht:** Agents, Message-Status, letzte Nachrichten
- **Admin:** Nutzer- und Team-Übersicht (nur Rolle `admin`)
- Session-Cookies + **Team-Scoping** auf jeder Route
- **Chat:** `/teams/<id>/chat` — SQLite-Verlauf (`data/<id>/chat.sqlite`)
- **Wissen:** `/teams/<id>/knowledge` — Qdrant-Suche

---

## Phase 2: Qdrant, Team-Chat, Playwright

### Team initialisieren

```bash
bot team init demo    # legt chat.sqlite + Qdrant-Collections an (wenn Qdrant aktiv)
```

### Qdrant (Vektor-Wissen pro Team)

In `config/system.json`:

```json
"qdrant_global": {
  "enabled": true,
  "url": "http://127.0.0.1:6333",
  "secret_ref": "QDRANT_API_KEY",
  "embedding": { "provider": "hash", "vector_size": 384 }
}
```

- Collections: `team_<slug>__project`, `team_<slug>__background`
- Registry: `data/<team>/qdrant_registry.json`

```bash
export QDRANT_API_KEY=...   # falls Qdrant Cloud/auth
bot qdrant init --team demo
bot qdrant upsert --team demo --collection project --text "Unsere API nutzt FastAPI"
bot qdrant search --team demo --collection project --query "FastAPI"
```

`embedding.provider`: `hash` (offline/Tests) oder `litellm` (echte Embeddings).

### Team-Chat (SQLite-Historie)

Pro Team eine Datei: **`data/<team_id>/chat.sqlite`**

```bash
bot chat send --team demo --role user --content "Hallo Team" --agent orchestrator
bot chat list --team demo
bot chat list --team demo --agent orchestrator --search "Hallo"
bot chat clear --team demo --yes
```

Im Web-Panel: Team → **Chat** — senden, filtern, Verlauf leeren (Bestätigung `CLEAR`).

### Playwright (Browser)

Global in `config/system.json` → `playwright_global`:

```json
"playwright_global": {
  "mode": "local",
  "headless": true,
  "ws_endpoints": []
}
```

Team-Override: `teams/<id>/playwright.json`:

```json
{
  "playwright": {
    "source": "custom",
    "mode": "remote",
    "ws_endpoints": ["ws://browser-host:9222"]
  }
}
```

Installation:

```bash
pip install -e ".[playwright]"
playwright install chromium
```

```bash
bot browser config --team demo
bot browser open --team demo --url https://example.com --screenshot data/demo/screenshots/example.png
```

| Modus | Bedeutung |
|-------|-----------|
| `local` | Browser auf dem Rechner des Team-Runners |
| `remote` | Verbindung über `ws_endpoints` (CDP/WebSocket) |

---

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
