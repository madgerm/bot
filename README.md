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

Pipeline (konfigurierbar pro Team): z. B. Demo `orchestrator` → `worker-exec` → `worker-review`; Coding `coder` → `tester` → `doku`; Story `drehbuch-autor` → `logik-pruefer`. Agents nutzen **Tools** (Dateien, Git, Qdrant, Browser, Story-Szenen) im LLM-Loop.

**Agent-Loop:** Jeder Agent hat einen **Inbox-Watch-Thread** (`inbox_watch_seconds`, Standard 0,5s) — neue Dateien in `inbox/` wecken den Loop sofort. Ohne Änderung gilt `interval_seconds` als Idle-Polling. Standardmäßig läuft jeder Agent in einem **eigenen OS-Prozess** (`worker_mode: "process"` in `config/system.json`); für Tests/Cron nutzt `bot run --once` intern Threads.

Fertige Team-Presets: `teams/demo/`, `teams/coding/`, `teams/story/`.

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
| `bot mail …` | E-Mail (IMAP/SMTP, Freigabe) |
| `bot hours …` | Öffnungszeiten (Master, Diff, Publish) |
| `bot tasks …` | Task Board (SQLite) |
| `bot git …` | Git pro Team-Workspace |
| `bot crawl …` | Domain-Crawl + Qdrant |
| `bot story …` | Story (Charaktere, Welten, Szenen, Export EPUB/PDF) |
| `bot qdrant reindex` | Workspace + Crawl in Qdrant indexieren |
| `bot run` + `qdrant_global.reindex` | Periodischer Reindex + Workspace-Watch während der Laufzeit |
| `bot media …` | Vision, STT, TTS, Bilder |
| `bot deploy …` | systemd + Provision (Linux-User/Team) |
| `bot llm test` | LLM-Verbindung testen |

---

## Phase 3: Plattform-Erweiterungen

### Webhooks (eingehend)

```bash
export BOT_WEBHOOK_SECRET=...
curl -X POST http://127.0.0.1:8080/api/v1/webhooks/demo/orchestrator \
  -H "X-Webhook-Token: $BOT_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"subject":"CI","content":"Deploy auslösen"}'
```

### Task Board, Agent Manager, Dateien, Git, Story

Web-Panel (pro Team):

| Pfad | Funktion |
|------|----------|
| `/teams/<id>/tasks` | Kanban (todo / in progress / done) |
| `/teams/<id>/agents` | Agents anlegen/löschen |
| `/teams/<id>/files` | Datei-Browser + Editor (`data/<id>/workspace`) |
| `/teams/<id>/git` | Status, Commit |
| `/teams/<id>/story` | Story Studio (Hub) |
| `/teams/<id>/story/planner` | Story anlegen (AGENTS.md, meta.json) |
| `/teams/<id>/story/characters` | Character Manager (JSON + Beziehungen) |
| `/teams/<id>/story/world` | World Editor (orte.md, regeln.md, timeline.md) |
| `/teams/<id>/story/scenes` | Szenen-Editor (Kapitel/szene-*.md, Version) |
| `/teams/<id>/story/review` | Review Panel (issues.jsonl) |
| `/teams/<id>/media` | Bildgenerierung |
| `/teams/<id>/crawl` | Domain-Crawl → Qdrant |

CLI: `bot tasks`, `bot git`, `bot story`, `bot crawl`, `bot media image`.

### Multi-Machine (nur Dateien)

Agent-Kommunikation bleibt **file-basiert** (`inbox/`/`outbox/`). Für mehrere Rechner: gemeinsames Dateisystem (NFS/SSH-Mount) und optional `communication.multi_machine.shared_inbox_base` in `config/system.json` — **kein Redis**.

### Medien, Crawl, Integrationen

- **Medien:** `media_global` in `system.json`, Override: `teams/<id>/media.json`
- **Crawl4AI:** `pip install -e ".[crawl]"` · `teams/<id>/crawl.json` — liefert **fit_markdown** (ohne Menü/Navigation) unter `data/<id>/crawl/`
- **Telegram/Matrix:** `teams/<id>/integrations.json` → `POST /api/v1/integrations/<team>/telegram|matrix`

### Deployment (Linux-User pro Team)

```bash
bot deploy generate --team demo
# → deploy/demo/bot-team@demo.service, provision-demo.sh
```

Admin-UI: `/admin/deploy`

---

## E-Mail-Team (IMAP, Freigabe, Versand)

**Rollen:** Admin legt Team + `teams/<id>/email.json` an; **alle Team-Nutzer** bearbeiten, freigeben und senden.

```bash
export FIRMA_IMAP_PASSWORD=...
export FIRMA_SMTP_PASSWORD=...
cp teams/demo/email.json.example teams/mein-team/email.json
bot team init mein-team
bot mail poll --team mein-team
bot mail draft --team mein-team --thread <uuid> --body "Antwort…"
bot mail approve --team mein-team --draft <uuid> --approved-by max
bot mail send --team mein-team --draft <uuid>
```

Web-Panel: `/teams/<id>/mail` — Entwurf, **Freigeben**, dann **SEND** bestätigen.

Agents versenden **nicht** selbst; Versand nur nach Status `approved`.

---

## Öffnungszeiten (Agent liest Website)

Der **hours_checker**-Agent lädt die konfigurierte URL, extrahiert Öffnungszeiten per LLM und vergleicht mit dem **Master**. Keine zweite JSON-Datei manuell pflegen.

```bash
cp teams/demo/hours.json.example teams/mein-team/hours.json
cp teams/demo/hours.master.json.example teams/mein-team/hours.master.json

bot hours check --team mein-team
bot hours queue --team mein-team   # Auftrag → bot run
bot hours approve --team mein-team --diff <uuid> --approved-by max
bot hours publish --team mein-team --diff <uuid>
```

`hours.json`: `website.type: "page"` + URL; `publish` für Ziel nach Freigabe (file/http).  
Legacy: `website.type: file|http` ohne Seitenlesen.

Web-Panel: `/teams/<id>/hours`

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
| `data/<team>/email.sqlite` | Runner/Panel | E-Mail-Threads, Entwürfe |
| `data/<team>/hours.sqlite` | Runner/Panel | Öffnungszeiten-Diffs |
| `teams/<id>/email.json` | Runner/Panel | IMAP/SMTP (Secrets per Env) |
| `teams/<id>/hours.json` | Runner/Panel | Website/Google-Abgleich |
| `teams/<id>/hours.master.json` | Runner/Panel | Kanonische Öffnungszeiten |
| `data/<team>/tasks.sqlite` | Runner/Panel | Task Board |
| `data/<team>/story.sqlite` | Runner/Panel | Story-Daten |
| `data/<team>/workspace/` | Runner/Panel | Datei-Browser / Git |
| `teams/<id>/git.json` | Runner/Panel | Git-Remote/Branch |
| `teams/<id>/crawl.json` | Runner/Panel | Crawl-Domains |
| `teams/<id>/integrations.json` | Runner/Panel | Telegram, Matrix |
| `teams/<id>/media.json` | Runner/Panel | Medien-Overrides |
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
- `config/users.json` / Tokens **nicht** committen — Passwörter in Produktion hashen:
  ```bash
  bot auth hash-password   # bcrypt-Hash in users.json eintragen
  ```
- Umgebungsvariablen: siehe `.env.example` (CSRF, Rate-Limits, Secrets).
- `/health` liefert Queue-Tiefen (pending/processing) pro Agent — für Monitoring.
