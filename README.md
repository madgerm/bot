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

## Installation (Debian/Ubuntu)

Das interaktive Skript `scripts/install-debian.sh` richtet **Team-Runner**, **Web-Panel** oder **beides** ein, prüft Voraussetzungen (Python ≥3.11, `python3-venv`, Git, SQLite3, …) und installiert fehlende Pakete per `apt` nach Rückfrage.

### One-Liner (empfohlen)

**Interaktiv** (fragt: Runner / Web / beides, systemweit oder nur Ihr Benutzer):

```bash
curl -fsSL https://raw.githubusercontent.com/madgerm/bot/main/scripts/install-debian.sh -o /tmp/bot-install-debian.sh && bash /tmp/bot-install-debian.sh
```

**Systemweit** unter `/opt/bot` (benötigt `sudo`, Dienstbenutzer `bot`, optional systemd):

```bash
curl -fsSL https://raw.githubusercontent.com/madgerm/bot/main/scripts/install-debian.sh -o /tmp/bot-install-debian.sh && sudo bash /tmp/bot-install-debian.sh
```

**Nur für den aktuellen Benutzer** nach `~/bot` (ohne root):

```bash
curl -fsSL https://raw.githubusercontent.com/madgerm/bot/main/scripts/install-debian.sh | bash -s --
```

**Nicht-interaktiv** (z. B. Automatisierung): Runner + Panel, Benutzer-Installation nach `~/bot`:

```bash
curl -fsSL https://raw.githubusercontent.com/madgerm/bot/main/scripts/install-debian.sh | BOT_INSTALL_NONINTERACTIVE=1 BOT_INSTALL_MODE=both BOT_INSTALL_SCOPE=user bash -s --
```

Aus dem **bereits geklonten** Repository (ohne erneuten Download):

```bash
git clone https://github.com/madgerm/bot.git && cd bot && bash scripts/install-debian.sh
```

| Variable | Werte | Bedeutung |
|----------|--------|-----------|
| `BOT_INSTALL_MODE` | `runner`, `web`, `both` | Was installiert wird |
| `BOT_INSTALL_SCOPE` | `user`, `system` | Nur Ihr Login vs. `/opt/bot` + `bot`-User |
| `BOT_INSTALL_DIR` | Pfad | Zielverzeichnis (Standard: `~/bot` oder `/opt/bot`) |
| `BOT_REPO_URL` / `BOT_REPO_BRANCH` | | Quelle beim Download-Install |
| `BOT_INSTALL_PLAYWRIGHT` | `0`/`1` | Playwright + Chromium (interaktiv: Rückfrage) |
| `BOT_INSTALL_CRAWL` | `0`/`1` | Crawl4AI-Extra |
| `BOT_INSTALL_QDRANT` | `0`/`1` | Qdrant-Container per Docker Compose |
| `BOT_INSTALL_AUTOSTART` | `0`/`1` | systemd enable (nur mit `NONINTERACTIVE`) |

**Vollständig inkl. Extras + Autostart (nicht-interaktiv):**

```bash
curl -fsSL https://raw.githubusercontent.com/madgerm/bot/main/scripts/install-debian.sh | BOT_INSTALL_NONINTERACTIVE=1 BOT_INSTALL_MODE=both BOT_INSTALL_SCOPE=system BOT_INSTALL_PLAYWRIGHT=1 BOT_INSTALL_CRAWL=1 BOT_INSTALL_QDRANT=1 BOT_INSTALL_AUTOSTART=1 sudo -E bash -s --
```

Nach der Installation: `bot` liegt bei systemweiter Installation in `/usr/local/bin/bot`, sonst in `~/.local/bin/bot` (ggf. `export PATH="$HOME/.local/bin:$PATH"`).

### Was das Skript einrichtet

| Komponente | Standard | Optional (Rückfrage im Installer) |
|------------|----------|-------------------------------------|
| Python-venv + Bot-Kern (`pip`) | ja | — |
| Team-Runner / Web-Panel | nach Auswahl | — |
| `config/`, Demo-Teams | ja | — |
| Secrets (`BOT_SESSION_SECRET` …) | ja (Web) | — |
| **Autostart nach Neustart** | nein | **ja** — `systemctl enable` + Start; bei Benutzer-Install zusätzlich `loginctl enable-linger` |
| **Playwright** (`bot browser`) | nein | pip-Extra + `playwright install-deps` + Chromium |
| **Crawl4AI** (`bot crawl`) | nein | pip-Extra |
| **Qdrant** (Vektor-Wissen) | nein | Docker installieren/starten; danach `qdrant_global.enabled` in `config/system.json` |

**Geprüfte Systempakete:** `python3` (≥3.11), `python3-venv`, `python3-dev`, `git`, `sqlite3`, `build-essential`, `curl`, `ca-certificates`.  
**SQLite** für Chat/Tasks/E-Mail ist in Python enthalten — kein separater DB-Server.  
**LLM/Ollama/LiteLLM** werden nicht mitinstalliert — nur Hinweis in `.env` / `config/system.json`.

### Initiale Web-Zugänge (Demo)

Aus `config/users.json` — **in Produktion sofort ändern** (`bot auth hash-password`):

| Benutzer | Passwort | Rolle / Zugriff |
|----------|----------|------------------|
| `admin` | `changeme` | Administrator, Teams demo / coding / story |
| `demo` | `changeme` | Operator für Team `demo` |
| `reader` | `changeme` | Nur Lesen (`reader`) für Team `story` |

Session-Geheimnis: wird beim Install in `~/.config/bot/env` (Benutzer) oder `/etc/bot/env` (systemweit) erzeugt — nicht committen.

### Nach der Installation

**Nur Team-Runner (Agents):**

```bash
set -a && source ~/.config/bot/env && set +a   # oder: source /etc/bot/env
cd ~/bot && source .venv/bin/activate
bot config validate
bot run
```

**Nur Web-Panel:**

```bash
set -a && source ~/.config/bot/env && set +a
bot web
# → http://127.0.0.1:8080
```

**Beides auf einem Rechner** (Standard nach Install-Option „3“):

```bash
# Terminal 1
set -a && source ~/.config/bot/env && set +a && bot run
# Terminal 2
set -a && source ~/.config/bot/env && set +a && bot web
```

**systemd (falls beim Install gewählt):**

```bash
sudo systemctl status bot-team-runner bot-web-panel
sudo journalctl -u bot-web-panel -f
```

Ausführliches Betriebshandbuch: `docs/OPERATIONS.md` · Docker: `deploy/docker-compose.yml`

---

## Installation (manuell / Entwicklung)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"     # Runtime + pytest/ruff/mypy
cp .env.example .env        # Secrets setzen
bot config validate
```

**Optionale Extras** (nicht für jedes Deployment nötig):

| Extra | Befehl | Zweck |
|-------|--------|--------|
| `playwright` | `pip install -e ".[playwright]"` | `bot browser` |
| `crawl` | `pip install -e ".[crawl]"` | Crawl4AI → Qdrant |

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

Login: siehe Tabelle **Initiale Web-Zugänge** oben (`admin` / `changeme`, …).

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

Typisches Setup: **Team-Runner auf VPS** (Internet), **Web-Panel + Ollama im LAN** — du steuerst alles nur über das Panel; Ollama muss vom VPS aus **nicht** erreichbar sein.

### 1. Panel steuert Runner (Dashboard)

1. HTTP-API auf dem Team-Runner (`bot team serve`)
2. Gemeinsames **API-Token** (`bot team token`)
3. `config/team_hosts.json` auf dem Panel mit `mode: "remote"`

```bash
bot team token --write-config

# VPS (Team-Runner):
export BOT_TEAM_API_TOKEN=<token>
bot run
bot team serve --host 0.0.0.0 --port 8443

# LAN (Web-Panel):
export BOT_TEAM_API_TOKEN=<derselbe-token>
bot web
```

### 2. Runner nutzt Panel als LLM-Proxy (Ollama nur im LAN)

Agents auf dem VPS rufen **kein** Ollama direkt an, sondern `POST /api/v1/llm/complete` auf dem Panel; das Panel leitet an LiteLLM/Ollama weiter.

| Rechner | `config/system.json` | Rolle |
|---------|----------------------|--------|
| **LAN (Panel)** | `llm.mode: "direct"`, `api_base` → Ollama/LiteLLM lokal | Proxy-Ziel |
| **VPS (Runner)** | `llm.mode: "proxy"`, `llm.proxy.base_url` → Panel-URL | Agents |

Beispiel-Konfigurationen: `config/system.panel-lan.example.json`, `config/system.runner-proxy.example.json`.

**Panel (LAN)** — Ollama erreichbar, Proxy-API aktiv:

```json
"llm": {
  "enabled": true,
  "mode": "direct",
  "api_base": "http://127.0.0.1:11434"
}
```

```bash
export BOT_LLM_PROXY_TOKEN=<langer-zufallswert>   # oder BOT_TEAM_API_TOKEN
# optional config/team_api.json: { "token_env": "BOT_LLM_PROXY_TOKEN" }
bot web --host 0.0.0.0 --port 8080
```

**Runner (VPS)** — nur Proxy, kein Ollama:

```json
"llm": {
  "enabled": true,
  "mode": "proxy",
  "proxy": {
    "base_url": "https://panel.dein-lan.de:8080",
    "token_env": "BOT_LLM_PROXY_TOKEN"
  }
}
```

```bash
export BOT_LLM_PROXY_TOKEN=<derselbe-wert-wie-am-panel>
bot run
```

Das Panel muss vom VPS aus erreichbar sein (HTTPS, VPN, Tailscale oder Reverse-Tunnel). Latenz VPS ↔ LAN ist für die Agent-Loops unkritisch, solange das Panel erreichbar bleibt.

**Hinweis:** Chat, Dateien und Qdrant nutzen weiterhin das Projekt-`root` am Panel — für volle Remote-Verwaltung gemeinsames Datenverzeichnis oder spätere API-Erweiterungen. Der **LLM-Proxy** deckt die Agent-Modellaufrufe ab.

### 3. Kanal-Modus (empfohlen): Panel verbindet sich zum Runner

Wie ein **Chat**: Das Panel baut **eine ausgehende** WebSocket-Verbindung zum VPS auf (`wss://…/api/v1/channel/ws`). Darüber laufen LLM-Anfragen in beide Richtungen — der **Runner muss das Panel nicht im Internet erreichen**.

| | Panel (LAN) | Runner (VPS) |
|---|-------------|----------------|
| Verbindung | verbindet sich → Runner | `bot team serve` (WebSocket) |
| LLM | `llm.mode: direct` → Ollama | `llm.mode: channel` |
| Konfig | `team_hosts.json` → `"channel": true` | `data/_channel/llm_queue.sqlite` (Cache bei Ausfall) |

**LLM-Anfragen** werden auf dem Runner **persistent gecacht**, bis das Panel wieder verbunden ist. **Ping/HTTP-Status** dürfen fehlschlagen, ohne die Queue zu löschen.

Beispiele: `config/system.panel-lan.example.json`, `config/system.runner-channel.example.json`, `config/team_hosts.channel.example.json`.

**VPS:**

```json
"llm": { "enabled": true, "mode": "channel", "timeout_seconds": 600 }
```

```bash
export BOT_TEAM_API_TOKEN=<token>
bot run
bot team serve --host 0.0.0.0 --port 8443
```

**LAN (Panel):**

```json
"llm": { "enabled": true, "mode": "direct", "api_base": "http://127.0.0.1:11434" }
```

`config/team_hosts.json`:

```json
{
  "hosts": [{
    "id": "vps",
    "mode": "remote",
    "base_url": "https://runner.example.com:8443",
    "token_env": "BOT_TEAM_API_TOKEN",
    "channel": true,
    "teams": ["demo"]
  }]
}
```

```bash
export BOT_TEAM_API_TOKEN=<derselbe-token>
bot web
```

Das Panel startet den Kanal-Connector automatisch beim `bot web`-Start.

#### Satellit-Runner: was über den Kanal läuft (`llm.mode: channel`)

| Dienst | Über Panel-Kanal | Nur am Panel (LAN) |
|--------|------------------|---------------------|
| **LLM / Ollama** | ja (gecached) | `qdrant_global`, Embeddings |
| **Qdrant-Suche** (`qdrant_search` Tool) | ja | Qdrant-Server |
| **Workspace → Qdrant** (`index_workspace` Tool) | ja | Index liest Panel-`data/…/workspace` |
| **Bildgenerierung** (RPC `media.generate_image`) | ja (API, nicht Agent-Tool) | `media_global` / Webhook |
| **Qdrant-Reindex im Runner** | nein (deaktiviert) | Reindex auf Panel oder Cron am Panel |

**Noch nicht über den Kanal** (brauchen lokales `root` auf dem VPS oder gemeinsames Storage):

- Agent-Dateien (`read_file`, `write_file`, Git)
- Playwright (`browser_open`) — Browser läuft dort, wo das Tool ausgeführt wird
- Team-Chat/Tasks-SQLite am Panel-`root`

Für einen „echten“ Satelliten: Agents auf dem VPS, **Wissen (Qdrant) und LLM nur im LAN** — Panel mit `channel: true`, Qdrant und Ollama lokal. Workspace-Dateien für Indexing liegen unter `data/<team>/workspace` **am Panel**.

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
