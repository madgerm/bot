# Betriebshandbuch (Kurz)

Typischer Ablauf für **einen Rechner** (lokal oder Server).

## 0. Debian/Ubuntu-Installation (Skript)

```bash
curl -fsSL https://raw.githubusercontent.com/madgerm/bot/main/scripts/install-debian.sh -o /tmp/bot-install-debian.sh && bash /tmp/bot-install-debian.sh
```

Das Skript fragt:

1. **Team-Runner**, **Web-Panel** oder **beides**
2. **systemweit** (`/opt/bot`, User `bot`, `/etc/bot/env`) oder **nur Ihr Benutzer** (`~/bot`, `~/.config/bot/env`)
3. optional **systemd**-Dienste

Demo-Logins: `admin` / `changeme`, `demo` / `changeme`, `reader` / `changeme` — Details in `README.md`.

## 1. Vorbereitung (manuell)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# BOT_SESSION_SECRET, ggf. LITELLM_API_KEY setzen
bot auth hash-password   # → config/users.json
bot config validate
```

Optionale Extras **nur bei Bedarf**:

| Extra | Install | Zweck |
|--------|---------|--------|
| `playwright` | `pip install -e ".[playwright]"` + `playwright install chromium` | `bot browser` |
| `crawl` | `pip install -e ".[crawl]"` | Crawl4AI → Qdrant |

## 2. Dauerbetrieb

**Terminal 1 — Team-Runner (Agents):**

```bash
bot run
# oder ein Team: bot run --team demo
```

**Terminal 2 — Web-Panel:**

```bash
export BOT_SESSION_SECRET=...
bot web
# → http://127.0.0.1:8080
```

Remote: zusätzlich `bot team serve` auf dem Runner-Rechner und `config/team_hosts.json` auf dem Panel.

## 3. Cron / periodische Jobs

| Aufgabe | Beispiel |
|---------|----------|
| E-Mail abholen | `*/5 * * * * bot mail poll --team mein-team` |
| Öffnungszeiten prüfen | `0 8 * * * bot hours queue --team mein-team` |
| Einmal-Pipeline | `bot run --team demo --once` |
| Backup | `0 2 * * * bot backup create` |

## 4. Backup & Restore

```bash
bot backup list
bot backup create                    # alle Teams unter data/
bot backup create --team demo
bot backup restore data/_backups/bot-backup-....tar.gz --dry-run
bot backup restore data/_backups/bot-backup-....tar.gz
```

Sichert `data/<team>/*.sqlite`, Workspace und optional `teams/<team>/` (ohne Inbox/Outbox).

## 5. Docker Compose (Beispiel)

```bash
cd deploy
export BOT_SESSION_SECRET=...
export BOT_TEAM_API_TOKEN=...
docker compose up -d team-runner web-panel team-api
# Mit Qdrant: docker compose --profile qdrant up -d
```

HTTPS: `deploy/Caddyfile` vor den Containern (Reverse Proxy).

## 6. Monitoring

- `GET /health` — Queue-Tiefen, `worker_mode`, `inbox_watch_seconds`
- Logs: strukturierte Zeilen mit `team_id`, `agent_id`, `message_id`

## 7. Medien (Produktion)

- Beispiel-JSON: `config/media.production.example.json`
- Im Panel (Admin): `/admin/media` — globale STT/TTS/Bild-URLs in `config/system.json` pflegen
- Team-Overrides: `teams/<id>/media.json` oder Formular auf derselben Seite
- Status stub/live: Team-Seite `/teams/<id>/media` und Admin-Übersicht

## 8. Entwicklung & CI

```bash
pytest
ruff check src tests
mypy src/bot
pip install -r requirements-lock.txt && pip install -e . --no-deps
```

Lockfile aktualisieren: `./scripts/lock-deps.sh`  
CI prüft, dass `requirements-lock.txt` zum `pyproject.toml` passt.
