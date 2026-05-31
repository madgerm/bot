# Web-Panel: Konfiguration (CONFIG-UI)

Übersicht der **Einstellungs-Routen** im Panel. Operative Seiten (Chat, Tasks, Mail senden) bleiben unter `/teams/<id>/…` getrennt.

## Roadmap

Vollständiger Plan: [`plans/2026-05-30-web-panel-config-ui.md`](../plans/2026-05-30-web-panel-config-ui.md)

| Phase | Inhalt | Status |
|-------|--------|--------|
| 0 | Writer-Schicht, `/admin/settings` Gerüst | **aktiv** |
| 1 | Nutzer CRUD | geplant |
| 2 | LLM, Qdrant, Playwright, task_models | geplant |
| 3 | Team, Agents, Pipeline | geplant |
| 4 | Crawl, E-Mail, Hours, Integrationen, Git | geplant |
| 5 | Hosts-Wizard, Agent-Tools/Wissen, Status | geplant |
| 6 | Installer-Profile (Relay, …) | geplant |

## Routen (Admin)

| URL | Beschreibung | Schreibt JSON |
|-----|--------------|---------------|
| `/admin/settings` | Übersicht aller Konfigurationsbereiche | — |
| `/admin/media` | Medien global + Team-Overrides | `system.json` (`media_global`), `teams/<id>/media.json` |

Weitere Routen folgen unter `/admin/settings/…` (Phase 1+).

## Technik

- **Lesen/Schreiben:** `src/bot/config/writers/base.py` — atomisches `atomic_write_json`, Pydantic-Validierung via `load_json_model`
- **Audit:** Kategorie `config` in `data/audit.sqlite` (POST-Aktionen)
- **Rechte:** nur `role: admin` (`require_admin`)

## Manuell (vorerst)

- **Panel ↔ Team-Runner:** `config/team_hosts.json`, Tokens in `.env` — später Setup-Assistent (Phase 5)
- **Secrets:** Umgebungsvariablen (`LITELLM_API_KEY`, …), nicht Klartext im Panel speichern
