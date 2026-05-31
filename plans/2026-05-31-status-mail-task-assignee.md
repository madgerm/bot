# Status: E-Mail-Probe + Task-Assignee

**Datum:** 2026-05-31  
**Status:** umgesetzt

## Ziel

Zwei kleine Betriebs-Features mit direktem Nutzen im Alltag — keine weiteren Config-Formulare.

## A — E-Mail-Verbindungstest auf `/admin/settings/status`

### Problem

Mail-Ausfälle (falsches Secret, IMAP/SMTP-Port) merkt man oft erst beim Poll. LLM/Qdrant haben bereits HTMX-Tests.

### Lösung

- Modul `src/bot/config/writers/mail_status.py`
- Pro Team mit `teams/<id>/email.json`:
  - **Config-Check:** enabled, Hosts, `secret_ref` gesetzt (ohne Netz)
  - **Verbindungstest** (`?probe=1`): bestehende `test_imap_connection` / `test_smtp_connection` via `MailService.test_connections()`
- HTMX-Fragment `/admin/settings/status/fragment/mail` + Einbindung in Gesamt-Fragment
- UI: Button „Verbindung testen“ pro Sektion (wie LLM API-Ping)

### Nicht im Scope

- Kein Mailversand, kein Poll
- Teams ohne `email.json` werden nicht gelistet

## B — Task-Board: Assignee aus Agent-Liste

### Problem

Freies Textfeld `assignee_agent` → Tippfehler, keine Übersicht welcher Agent zuständig ist.

### Lösung

- Task-Formular: `<select>` mit allen Agent-IDs (+ leer)
- Anzeige Assignee auf Task-Karten
- Optional `default_task_assignee: bool` in `agent.json` — Checkbox im Agent-Editor; höchstens ein Standard pro Team (beim Speichern andere zurücksetzen)

### Nicht im Scope

- Task-Bearbeitung / Re-Assign per UI
- Automatische Zuweisung durch Pipeline (später)

## Akzeptanz

- [x] Status zeigt Mail-Teams; Probe liefert IMAP/SMTP-Ergebnis
- [x] Task anlegen mit Dropdown; Standard vorausgewählt wenn gesetzt
- [x] `pytest`, `ruff`, `mypy` grün

## Referenz

- Bestehend: `bot.mail.service.MailService.test_connections`
- Status-Muster: `status_settings_routes.py`, LLM-Fragmente
