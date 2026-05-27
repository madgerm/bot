# MVP, Reihenfolge und Architektur-Entscheidungen

Ergänzung zu `runtime-teams.md` und den domänen-Plänen. **Ziel:** umsetzbare Defaults mit **maximalem Sinn** für Betrieb, Sicherheit und spätere Skalierung — nicht „minimalster Prototyp um jeden Preis“.

---

## Was *wirklich* zuerst drin sein muss (MVP-Kern)

Ohne diesen Kern wird jedes Team-Setup frustrierend unsicher oder nicht bedienbar:

1. **Runtime / Supervisor** — ein Dienst startet, lädt Teams dynamisch, überwacht Worker.
2. **Konfiguration** — `system.json` (oder äquivalent) + Team-/Agent-Definitionen; **Hot-Reload** neuer Teams ohne Full-Restart.
3. **Nachrichten / Aufträge** — file-basierte `inbox/`/`outbox/` (wie in den Plänen) **plus** stabiles **Message-JSON** mit `id`, `schema_version`, `status`, Timestamps (siehe unten).
4. **Mindestens ein vollständiges Team** — Orchestrator + **zwei** Subagents (z. B. „Ausführen“ + „Prüfen“), damit Delegation und Review-Schleife **real** erprobt werden.
5. **LLM-Anbindung** — LiteLLM (oder direkter Client) + **Model-Routing** nach Task-Kategorie; Retry + Fallback (kurz, aber vorhanden).
6. **Web-Panel (karg, aber echt)** — **HTTPS**, Login, **Team-Sicht** für Nutzer; Admin-Bereich für User/Team-Verwaltung (siehe Auth).
7. **Periodischer Agent-Loop** — Jeder Agent **pollt** die Inbox in konfigurierbarem Intervall; zusätzlich **sofortige** Reaktion auf neue Dateien (Watch/Trigger), damit nicht alles nur „alle 5 s“ ist.

Alles andere (Qdrant, alle Prüfer-Rollen, Multi-Machine-Broker, Export PDF/Epub, Telegram …) ist **Phase 2+**, sobald der Kern stabil läuft.

---

## Reihenfolge der Implementierung (Vorschlag, nicht Dogma)

Die exakte Reihenfolge ist weniger wichtig als **„Kern zuerst“**. Sinnvolle Abhängigkeiten:

| Schritt | Inhalt |
|--------|--------|
| 1 | Config-Loader + Validierung + Hot-Reload API/Datei-Watch |
| 2 | Message-Format + Inbox/Outbox + Status (`pending` → `processing` → `done` / `failed`) |
| 3 | Supervisor + **ein** Team-Template + Orchestrator + 2 Subagents |
| 4 | LLM-Client + Router + Retries/Fallback (knapp) |
| 5 | Web: Auth + Admin (User/Team) + Team-Dashboard (Status, letzte Messages) |
| 6 | Webhooks (eingehend) + optional interne Events |
| 7 | Qdrant, weitere Agents, Broker-Multi-Machine, domänenspezifische UIs |

Parallel können **Coding**- und **Story**-Spezifika angebaut werden, sobald Schritt 3 steht — sie teilen denselben Kern.

---

## Trigger: wann arbeitet ein Agent?

**Alle gelten parallel** (OR-Verknüpfung), was zuerst eintritt:

| Trigger | Beschreibung |
|--------|----------------|
| **Neue Datei in `inbox/`** | Hauptpfad: anderer Agent oder Orchestrator legt Auftrag ab → Worker reagiert (Watch + Poll als Absicherung). |
| **Webhook** | Externes System (CI, Formular, eigener Dienst) schreibt Nachricht oder ruft HTTP-Endpoint auf → Supervisor erzeugt Message → richtet sich an Team/Agent. |
| **Periodisch (Polling)** | Jeder Agent läuft in einer Schleife: Inbox lesen, konfigurierbares `interval_seconds`; zusätzlich **„Idle-Gesundheit“** — z. B. kurzer Check „gibt es hängende Tasks / inkonsistente States?“ wenn keine neue Message da ist (dein Wunsch: *automatisch immer prüfen ob alles ok ist*). |
| **Start / Resume** | Beim Hochfahren des Workers oder nach Crash: Backlog aus `pending` verarbeiten. |

**Sinnvoll:** Watchdog + Polling kombinieren — Watch ist schnell, Polling fängt verpasste Events und Netzwerk-Glitches ab.

---

## „Ein Panel vs. viele Ports“ — Klärung (Entscheidung)

**Nach außen (Menschen & Browser):** **ein** Einstieg — **eine HTTPS-Origin** (eine Domain + TLS), z. B. `https://agents.example.com`. Darüber: Login, Team-Auswahl, Dashboard, Chat, Dateien — **ein** kohärentes Panel.

**Nach innen (Technik):** frei wählbar und **nicht** dem Endnutzer sichtbar:

- Entweder **ein** FastAPI-Prozess mit **Routern** pro Team/Untermodul, **oder** mehrere interne Dienste auf **localhost-Ports**, die nur hinter **einem Reverse Proxy** (Caddy/nginx) hängen.

Die früheren Tabellen mit `http://host:8765` … sind **Entwickler-/Debug-Ansicht** oder **interne** Zuordnung — nicht die Forderung, dass jeder Endnutzer zehn Ports bookmarken soll.

**Kurz:** **Ein Panel / ein öffentlicher Zugang**; Ports sind **Implementierungsdetail** hinter Reverse Proxy oder im selben Prozess.

---

## Auth und Rollen (wie von dir beschrieben, präzisiert)

| Rolle | Rechte |
|-------|--------|
| **Admin** | Legt **Nutzer** und **Teams** an; weist Nutzer Teams zu; sieht Systemzustände (optional globale Metriken). |
| **Nutzer (Team-Mitglied)** | Sieht und bedient **nur** die Teams, denen sie zugeordnet ist; keine fremden Daten, keine Admin-Funktionen. |

**Technisch sinnvoll:** Session-Cookies + serverseitige **Team-Scoping**-Prüfung auf **jeder** API-Route (nicht nur im UI verstecken). Optional später: feinere Rollen innerhalb eines Teams (Leser vs. Operator).

---

## Weitere Punkte — Entscheidung „was am meisten Sinn macht“

### Secrets (Passwörter, Tokens, API-Keys)

- **Nie** Klartext in Git oder in `agent.json`, die versioniert werden.
- **Sinnvoll:** Umgebungsvariablen + optional `secrets/` außerhalb des Repos oder Secret-Store; Referenzen in Config nur als Namen (`SECRET_REF=...`).

### Message-Schema & Idempotenz

- Jede Message hat **`id` (UUID)** und **`schema_version`**.
- **Idempotent:** gleiche `id` erneut einliefern → kein doppeltes Arbeiten; Status `done` verhindert erneute Ausführung (oder explizites `retry` mit neuem `id`).

### Prozessmodell (Default-Empfehlung)

- **Supervisor** als eigener Prozess.
- **Pro Agent ein Subprozess** (oder Pool mit hartem Limit), damit Abstürz/Tools/Blocking **ein** Worker nicht die gesamte Runtime mitreißen und Ressourcen (RAM, CPU) per OS begrenzbar sind.
- Für extrem ressourcenschwache Dev-Maschinen kann die Implementierung **temporär** Worker im selben Prozess starten — **Zielbild** bleibt Subprozesse.

### Observability

- Strukturiertes **Logging** (ohne Secrets), Korrelation über `message_id` / `team_id` / `agent_id`.
- Einfache **Health-Endpoints** für den Supervisor (läuft, Queue-Tiefe, letzte LLM-Fehler).

### Daten & Story-Konflikte (zwei Agents, eine Szene)

- **Sinnvoll:** pro bearbeitbare Einheit (Szene/Datei) ein **Lock** oder **Optimistic Concurrency** (`version` im JSON) — wer zuerst schreibt gewinnt, der andere bekommt Konflikt-Meldung statt stiller Überschreibung.

### Multi-Machine / Last

- Lokal: **direct** + Datei-Inbox.
- Verteilt: **Broker** + explizite Ziele — wie in `runtime-teams.md`; nicht erst „alles umbauen“, wenn der MVP auf einem Host steht.

### Rechtliches / Inhalt (Story, unzensierte Modelle)

- Das Produkt **erzwingt keine inhaltliche Zensur** und **blockiert** LLM-Output **nicht** über zusätzliche Filter — im Einklang mit dem Wunsch, **unzensierte** Modelle zu nutzen, ohne künstliche Begrenzung dessen, was das Modell liefert.
- **Verantwortung** liegt beim **Betreiber** (Hosting, Zugriff, wer das System nutzt); öffentliche Ausspielung bleibt eine **Betreiber-Entscheidung** (Netzwerk, Auth, ob Stories veröffentlicht werden).

---

## Hinweis zur „Reihenfolge“

Wenn du „nervst“ bis alles läuft — gut: dann dient diese Datei als **Referenz**, gegen die wir Iterationen spiegeln. Reihenfolge ist **anpassbar**, solange der **MVP-Kern** oben nicht dauerhaft übersprungen wird.

---

*Status: verbindliche Planungs-Defaults (können bei Bedarf revidiert werden)*  
*Letzte Änderung: 2026-05-27*
