# bot

Multi-Agent-Runtime mit Team-Runner, file-basierter Message-Queue und Web-Panel.

## Architektur (zwei Rollen)

| Rolle | Was es ist | Startbefehl |
|--------|------------|-------------|
| **Team-Runner** | Führt Agents aus (`bot run`), optional HTTP-API für Fernzugriff | `bot run` + `bot team serve` |
| **Web-Panel** | Login, Dashboard, Team-Status (lokal oder per API) | `bot web` |

```text
┌─────────────────────┐         HTTPS + Bearer-Token          ┌──────────────────────┐
│  Rechner A          │  ─────────────────────────────────►  │  Rechner B           │
│  Web-Panel          │         (nur bei mode: remote)         │  Team-Runner         │
│  bot web :8080      │                                        │  bot run             │
│  config/team_hosts  │                                        │  bot team serve :8443│
└─────────────────────┘                                        └──────────────────────┘

Alles auf einem Rechner: mode "local" in team_hosts.json — kein API-Token nötig.
```

---

## Voraussetzungen

- Python 3.11+
- Optional: LiteLLM-kompatibler Server (Ollama, LiteLLM-Proxy, …)

## Installation

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## Schnellstart (alles lokal auf einem Rechner)

### 1. Team-Runner starten (Agents arbeiten)

```bash
# Konfiguration prüfen
bot config validate

# Dauerbetrieb: alle Teams, Agent-Loops
bot run

# Nur Demo-Team, ein Durchlauf (Test/Cron)
bot run --team demo --once
```

Der Team-Runner liest `config/`, `teams/<id>/` und die Inboxen unter  
`teams/<id>/agents/<agent>/inbox/`.

### 2. Web-Panel starten (Bedienoberfläche)

```bash
export BOT_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")

bot web
# → http://127.0.0.1:8080
```

Login: `config/users.json` (Demo: **admin** / **changeme** oder **demo** / **changeme**).

Standard: `config/team_hosts.json` verweist auf **lokal** — das Panel liest dieselben Dateien wie der Runner (oder spricht per API mit einem Remote-Runner).

- **Dashboard:** zugängliche Teams (inkl. Runner-Verbindung)
- **Team-Ansicht:** Agents, Message-Status, letzte Nachrichten
- **Chat:** `/teams/<id>/chat` — SQLite-Verlauf (`data/<id>/chat.sqlite`)
- **Wissen:** `/teams/<id>/knowledge` — Qdrant-Suche
- **Admin:** Nutzer, Teams und Team-Runner-Hosts

### 3. Aufgabe auslösen

```bash
bot msg send --team demo --from orchestrator --to orchestrator \
  --subject "Aufgabe" --content "Feature X umsetzen"

bot run --team demo --once   # oder bot run dauerhaft
```

Pipeline: `orchestrator` → `worker-exec` → `worker-review` → `orchestrator`.

---

## Remote: Web-Panel ↔ Team-Runner auf anderem Rechner

Wenn der **Team-Runner** auf Server B läuft und das **Web-Panel** auf Server A, brauchst du:

1. HTTP-API auf dem Team-Runner (`bot team serve`)
2. Ein gemeinsames **API-Token** (`bot team token`)
3. Eintrag in `config/team_hosts.json` auf dem Web-Panel-Rechner

```bash
bot team token --write-config
# → export BOT_TEAM_API_TOKEN=...

# Server B:
export BOT_TEAM_API_TOKEN=<token>
bot run --team demo
bot team serve --host 0.0.0.0 --port 8443

# Server A:
export BOT_TEAM_API_TOKEN=<derselbe-token>
bot web
```

Details und `team_hosts.json`-Beispiele siehe oben in der Architektur-Tabelle.

---

## Phase 2: Qdrant, Team-Chat, Playwright

### Team-Ressourcen initialisieren

```bash
bot team init demo    # chat.sqlite + Qdrant-Collections (wenn Qdrant aktiv)
```

### Qdrant

In `config/system.json`: `qdrant_global.enabled = true`

```bash
bot qdrant init --team demo
bot qdrant upsert --team demo --collection project --text "Projektwissen …"
bot qdrant search --team demo --collection project --query "FastAPI"
```

Collections: `team_<slug>__project`, `team_<slug>__background`

### Team-Chat (SQLite)

```bash
bot chat send --team demo --role user --content "Hallo" --agent orchestrator
bot chat list --team demo
bot chat clear --team demo --yes
```

### Playwright

```bash
pip install -e ".[playwright]"
playwright install chromium
bot browser open --team demo --url https://example.com
```

---

## CLI-Übersicht

| Befehl | Zweck |
|--------|--------|
| `bot config validate` | Konfiguration prüfen |
| `bot run [--team ID] [--once]` | Team-Runner (Supervisor) |
| `bot team serve` / `bot team token` | Remote-API + Token |
| `bot team init <id>` | Chat-DB + Qdrant-Collections |
| `bot web` | Web-Panel |
| `bot msg …` | Agent-Inbox (file-basiert) |
| `bot chat …` | Team-Chat (SQLite) |
| `bot qdrant …` | Vektor-Wissen |
| `bot browser …` | Playwright |
| `bot llm test` | LLM-Verbindung testen |

---

## Konfigurationsdateien

| Datei | Wo | Inhalt |
|-------|-----|--------|
| `config/system.json` | Panel + Runner | System, LLM, Qdrant, Playwright |
| `config/task_models.json` | Panel + Runner | Model-Routing |
| `config/users.json` | Panel | Web-Login |
| `config/team_hosts.json` | Panel | Lokale/Remote Team-Runner |
| `config/team_api.json` | Runner | API-Token (`token_env`) |
| `data/<team>/chat.sqlite` | Runner/Panel | Chat-Historie |
| `teams/<id>/…` | Runner | Teams, Agents, Inboxen |

---

## LLM (LiteLLM)

In `config/system.json`: `"llm": { "enabled": true, … }`.

```bash
export LITELLM_API_KEY=sk-...
bot llm test --task-category coding --prompt "Kurz antworten"
```

Mit `"enabled": false` nutzen die Handler den **Stub**.

---

## Tests

```bash
pytest
```

---

## Ordner

| Pfad | Zweck |
|------|--------|
| `src/bot/` | Anwendungscode |
| `tests/` | Tests |
| `plans/` | Architektur- und MVP-Pläne |

## Sicherheit (Kurz)

- Web-Panel: `BOT_SESSION_SECRET` setzen, HTTPS in Produktion (`bot web --ssl-cert …`).
- Team-API: langer Zufallstoken (`bot team token`), nur VPN/Firewall oder TLS.
- `config/users.json` / Tokens **nicht** committen — Passwörter in Produktion hashen (bcrypt `$2…`).
