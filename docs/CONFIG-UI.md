# Web-Panel: Konfiguration (CONFIG-UI)

Übersicht der **Einstellungs-Routen** im Panel. Operative Seiten (Chat, Tasks, Mail senden) bleiben unter `/teams/<id>/…` getrennt.

## Roadmap

Vollständiger Plan: [`plans/2026-05-30-web-panel-config-ui.md`](../plans/2026-05-30-web-panel-config-ui.md)

| Phase | Inhalt | Status |
|-------|--------|--------|
| 0 | Writer-Schicht, `/admin/settings` Gerüst | **fertig** |
| 1 | Nutzer CRUD | **fertig** |
| 2 | LLM, Qdrant, Playwright, task_models | **fertig** |
| 3 | Team, Agents, Pipeline | **fertig** |
| 4 | Crawl, E-Mail, Hours, Integrationen, Git | **fertig** |
| 5 | Hosts-Wizard, team_api, Status | **fertig** |
| 6 | Installer-Profile (Relay, …) | geplant |

## Routen (Admin)

| URL | Beschreibung | Schreibt JSON |
|-----|--------------|---------------|
| `/admin/settings` | Übersicht aller Konfigurationsbereiche | — |
| `/admin/settings/users` | Nutzerliste | — |
| `/admin/settings/users/new` | Nutzer anlegen | `config/users.json` |
| `/admin/settings/users/{name}` | Nutzer bearbeiten | `config/users.json` |
| `/admin/settings/system` | LLM, Qdrant, Playwright, Polling, Webhooks | `config/system.json` |
| `/admin/settings/models` | Task-Modell-Routing | `config/task_models.json` |
| `/admin/media` | Medien global + Team-Overrides | `system.json` (`media_global`), `teams/<id>/media.json` |
| `/admin/settings/hosts` | Team-Runner (lokal/remote, Kanal, Relay) | `config/team_hosts.json` |
| `/admin/settings/hosts/wizard` | Setup-Assistent + Token-Generator | `team_hosts.json`, ggf. `team_api.json` |
| `/admin/settings/hosts/new` | Host anlegen | `team_hosts.json` |
| `/admin/settings/hosts/{id}` | Host bearbeiten | `team_hosts.json` |
| `/admin/settings/status` | Verbindungstests (Hosts, LLM, Qdrant) | — |

| `/teams/<id>/settings` | Team-Übersicht | — |
| `/teams/<id>/settings/general` | Name, Preset, Orchestrator | `teams/<id>/team.json` |
| `/teams/<id>/settings/pipeline` | Pipeline-Agents | `teams/<id>/team.json` |
| `/teams/<id>/settings/agents` | Agent-Liste, CRUD | `teams/<id>/agents/<id>/agent.json` |

| `/teams/<id>/settings/crawl` | Crawl-Domains | `teams/<id>/crawl.json` |
| `/teams/<id>/settings/email` | IMAP/SMTP | `teams/<id>/email.json` |
| `/teams/<id>/settings/hours` | Quellen, Checker | `teams/<id>/hours.json` |
| `/teams/<id>/settings/hours/master` | Wochenzeiten | `hours.master.json` |
| `/teams/<id>/settings/integrations` | Telegram/Matrix | `integrations.json` |
| `/teams/<id>/settings/git` | Repo/Branch | `git.json` |
| `/teams/<id>/settings/playwright` | Team-Override | `playwright.json` |

## Technik

- **Lesen/Schreiben:** `src/bot/config/writers/base.py` — atomisches `atomic_write_json`, Pydantic-Validierung via `load_json_model`
- **Audit:** Kategorie `config` in `data/audit.sqlite` (POST-Aktionen)
- **Rechte:** nur `role: admin` (`require_admin`)

## Manuell (vorerst)

- **Panel ↔ Team-Runner:** Tokens in `.env` (Wizard unter `/admin/settings/hosts/wizard` erzeugt Vorschlag)
- **Secrets:** Umgebungsvariablen (`LITELLM_API_KEY`, …), nicht Klartext im Panel speichern
