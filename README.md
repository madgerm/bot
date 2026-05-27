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

Standard: `config/team_hosts.json` verweist auf **lokal** — das Panel liest dieselben Dateien wie der Runner.

### 3. Aufgabe auslösen

```bash
bot msg send --team demo --from orchestrator --to orchestrator \
  --subject "Aufgabe" --content "Feature X umsetzen"

bot run --team demo --once   # oder bot run dauerhaft
```

Pipeline: `orchestrator` → `worker-exec` → `worker-review` → `orchestrator`.

---

## Remote: Web-Panel ↔ Team-Runner auf anderem Rechner

Wenn der **Team-Runner** auf Server B läuft und das **Web-Panel** auf Server A (oder deinem Laptop), brauchst du:

1. HTTP-API auf dem Team-Runner (`bot team serve`)
2. Ein gemeinsames **API-Token** (Geheimnis)
3. Eintrag in `config/team_hosts.json` auf dem Web-Panel-Rechner

### Schritt A — API-Token erzeugen (einmal)

Auf **beliebigem** Rechner (Token sicher weitergeben):

```bash
bot team token --write-config
```

Ausgabe z. B.:

```bash
export BOT_TEAM_API_TOKEN=abc123...sehr_lang...
```

- **Niemals** in Git committen.
- Gleicher Wert muss auf **Team-Runner** und **Web-Panel** (per Env) gesetzt sein.

| Rechner | Umgebungsvariable |
|---------|-------------------|
| Team-Runner (Server B) | `BOT_TEAM_API_TOKEN` |
| Web-Panel (Server A) | dieselbe Variable (für Remote-Hosts) |

Optional auf dem Runner: `config/team_api.json` (nur `token_env`, kein Klartext-Token):

```json
{
  "token_env": "BOT_TEAM_API_TOKEN",
  "teams": ["demo"]
}
```

Vorlage: `config/team_api.json.example`.

### Schritt B — Team-Runner auf Server B

Projekt nach Server B kopieren (oder Git clone), dann:

```bash
export BOT_TEAM_API_TOKEN=<dein-token>

# Agents im Hintergrund
bot run --team demo

# HTTP-API für das Web-Panel (in zweitem Terminal oder systemd)
bot team serve --host 0.0.0.0 --port 8443

# Produktion: TLS
bot team serve --host 0.0.0.0 --port 8443 \
  --ssl-cert /pfad/zertifikat.pem --ssl-key /pfad/schluessel.pem
```

Test von Server A:

```bash
curl -H "Authorization: Bearer $BOT_TEAM_API_TOKEN" \
  http://<server-b-ip>:8443/api/v1/health
```

### Schritt C — Web-Panel auf Server A konfigurieren

`config/team_hosts.json`:

```json
{
  "hosts": [
    {
      "id": "buero-server",
      "label": "Team-Server Büro",
      "mode": "remote",
      "base_url": "https://10.0.0.5:8443",
      "token_env": "BOT_TEAM_API_TOKEN",
      "teams": ["demo"]
    }
  ]
}
```

| Feld | Bedeutung |
|------|-----------|
| `mode` | `"local"` = gleicher Rechner wie Panel; `"remote"` = `base_url` + Token |
| `base_url` | URL des Team-Runners (`bot team serve`), **ohne** trailing slash |
| `token_env` | Name der Env-Variable mit dem API-Token |
| `teams` | Welche Team-IDs dieser Host bedient |

Dann:

```bash
export BOT_TEAM_API_TOKEN=<derselbe-token-wie-auf-server-b>
export BOT_SESSION_SECRET=<panel-session-secret>
bot web --host 0.0.0.0 --port 8080
```

Im **Admin**-Bereich siehst du die konfigurierten Hosts; im Dashboard steht bei jedem Team die Verbindung (`Runner: https://…`).

### Localhost + Remote gemischt

```json
{
  "hosts": [
    {
      "id": "local",
      "label": "Lokal",
      "mode": "local",
      "teams": ["demo"]
    },
    {
      "id": "cloud",
      "label": "Cloud-Runner",
      "mode": "remote",
      "base_url": "https://runner.example.com:8443",
      "token_env": "BOT_CLOUD_RUNNER_TOKEN",
      "teams": ["prod-team"]
    }
  ]
}
```

---

## CLI-Übersicht

| Befehl | Zweck |
|--------|--------|
| `bot config validate` | Konfiguration prüfen |
| `bot run [--team ID] [--once]` | **Team-Runner** — Supervisor + Agent-Loops |
| `bot team serve` | **Team-Runner-API** für Remote-Zugriff |
| `bot team token` | API-Token erzeugen (`export …`) |
| `bot web` | **Web-Panel** |
| `bot msg send …` | Nachricht in Agent-Inbox |
| `bot llm test` | LLM-Verbindung testen |

---

## Konfigurationsdateien

| Datei | Wo | Inhalt |
|-------|-----|--------|
| `config/system.json` | Panel + Runner | System, LLM, Polling, Inbox-Pfade |
| `config/task_models.json` | Panel + Runner | Model-Routing |
| `config/users.json` | **nur Panel** | Web-Login (Benutzer, Rollen, Teams) |
| `config/team_hosts.json` | **nur Panel** | Wo jeder Team-Runner erreichbar ist |
| `config/team_api.json` | **nur Runner** | `token_env` für `bot team serve` |
| `teams/<id>/team.json` | Runner | Team-Metadaten |
| `teams/<id>/agents/<agent>/agent.json` | Runner | Agent-Rolle, Intervall |

---

## LLM (LiteLLM)

In `config/system.json`: `"llm": { "enabled": true, … }`.

```bash
export LITELLM_API_KEY=sk-...   # Name aus secret_ref
bot llm test --task-category coding --prompt "Kurz antworten"
```

Mit `"enabled": false` nutzen die Handler den **Stub** (ohne echtes Modell).

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
