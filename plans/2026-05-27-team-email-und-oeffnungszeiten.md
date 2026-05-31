# Team-E-Mail (IMAP/SMTP) und Öffnungszeiten-Sync (Web + Google)

**Status:** MVP umgesetzt (2026-05-31) — E4/H4 optional offen  
**Datum:** 2026-05-27  
**Verknüpfungen:** Nutzeranfrage (Firmenpostfach mit Freigabe; Webseite ↔ Google Business)  
**Baut auf:** [`mvp-und-entscheidungen.md`](mvp-und-entscheidungen.md), [`runtime-teams.md`](runtime-teams.md), Phase-2 (Chat, Qdrant, Playwright)

---

## Ziel

Zwei **optionale Team-Typen** (Presets + Module), die auf der bestehenden Runtime aufsetzen:

1. **E-Mail-Team** — Firmenpostfach per **IMAP** lesen, Agents recherchieren und formulieren, Dialog mit dem Nutzer im **Team-Chat**, Versand per **SMTP** erst nach **expliziter Freigabe** (kein Auto-Send).
2. **Öffnungszeiten-Team** — **Single Source of Truth** für Öffnungszeiten; Abgleich **Website ↔ Google Business Profile**; Änderungen nur als **Vorschlag + Freigabe**, dann API-gestütztes Update (Playwright nur als Fallback).

Am Ende soll ein Betreiber ein Team anlegen, Secrets setzen, Agents starten (`bot run`) und im Web-Panel Entwürfe prüfen und freigeben können.

---

## Festgelegte Entscheidungen (Rollen)

| Rolle | Aufgabe |
|-------|---------|
| **Admin** | System- und Team-**Aufbau**: Nutzer anlegen, Teams zuweisen, `email.json` / Secrets / Runner — **kein** täglicher Mail-Betrieb |
| **Team-Nutzer** (alle mit Zugriff auf das Team in `users.json`) | **Betrieb**: Postfach bearbeiten, mit Agents diskutieren, Entwürfe **freigeben** und **abschicken** |

**Freigabe & Versand:** Jeder Team-Nutzer mit `require_team_access(team_id)` darf freigeben und senden — **nicht** auf Admin beschränkt. Die Hürde ist **bewusste Freigabe pro Entwurf** (Human-in-the-loop), nicht eine Admin-Rolle.

**Öffnungszeiten:** gleiches Modell — Team-Nutzer pflegen Master (falls berechtigt), prüfen Diffs, geben Publish frei; Admin richtet nur Team und API-Zugänge ein.

---

## Ausgangslage (Ist)

| Baustein | Vorhanden | Fehlt für die Use Cases |
|----------|-----------|-------------------------|
| Teams / Agents / Supervisor | ja | domänenspezifische Rollen & Handler |
| Interne Messages (`inbox/`/`outbox/`) | ja | ≠ E-Mail |
| Team-Chat (SQLite) | ja | Thread pro Mail-Entwurf |
| Qdrant | ja | Indexierung Mail-Kontext / Firmen-FAQ |
| Playwright | ja (basic) | nicht für Google-Login-Produktion |
| Web-Panel + RBAC | ja | Routen Entwürfe / Freigabe |
| Remote Team-Runner API | ja | Endpoints für Mail/Sync (später) |

**Wichtig:** Die bestehende `Mailbox`-Klasse bleibt **intern**; das neue Modul heißt z. B. `bot.mail` / `EmailStore`, um Verwechslung zu vermeiden.

---

## Gemeinsame Prinzipien (beide Features)

### Human-in-the-loop (Pflicht)

```
Eingang → Verarbeitung (Agents) → draft / awaiting_approval
                                        │
                    Nutzer im Panel/Chat ◄┘ (Diskussion, Revision)
                                        │
                              approved (explizit)
                                        │
                              Ausführung (SMTP / API-Write)
```

- **Kein** LLM-Tool „send_mail“ ohne vorherigen Status `approved`.
- Versand-Code prüft **serverseitig** `status == approved` und `approved_by` + `approved_at` (jeder berechtigte Team-Nutzer).
- Optional pro Team: UI-Bestätigung (`CONFIRM_SEND`) vor dem ersten Versand — **ohne** Admin-Pflicht.

### Secrets & Compliance

- Credentials nur via **Umgebungsvariablen** / `secret_ref` (siehe `mvp-und-entscheidungen.md`); Konfiguration durch **Admin**, Laufzeit-Nutzung durch Team-Nutzer im Panel.
- Team-Scope: Nutzer sieht und bedient nur Teams aus `users.json` (bestehendes RBAC).
- Logging: **keine** Mail-Bodies / Passwörter; nur `message_id`, Betreff-Länge, Status.
- Betreiber verantwortet **DSGVO**, Auftragsverarbeitung, Zugriff auf Firmenpostfächer.

### Anbindung an bestehende Runtime

| Trigger | Nutzung |
|---------|---------|
| **Polling** (IMAP IDLE optional später) | neuer Mail-Poll-Job im Supervisor oder dedizierter `email-poller`-Agent |
| **Interne Message** | IMAP → normalisierte Aufgabe → `bot msg` an `researcher` / `composer` |
| **Chat** | Nutzer-Feedback → Orchestrator-Message |
| **Webhook** (Phase 2) | externes Ticketing |

---

# Teil A: E-Mail-Team

## A.1 Nutzer-Workflow (Soll)

1. Neue Mail im Postfach (IMAP) → System legt **EmailThread** + Aufgabe „bearbeiten“ an.
2. Agent **researcher** sammelt Kontext (Qdrant, Anhänge-Metadaten, optional Web).
3. Agent **composer** erstellt **Antwortentwurf** → Status `awaiting_approval`.
4. Nutzer bespricht im **Team-Chat** oder Entwurfs-UI Änderungen → Revisionen (`draft_v2`, …).
5. Nutzer klickt **Freigeben** → Status `approved`.
6. **Nur dann:** `mail send` → SMTP; Status `sent`; IMAP-Flag „beantwortet“ optional.

**Antwort-Mail, keine Eingangsmail:** Nutzer startet im Panel „Neue Mail“ → gleicher Pfad ab Schritt 3.

## A.2 Team-Preset `teams/<id>/`

Empfohlene Agent-Rollen (analog Demo-Pipeline):

| Agent | Rolle |
|-------|--------|
| `orchestrator` | Verteilt Aufgaben, wartet auf Freigabe-Signal |
| `mail-researcher` | Kontext, Fakten, keine Formulierung |
| `mail-composer` | Entwurf, Ton, Betreff |
| `mail-reviewer` | Optional: Konsistenz, keine Halluzinationen |

Dateien:

- `team.json` — `team_type: "email"` (optional, für UI-Preset)
- `email.json` — IMAP/SMTP, Ordner, Signature, erlaubte Domains
- bestehende `agents/*/agent.json`

## A.3 Konfiguration (Schema-Entwurf)

`teams/<team_id>/email.json`:

```json
{
  "email": {
    "enabled": true,
    "imap": {
      "host": "imap.firma.de",
      "port": 993,
      "use_ssl": true,
      "username": "buero@firma.de",
      "secret_ref": "FIRMA_IMAP_PASSWORD",
      "mailbox": "INBOX",
      "poll_interval_seconds": 120
    },
    "smtp": {
      "host": "smtp.firma.de",
      "port": 587,
      "starttls": true,
      "username": "buero@firma.de",
      "secret_ref": "FIRMA_SMTP_PASSWORD",
      "from_display_name": "Firma GmbH"
    },
    "rules": {
      "allowed_recipient_domains": ["firma.de", "kunde.de"],
      "max_attachment_mb": 10,
      "require_approval": true
    }
  }
}
```

Global optional: `config/system.json` → `email_global` (Default-Server, falls Team `source: global`).

**POP3:** nur falls nötig (Phase B); **IMAP** ist Default (Ordner, Flags, IDLE später).

**OAuth2 (Google/Microsoft):** Phase B — `auth_type: "oauth2"` + Token-Refresh; MVP startet mit **App-Passwort** / klassischen Credentials.

## A.4 Datenmodell

SQLite pro Team: `data/<team_id>/email.sqlite` (neben `chat.sqlite`)

| Tabelle | Zweck |
|---------|--------|
| `threads` | `id`, `imap_uid`, `subject`, `from`, `received_at`, `status` |
| `messages` | einzelne Mail-Teile (incoming/outgoing), `body_text`, `body_html` (optional redacted in logs) |
| `drafts` | `version`, `content`, `created_by_agent`, `status` |
| `approvals` | `draft_id`, `approved_by`, `approved_at`, `ip` optional |

Statusmaschine **Draft:**

`draft` → `awaiting_approval` → `approved` → `sending` → `sent` | `failed`  
Zweig: `rejected` (Nutzer verwirft)

Verknüpfung: `draft_id` ↔ Chat-Systemnachrichten („Entwurf v3 bereit“).

## A.5 Module & CLI (Implementierung)

| Pfad | Inhalt |
|------|--------|
| `src/bot/mail/` | `imap_client`, `smtp_client`, `store`, `normalize`, `approval` |
| `src/bot/cli_mail.py` | CLI-Registrierung |

**CLI (Vorschlag):**

| Befehl | Zweck |
|--------|--------|
| `bot mail poll --team ID` | einmal IMAP abholen |
| `bot mail list --team ID` | Threads/Entwürfe |
| `bot mail show --team ID --thread UUID` | Inhalt anzeigen |
| `bot mail approve --team ID --draft UUID` | Freigabe (CLI-Alternative zum UI) |
| `bot mail send --team ID --draft UUID` | nur wenn `approved` |
| `bot mail test --team ID` | IMAP+SMTP-Verbindung testen |

**Supervisor:** optional integrierter Poll alle `poll_interval_seconds` pro aktivem E-Mail-Team.

## A.6 Web-Panel

Neue Routen (Team-Scope wie Chat):

- `GET /teams/<id>/mail` — Thread-Liste, Filter `awaiting_approval`
- `GET /teams/<id>/mail/<thread_id>` — Verlauf + aktueller Entwurf
- `POST .../mail/approve` — Freigabe (jeder Team-Nutzer mit Team-Zugriff)
- `POST .../mail/reject` — verwerfen + optional Rückmeldung an Orchestrator
- `POST .../mail/revise` — Nutzer-Kommentar → neue Agent-Aufgabe

Templates: `team_mail.html`, `team_mail_thread.html`.

## A.7 Agent-Handler (logisch)

Neue Message-Typen oder `task_category`:

- `email.incoming` → researcher
- `email.research_done` → composer
- `email.draft_ready` → Orchestrator + UI-Benachrichtigung
- `email.user_feedback` → composer (Revision)
- `email.approved` → **kein LLM** — reiner SMTP-Service-Call

Handler in `src/bot/runtime/handlers/` (oder Erweiterung bestehender Stub/LLM-Handler).

## A.8 Phasen E-Mail

| Phase | Umfang | Abhängigkeiten |
|-------|--------|----------------|
| **E0** | Schema + `email.json` validieren, `bot mail test` | — |
| **E1** | IMAP poll, Thread in SQLite, Anzeige Web read-only | E0 |
| **E2** | Agent-Pipeline → Entwurf, Chat-Verknüpfung | E1, LLM |
| **E3** | Freigabe UI + `approve` + SMTP send (hard gate) | E2 |
| **E4** | Anhänge, OAuth2, IMAP IDLE, Remote-API | E3 |

**MVP zum ersten Nutzen:** E0 + E1 + E3 (manueller Entwurf im UI optional) **oder** E0–E3 komplett.

---

# Teil B: Öffnungszeiten-Team (Web + Google)

## B.1 Nutzer-Workflow (Soll)

1. **Master-Daten** pflegen (eine Wahrheit): z. B. `teams/<id>/hours.json` oder Admin-UI.
2. Scheduler/Agent **checker** liest:
   - Master (`hours.json`)
   - Website (HTTP/API oder CMS)
   - Google Business Profile (**API**, nicht Scraping)
3. Bei Abweichung → **Diff-Report** im Chat/Panel, Status `awaiting_approval`.
4. Nutzer passt Master an oder bestätigt Vorschlag → **Freigabe**.
5. Agent **publisher** schreibt nur freigegebene Änderungen in Website-API und Google-API.

## B.2 Team-Preset

| Agent | Rolle |
|-------|--------|
| `orchestrator` | koordiniert Checks und Freigaben |
| `hours-checker` | liest Quellen, erzeugt Diff (kein Write) |
| `hours-publisher` | Write nur bei `approved` |

`team_type: "hours_sync"` in `team.json`.

## B.3 Konfiguration (Schema-Entwurf)

`teams/<id>/hours.json`:

```json
{
  "hours": {
    "enabled": true,
    "master_source": "file",
    "master_file": "teams/firma/hours.master.json",
    "website": {
      "type": "rest",
      "base_url": "https://cms.firma.de/api",
      "hours_endpoint": "/v1/opening-hours",
      "secret_ref": "CMS_API_TOKEN"
    },
    "google_business": {
      "enabled": true,
      "account_id": "...",
      "location_id": "...",
      "secret_ref": "GOOGLE_SERVICE_ACCOUNT_JSON",
      "use_official_api": true
    },
    "schedule": {
      "check_cron": "0 6 * * *",
      "timezone": "Europe/Berlin"
    },
    "require_approval": true
  }
}
```

**Playwright-Fallback** (`website.type: "playwright"`): nur wenn keine API — dokumentiert als **brittle**, nicht für Google Business (ToS-Risiko).

## B.4 Datenmodell

`data/<team_id>/hours.sqlite` oder JSON-Audit-Log:

| Entität | Inhalt |
|---------|--------|
| `master` | kanonische Öffnungszeiten (pro Wochentag/Feiertag) |
| `snapshots` | letzter Stand Website / Google (JSON) |
| `diffs` | Vorschlag, `status`, `approved_by` |
| `publish_log` | was wann geschrieben wurde |

Format Öffnungszeiten (intern): strukturiertes JSON (Mo–So, intervals, exceptions, locale).

## B.5 Externe Integrationen

| Ziel | Empfohlen | Vermeiden |
|------|-----------|-----------|
| Eigene Website | CMS-REST, statisches JSON im Repo, Headless-API | reines DOM-Scraping |
| Google | [Business Profile API](https://developers.google.com/my-business) mit Service Account / OAuth | Playwright-Login im Google-Admin |

**Crawl4AI** (laut MVP-Plan): optional nur zum **Lesen** der öffentlichen Website-HTML, nicht zum Schreiben.

## B.6 Module & CLI

| Pfad | Inhalt |
|------|--------|
| `src/bot/hours/` | `master`, `diff`, `adapters/website`, `adapters/google` |
| `src/bot/cli_hours.py` | CLI |

| Befehl | Zweck |
|--------|--------|
| `bot hours show --team ID` | Master anzeigen |
| `bot hours check --team ID` | Diff erzeugen |
| `bot hours approve --team ID --diff UUID` | Freigabe |
| `bot hours publish --team ID --diff UUID` | Write nach Freigabe |
| `bot hours test --team ID` | API-Erreichbarkeit |

## B.7 Web-Panel

- `GET /teams/<id>/hours` — Master + letzter Diff
- `POST .../hours/master` — Master bearbeiten (Team-Nutzer mit Team-Zugriff)
- `POST .../hours/approve` / `publish`

## B.8 Phasen Öffnungszeiten

| Phase | Umfang |
|-------|--------|
| **H0** | `hours.master.json` + Validator + `bot hours show` |
| **H1** | Website-Adapter (eine CMS-Variante oder „JSON-Datei im Repo“) |
| **H2** | Google Business Profile API read + Diff |
| **H3** | Freigabe + publish (beide Kanäle) |
| **H4** | Cron im Supervisor, Feiertags-Regeln, Multi-Standort |

**MVP:** H0 + H1 (nur Website) + manueller Google-Check-Hinweis **oder** H0–H3 mit Google read/write.

---

# Implementierungsreihenfolge (gesamt)

Empfohlen **sequenziell** (gemeinsame Freigabe-Infrastruktur nutzen):

| Schritt | Inhalt | Nutzen |
|---------|--------|--------|
| 1 | **`ApprovalService`** generisch (draft-Status, approve, audit) | einmal bauen, Mail + Hours teilen |
| 2 | E-Mail E0–E1 (IMAP + Store + Web read-only) | Postfach sichtbar |
| 3 | E-Mail E2–E3 (Agents + Freigabe + SMTP) | voller Mail-Workflow |
| 4 | Hours H0–H2 (Master + Diff Website/Google) | Abgleich sichtbar |
| 5 | Hours H3 + gemeinsame Publish-Logs | Sync mit Freigabe |
| 6 | Remote-API + OAuth + Anhänge | Betrieb skalieren |

Parallele Arbeit möglich ab Schritt 1: Mail- und Hours-Teams in getrennten PRs.

---

## Abhängigkeiten (Python-Pakete, Vorschlag)

| Paket | Zweck |
|-------|--------|
| `imap-tools` oder stdlib `imaplib` | IMAP |
| `aiosmtplib` oder stdlib `smtplib` | SMTP |
| `google-auth`, `google-api-python-client` | Google Business (Hours) |
| `httpx` | CMS-REST (bereits im Projekt) |
| optional `croniter` | Cron-Checks |

In `pyproject.toml` als optionale Extras: `mail = [...]`, `hours = [...]`.

---

## Tests (Mindestumfang)

| Bereich | Test |
|---------|------|
| Approval | Send ohne `approved` → Fehler |
| IMAP | Mock-Server oder Fixture-.eml |
| SMTP | Mock, kein echter Versand in CI |
| Hours | Diff zweier JSON-Snapshots |
| Google/Website | Adapter mit `httpx.MockTransport` |
| Web | Route RBAC: fremdes Team → 403 |

---

## Risiken & offene Fragen

| Risiko | Mitigation |
|--------|------------|
| LLM sendet trotzdem Mail | kein SMTP-Tool für Agents; nur Service nach `approved` |
| Google-API-Zugang | früh klären (Account-Typ, Verifizierung) |
| Microsoft/Google blockieren Basic-Auth | OAuth-Phase B einplanen |
| Playwright für Google | **nicht** für Produktion |
| Remote Team-Runner | Mail/Hours zunächst **lokal** am Runner; API später wie Dashboard |
| Rechtslage Firmenmail | Betreiber-Dokumentation |

**Offen:**

- [ ] Ein Postfach pro Team oder mehrere Aliase? *(Empfehlung: 1 Konto/Team)*
- [x] Freigabe/Versand: **jedes Team-Mitglied** mit Team-Zugriff; Admin nur Aufbau
- [ ] Welches CMS / welcher Google-Account-Typ beim Kunden?
- [ ] Feiertage: manuell in Master oder externe API? *(Empfehlung: manuell MVP)*

---

## Nächste Schritte (umsetzbar)

- [x] `ApprovalService` (Status-Übergänge in `bot.approval`)
- [x] `bot mail` E0–E3 (IMAP, Store, Web, Freigabe, SMTP)
- [x] `bot hours` H0–H3 (Master, Check, Diff, Freigabe, Publish)
- [x] Web: `/teams/<id>/mail`, `/hours` + Settings
- [x] Supervisor: `MailPollScheduler` + Agent-Notify bei neuen Mails
- [x] Agent-Pipeline: `email.incoming` → `email.compose` (Entwurf per LLM)
- [x] Web: Poll, Reject, Revise auf Entwürfen
- [ ] E4: OAuth2, IMAP IDLE, Anhänge, dedizierte Rollen `mail-researcher` / `mail-composer`
- [ ] H4: Cron im Supervisor für Hours, Multi-Standort, Google write produktionsreif
- [ ] Remote-API für Mail/Hours auf Team-Runner

---

*Stand main: Betrieb über Panel + CLI; siehe README Abschnitte E-Mail-Team / Öffnungszeiten.*
