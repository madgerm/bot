# Web-Panel: Vollständige Konfiguration ohne JSON-Edit

**Status:** Entwurf (Umsetzungs-Roadmap)  
**Datum:** 2026-05-30  
**Verknüpfungen:** Nutzerwunsch „alles im Panel einstellen“; bisher nur `/admin/media` + Agent-Anlegen/Löschen

## Ziel

Betreiber sollen **fast alle** Einstellungen über das Web-Panel pflegen können — ohne `config/*.json` oder `teams/<id>/*.json` von Hand zu bearbeiten:

- **LLM**, STT/TTS/Vision/Bild, **Qdrant**, Playwright/Browser
- **Crawl-Domains** (welche Webseiten indexiert werden)
- **Agents**: Rolle, Intervall, Pipeline-Zuordnung, später Wissen/Tools/Aufgaben
- **Nutzer**: anlegen, Rollen, Team-Zugriff, Passwort setzen
- **Team-Integrations**: E-Mail, Öffnungszeiten, Telegram/Matrix, Git

**Bewusst außerhalb des Panels (oder nur als geführter Wizard):**

- **Verbindung Panel ↔ Team-Runner** (Remote-URL, API-Token, Kanal/Relay): technisch Env + Netzwerk — Panel kann einen **Setup-Assistenten** anbieten (URLs/Tokens generieren, Copy-Paste, Verbindungstest), aber kein magisches „ohne einmalige Kopplung“.
- **Secrets in Produktion**: Passwörter/API-Keys weiter über **Env** oder Panel-gestütztes „Secret-Env-Name“ (Feld `secret_ref`), nicht Klartext in Git.

Am Ende: Panel = **Betrieb + Konfiguration**; JSON-Dateien bleiben Speicherformat (versionierbar, backup-fähig), werden aber primär vom Panel geschrieben.

---

## Ist-Zustand (Kurz)

| Bereich | Panel heute |
|---------|-------------|
| Medien global/team | `/admin/media` — schreibt `media_global` / `media.json` |
| Agents | `/teams/<id>/agents` — nur create/delete (id + role) |
| Admin | `/admin` — Nutzer/Hosts **nur lesen** |
| Qdrant/Crawl | Suchen/Reindex/Run — **Config nur per Datei** |
| LLM, task_models, users, team.json, email, hours, integrations, git, playwright | **nur Datei/CLI** |

Pläne (`plans/2026-05-26-*.md`) nennen „Config UI“ — **noch nicht implementiert**.

---

## Architektur-Entscheidungen

### 1. Config-Writer-Schicht (`src/bot/config/writers/`)

Einheitliches Muster (analog `src/bot/config/media_admin.py`):

```text
load_*()  →  Pydantic validieren  →  Form/API  →  model_dump  →  atomisch schreiben
```

- **Atomisches Schreiben**: temp-Datei + `rename`, UTF-8, `indent=2`
- **Validierung**: bestehende Pydantic-Modelle — keine zweite Wahrheit
- **Audit**: jede Änderung → `data/audit.sqlite` (Kategorie `config`, Aktion `update`, Pfad, Actor)
- **Hot-Reload**: bestehender `config/`-Watcher im Runner bleibt; Panel schreibt dieselben Pfade
- **RBAC**: `operator`/`admin` schreibt; `reader` nur lesen (bestehend `team_access.py`)

Pro Datei ein Modul, z. B.:

| Modul | Datei |
|-------|--------|
| `system_admin.py` | `config/system.json` (partielle Blöcke) |
| `users_admin.py` | `config/users.json` |
| `hosts_admin.py` | `config/team_hosts.json` |
| `task_models_admin.py` | `config/task_models.json` |
| `team_admin.py` | `teams/<id>/team.json` |
| `agent_admin.py` | `teams/<id>/agents/<id>/agent.json` |
| `crawl_admin.py` | `teams/<id>/crawl.json` |
| … | email, hours, integrations, git, playwright |

### 2. Web-Routen-Struktur

Neue Bereiche unter **`/admin/settings/...`** (global) und **`/teams/<id>/settings/...`** (team):

```text
/admin                          → Übersicht + Links (bestehend erweitern)
/admin/settings                 → Kacheln: System, Nutzer, Hosts, Modelle
/admin/settings/system          → LLM, Qdrant, Playwright, Polling, Webhooks
/admin/settings/users           → CRUD + Passwort
/admin/settings/hosts           → team_hosts + Verbindungs-Assistent
/admin/settings/models          → task_models.json
/admin/media                    → (bestehend)

/teams/<id>/settings            → Team-Übersicht
/teams/<id>/settings/agents     → Agent-Liste + Detail-Editor
/teams/<id>/settings/agents/<agent_id>
/teams/<id>/settings/crawl
/teams/<id>/settings/email
/teams/<id>/settings/hours
/teams/<id>/settings/integrations
/teams/<id>/settings/git
/teams/<id>/settings/playwright
/teams/<id>/settings/pipeline    → team.json pipeline / preset

Betriebs-UI (unverändert getrennt):
/teams/<id>/chat, /tasks, /mail, /hours (Workflow), /knowledge, /crawl (Run), …
```

Navigation: Tab **„Einstellungen“** neben Chat/Tasks in Team-Layout; Admin-Menüpunkt **„Einstellungen“**.

### 3. Schema-Erweiterungen (für Agent-Wissen & Aufgaben)

Heute stecken **Tools und Qdrant-Collections fest im Code** (`handlers.py`, `tools.py`). Für „Agent A hat dieses Wissen, Agent B jene Aufgabe“ brauchen wir optionale Felder in `agent.json`:

```json
{
  "agent": {
    "id": "worker-exec",
    "role": "worker",
    "enabled": true,
    "interval_seconds": 5,
    "display_name": "Ausführer",
    "task_categories": ["coding"],
    "tools_allow": ["read_file", "write_file", "qdrant_search"],
    "qdrant_collections": ["project", "background"],
    "system_prompt_extra": "Du bist für Backend-Code zuständig."
  }
}
```

| Feld | Zweck | Phase |
|------|--------|-------|
| `task_categories` | Override für `task_models.json`-Routing | 3b |
| `tools_allow` / `tools_deny` | Feingranulare Tools | 4 |
| `qdrant_collections` | Welche Collections `qdrant_search` nutzt | 4 |
| `system_prompt_extra` | Zusatz-Prompt pro Agent | 3b |

**Pipeline** bleibt in `team.json` → `pipeline.execute/review/document`; UI: Dropdown der Agent-IDs.

**Aufgaben im operativen Sinn** = Task-Board (`tasks.sqlite`, assignee) + Pipeline-Nachrichten — Panel verknüpft in Agent-Detail „Standard-Assignee für Tasks“ (optional später).

### 4. Secrets-UX

- Formularfelder: **„Umgebungsvariable“** (`LITELLM_API_KEY`, `BOT_TEAM_API_TOKEN`, …), nicht Klartext speichern
- Panel zeigt: gesetzt ja/nein (z. B. `os.environ.get` ohne Wert anzeigen)
- Optional Phase 5: `.env`-Snippet zum Download nach Speichern der `secret_ref`-Namen

### 5. Verbindungs-Assistent (Panel ↔ Runner)

Seite `/admin/settings/hosts/wizard`:

1. Modus wählen: lokal | remote HTTP | Kanal | Relay  
2. Panel generiert Token (`secrets.token_urlsafe`) → Anzeige + „in .env auf Runner kopieren“  
3. Vorschau der zu schreibenden JSON-Fragmente (Panel schreibt `team_hosts.json`; Runner-Hinweis für `system.json` / `team_api.json`)  
4. **Test**: `GET /health` (remote) oder Kanal-Ping / Relay-Raum-Status  

Kein Ersatz für einmalige Netzwerk-Einrichtung — aber **kein manuelles JSON-Edit** nötig, wenn Wizard durchlaufen wird.

---

## Umsetzungsphasen

Reihenfolge: Infrastruktur zuerst, dann global, dann Team, dann Agent-Tiefe, dann Installer.

### Phase 0 — Fundament (ca. 1 PR) ✅

**Ziel:** Alle folgenden Phasen nutzen dieselbe Basis.

- [x] `src/bot/config/writers/base.py` — `atomic_write_json(path, data)`, `load_json_model(path, Model)`
- [x] `src/bot/web/settings_routes.py` — Router registrieren; Layout `settings_base.html`
- [x] Audit-Kategorie `config` in Middleware (Medien-Speichern + künftige `/admin/settings/*` POST)
- [x] Tests: roundtrip load → mutate → save → validate; RBAC 403 für reader
- [x] Docs: `docs/CONFIG-UI.md` — Übersicht Routen

**Akzeptanz:** Settings-Übersicht unter `/admin/settings` erreichbar (admin only).

---

### Phase 1 — Nutzer & Navigation (ca. 1 PR) ✅

**Ziel:** Nutzer vollständig im Panel.

- [x] `/admin/settings/users` — Liste, anlegen, Rolle, Teams, aktiv/deaktiviert
- [x] Passwort setzen: bcrypt via `hash_password` in `users_admin.py`
- [x] Nutzer löschen / Team-Zugriff (`team_access`) editieren
- [x] Settings-Übersicht verlinkt Nutzer

**Akzeptanz:** Neuer User nur über Panel; Login funktioniert; Audit-Eintrag (`config` / `user_*`).

---

### Phase 2 — Globales System (ca. 1–2 PRs) ✅

**Ziel:** LLM, Qdrant, Playwright, Polling ohne Datei-Edit.

**2a — LLM & Modelle**

- [x] `/admin/settings/system` — Sektionen: LLM | Qdrant | Playwright | Polling | Webhooks
- [x] LLM: `enabled`, `mode` (direct/proxy/channel), `api_base`, `proxy.*`, `hub` (Relay)
- [x] Env-Status für `secret_ref` / Token-Env-Namen
- [x] `/admin/settings/models` — `task_models.json` Tabelle + neue Kategorie

**2b — Qdrant & Playwright**

- [x] Qdrant: `enabled`, `url`, `embedding.*`, `reindex.*`
- [x] Playwright: `mode`, `headless`, `ws_endpoints`
- [x] Settings-Nav: System | Modelle

**Akzeptanz:** `config/system.json` + `task_models.json` via Panel; pytest grün.

---

### Phase 3 — Team & Agents (Kern deines Wunsches) (ca. 2 PRs) ✅

**Ziel:** Teams und Agents im Panel konfigurieren.

**3a — Team & Pipeline**

- [x] `/teams/<id>/settings` — Übersicht + Links
- [x] `/teams/<id>/settings/general` — `name`, `enabled`, `preset`, `orchestrator_id`
- [x] `/teams/<id>/settings/pipeline` — execute/review/document Agent-Dropdowns
- [x] Validierung: referenzierte Agent-IDs existieren

**3b — Agent-Editor**

- [x] `/teams/<id>/settings/agents` — Liste mit Status
- [x] `/teams/<id>/settings/agents/<agent_id>` — role, display_name, interval, enabled
- [x] `AgentBlock`: `task_categories`, `system_prompt_extra`
- [x] Create/Delete; `/teams/<id>/agents` → Redirect auf Settings

**Akzeptanz:** Team/Agents über Panel; pytest grün.

---

### Phase 4 — Team-Dienste (ca. 2 PRs) ✅

**Ziel:** Crawl, E-Mail, Hours, Integrationen, Git, Playwright-Override.

| Seite | Config | Status |
|-------|--------|--------|
| `/teams/<id>/settings/crawl` | `crawl.json` | ✅ |
| `/teams/<id>/settings/email` | `email.json` | ✅ |
| `/teams/<id>/settings/hours` + `/hours/master` | `hours.json`, Master | ✅ |
| `/teams/<id>/settings/integrations` | `integrations.json` | ✅ |
| `/teams/<id>/settings/git` | `git.json` | ✅ |
| `/teams/<id>/settings/playwright` | `playwright.json` | ✅ |

**Akzeptanz:** Team-Dienste im Panel; Crawl-Run weiter unter `/teams/<id>/crawl`.

---

### Phase 5 — Hosts, Verbindung, Feinschliff Agent (ca. 1–2 PRs) ✅

- [x] `/admin/settings/hosts` — CRUD `TeamHostEntry` (mode, base_url, teams[], channel, relay_*)
- [x] Wizard (siehe oben) + Token-Generator
- [x] `team_api.json` — token_env + teams (admin only, Warnung)
- [x] Agent: `tools_allow` / `qdrant_collections` in Schema + Runtime (`tools.py` filtert)
- [x] Agent-Detail: „Wissen“ — Checkboxen project/background/web
- [x] Statusseite `/admin/settings/status` — LLM-Test, Qdrant, Host-Verbindung

**Akzeptanz:** Satellit-Setup über Wizard ohne JSON-Datei öffnen.

---

### Phase 6 — Installer (parallel oder nach Phase 2) (ca. 1 PR) ✅

**Ziel:** Debian-Skript ergänzen — optional, nicht Blocker für Panel-UI.

- [x] `BOT_INSTALL_RELAY=1` → `bot-relay.service` + Token in `.env`
- [x] `BOT_INSTALL_PROFILE=panel|runner|satellite|relay` → Example-Configs (`scripts/apply-install-profile.py`) + Tokens
- [x] `bot team serve` → `bot-team-api.service` (Runner/Satellit-Profil)
- [x] README One-Liner + Variablen-Tabelle

**Akzeptanz:** Non-interactive One-Liner für „Panel+Relay“ oder „Satellit+Runner“ dokumentiert.

---

## UI/UX-Richtlinien

- **Formulare** mit klaren deutschen Labels; technische Keys (`api_base`) als Hilfstext
- **Speichern** pro Sektion (nicht eine 200-Felder-Seite)
- **Validierungsfehler** inline (Pydantic `ValidationError` → lesbare Meldungen)
- **Gefährliche Aktionen** (User löschen, Agent löschen, mode=channel) mit Bestätigung
- **Dark/Light** — bestehende CSS-Variablen (`p-card`, `p-link`)
- Kein JavaScript-Framework nötig — HTMX optional später für Live-Tests

---

## Tests pro Phase

| Typ | Inhalt |
|-----|--------|
| Unit | `*_admin.py` load/save, invalid data rejected |
| Web | `TestClient` POST settings → Datei auf Disk → GET zeigt Wert |
| RBAC | reader → 403 auf POST |
| Integration | Agent-Änderung → `RuntimeConfig` reload sieht neuen `interval_seconds` |

---

## Abhängigkeiten & Risiken

| Risiko | Mitigation |
|--------|------------|
| Panel und Runner unterschiedliches `root` | Hosts-Wizard erklärt; Satellit: schwere Config nur Panel-`root` |
| Große `system.json`-Forms | Tabs + partielle Updates (nur geänderte Top-Level-Keys mergen) |
| Secrets in Git | Nur `secret_ref`; Panel speichert nie Klartext-Passwörter |
| Agent-Tools im Code | Phase 4 Schema + Filter; Default = bisheriges Verhalten |
| Kanal/Relay falsch konfiguriert | Statusseite + Verbindungstest |

---

## Was du manuell lassen musst (realistisch)

1. **Einmalig:** Runner erreichbar machen (`bot team serve`, Firewall, TLS)  
2. **Einmalig:** Gleiche Tokens in Panel- und Runner-`.env` (Wizard hilft)  
3. **Ollama/Qdrant/Relay** als Prozesse starten (Installer/systemd optional)  
4. **Git-Remote-Credentials** ggf. SSH auf dem Host — Panel nur URL/Branch

Alles andere (Welches LLM, welche Crawl-URL, welcher Agent welche Rolle, welcher User welches Team) → **Panel**.

---

## Nächste Schritte (sofort)

1. [x] Phase 0 PR: `config/writers` + `/admin/settings` Gerüst  
2. [x] Phase 1 PR: Nutzer-UI  
3. [x] Phase 2 PR: LLM + task_models + System  
4. [x] Phase 3 PR: Team/Agents/Pipeline  

Branch-Vorschlag pro Phase: `cursor/web-config-phase-N-f179`  
Review nach jeder Phase: du testest im Panel, dann nächste Phase.

---

## Referenz: Config-Dateien → Panel-Seite (Zielbild)

| Datei | Panel-Route (Ziel) |
|-------|-------------------|
| `config/users.json` | `/admin/settings/users` |
| `config/system.json` | `/admin/settings/system` |
| `config/task_models.json` | `/admin/settings/models` |
| `config/team_hosts.json` | `/admin/settings/hosts` |
| `config/team_api.json` | `/admin/settings/hosts` (API-Token) |
| `teams/<id>/team.json` | `/teams/<id>/settings/general`, `.../pipeline` |
| `teams/<id>/agents/<aid>/agent.json` | `/teams/<id>/settings/agents/<aid>` |
| `teams/<id>/crawl.json` | `/teams/<id>/settings/crawl` |
| `teams/<id>/email.json` | `/teams/<id>/settings/email` |
| `teams/<id>/hours.json` | `/teams/<id>/settings/hours` |
| `teams/<id>/integrations.json` | `/teams/<id>/settings/integrations` |
| `teams/<id>/git.json` | `/teams/<id>/settings/git` |
| `teams/<id>/playwright.json` | `/teams/<id>/settings/playwright` |
| `teams/<id>/media.json` | `/admin/media` (bestehend) |
