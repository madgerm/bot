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
| 5b | **Team-Chat:** eine **SQLite pro Team** (`chat.sqlite`) + **GUI** (Verlauf filtern, Einträge selektiv löschen, Chat **komplett leeren** — nur mit Team-Rechten) |
| 6 | Webhooks (eingehend) + optional interne Events |
| 6a | **Playwright:** global `mode` = `remote` (feste Ports / WS zu Browser-Server) **oder** `local` (GUI startet Playwright auf **Nutzer-Rechner**); Team optional `source: global` / `custom` |
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

## Team-Erstellung: Vision, Sprache, Bildgenerierung (Erweiterung)

Beim Anlegen eines **Teams** sollen optionale Medien-Pipelines konfigurierbar sein (Web-UI + JSON im Team-Ordner). Das ist **nicht** Teil des harten MVP-Kerns, aber früh als **Schema** vorgesehen, damit UI und Runtime nicht umbauen müssen.

### System-Defaults vs. Team-Overrides („global“ / „individuell“)

- In der **System-Konfiguration** (z. B. `config/system.json`, Block `media_global` oder gleichwertig) werden **Standard-Endpunkte** für **Vision**, **STT**, **TTS** und **Bildgenerierung** gepflegt — das sind die **globalen Vorgaben** für alle Teams, die nichts Eigenes setzen.
- **Pro Team** und **pro Kanal** (`vision`, `stt`, `tts`, `image_generation`) wählbar:
  - **`source`: `"global"`** — dieser Kanal nutzt **1:1** die System-Vorgabe (kein doppeltes Pflegen derselben URLs im Team).
  - **`source`: `"custom"`** — das Team bringt **eigene** Werte mit (eigener Server, anderes Modell, anderer Webhook, MiniMax nur für dieses Team, …).
- **Granularität:** Mischform ist explizit erlaubt und sinnvoll, z. B. *Vision global, STT global, TTS individuell, Bilder individuell* — so bleiben günstige Defaults global, Ausreißer/Kostenfälle nur dort, wo nötig.
- **Web-UI:** Schalter oder Dropdown pro Kanal: „Systemstandard“ vs. „Eigene Einstellungen“; bei „Eigene“ werden die Felder wie unten editierbar, bei „Systemstandard“ sind sie ausgegraut und werden zur Laufzeit aus `media_global` aufgelöst.

### Vision (Bilder verstehen)

- Pro Team: **Vision-Profil** — entweder **übernommen aus `media_global.vision`** (`source: "global"`) oder **eigenes Profil** (`source: "custom"`): welches **LLM** auf welchem **Server** Bilder einliest und versteht (z. B. LiteLLM mit Multimodal-Modell).
- Felder (konzeptionell): `provider`, `api_base`, `model`, optional `max_side_px`, `timeout_seconds`, `secret_ref` für API-Keys.
- Nutzung: Uploads im Web-Panel, Screenshots, Story-Boards — Agents erhalten Bildreferenzen im Kontext und lösen Vision-Calls nach Bedarf aus.

### Sprache: TTS und STT

- **STT (Speech-to-Text):** wie Vision — **`source`: `global` oder `custom`**; bei `custom` z. B. lokales Whisper, Cloud-API oder eigener Dienst (`provider`, `endpoint`, `language`, `secret_ref`).
- **TTS (Text-to-Speech):** ebenfalls **`source`** pro Team; bei `custom`: `provider`, `voice_id`, `endpoint`, `sample_rate`, `secret_ref`.
- **Ziel:** **Sprach-Kommunikation** mit dem Team (Mikro → STT → Chat/Inbox; Antworten optional per TTS). Transport (WebRTC vs. Chunk-Upload) ist Implementierungsdetail; **Konfiguration ist team-scoped**.

### Bildgenerierung (mehrere Backends, wählbar pro Team)

Eine abstrakte Aktion „Bild erzeugen“; **`source`** pro Team entweder **`global`** (System-`media_global.image_generation`) oder **`custom`** (eigenes Backend pro Team), Backend dann wählbar:

| `image_generation.type` | Bedeutung |
|-------------------------|-----------|
| `webhook` | HTTP-POST an konfigurierte URL (Prompt, Größe, Team-Id); Antwort mit Bild-URL oder Base64. Ideal für **selbst gehostete** Generatoren (eigener Worker, ComfyUI-Bridge, …). |
| `selfhosted` | Direkter Aufruf eines **selbst gehosteten** Bilddienstes mit fest dokumentiertem JSON-Schema (z. B. lokaler SDXL/Flux/ähnlicher Dienst). |
| `minimax` | Anbindung der **MiniMax**-Bild-API (oder kompatibler Endpoint): `api_base`, `model`, `secret_ref`, ggf. Region — Feldnamen an die jeweils gültige API-Doku anpassen. |

- Gemeinsam: `default_aspect`, `max_parallel`, `timeout_seconds`.
- Ergebnis: Asset im Team-Speicher + Referenz in Chat/Message, damit Agents und Nutzer dasselbe Bild teilen.

### Platzierung in der Config

- Block `team.media` oder Datei `team-media.json` neben den Team-Metadaten; pflegbar durch **Admin** bei Team-Erstellung; für normale Team-Nutzer standardmäßig **nur lesend** (optional später erweitern).
- **System:** `media_global` in der zentralen Config; Resolver-Regel zur Laufzeit: pro Kanal effektive Config = `global` ? `media_global.<kanal>` : `team.media.<kanal>` (Pflichtfelder validieren).

### Beispiel `team.media` (Illustration, keine finale API-Garantie)

```json
{
  "team_id": "beispiel-team",
  "media": {
    "vision": { "source": "global" },
    "stt": { "source": "global" },
    "tts": {
      "source": "custom",
      "provider": "custom",
      "endpoint": "http://127.0.0.1:9101/synthesize",
      "voice_id": "de_DE_neural",
      "sample_rate": 24000,
      "secret_ref": "TTS_API_KEY"
    },
    "image_generation": {
      "source": "custom",
      "type": "webhook",
      "url": "https://bild-bridge.intern/generate",
      "headers_template": { "Authorization": "Bearer {{secret:IMG_WEBHOOK}}" },
      "default_aspect": "16:9",
      "max_parallel": 2,
      "timeout_seconds": 180
    }
  }
}
```

Wechsel z. B. auf MiniMax-Bilder durch Austausch von `image_generation`:

```json
"image_generation": {
  "source": "custom",
  "type": "minimax",
  "api_base": "https://api.minimax.io",
  "model": "image-01",
  "secret_ref": "MINIMAX_API_KEY",
  "default_aspect": "1:1",
  "timeout_seconds": 120
}
```


---

## Qdrant: globaler Server und Team-Collections

### Begriff (Qdrant ≠ SQL-Datenbank)

- Ein **Qdrant-Server** (oder Cluster) verwaltet **Collections** — Vektor-Indizes inkl. Payload. Klassische SQL-**Datenbanken** pro Team gibt es so nicht; stattdessen mehrere **Collections** mit **Namenskonvention**, die eurer Idee „pro Team eine logische Datenbank“ entsprechen.

### Global

- **System-Konfiguration** (z. B. `qdrant_global` in `config/system.json`): **URL**, optional **API-Key** (`secret_ref`), Standard-**Embedding-Profil** (Modell + Endpoint für Embeddings), globale Limits (Timeouts, maximale Batchgröße).

### Team-Initialisierung (automatisch)

Beim **Anlegen / Initialisieren** eines Teams legt die Runtime **idempotent** (nur anlegen, falls noch nicht vorhanden) mindestens diese **Collections** an — `team_slug` URL-sicher normalisiert (`[a-z0-9_]`):

| Collection | Inhalt |
|------------|--------|
| `team_{slug}__project` | **Projektwissen** — indizierte **Codebase** / Arbeitsbaum, an dem das Team arbeitet. |
| `team_{slug}__background` | **Hintergrundwissen** — längerlebige **Anleitungen / Wikis** (z. B. internes PHP-Wiki, Runbooks), bewusst getrennt von flüchtigem Chat und vom Rohtext der Repo-Dateien. |

Optional später weitere Collections (z. B. `team_{slug}__review`).

### Domains + Crawl4AI (optional pro Team)

- Pro Team: Liste **`crawl.domains[]`** (URLs/Hosts), Pflege durch **Admin**; rechtliche/robots-Konformität und Zugriffsrecht liegen beim **Betreiber**.
- **Crawl4AI** (oder gleichwertiger Crawler) erzeugt **offline nutzbare** Snapshots (Markdown/HTML) im Team-Datenbereich.
- **Periodischer Index-Job** (Cron, optional zusätzlicher Watch auf dem Snapshot-Ordner): Änderungen chunken, embedden (Embedding-Profil **global** oder **Team-Override**), **Upsert** nach Qdrant — so bleiben **Wiki-/Web-Inhalte** fortlaufend aktuell.
- **Ziel-Collection:** z. B. eine gemeinsame `team_{slug}__web` mit Payload-Feld `domain` / `canonical_url` **oder** mehrere Collections `team_{slug}__crawl__{host_hash}` — konkrete Wahl bei der Implementierung; beides ist planbar.
- **Fortschreiben:** regelmäßiger Re-Crawl / Re-Embed; veraltete Chunks über Payload (`retired_at`, `content_hash`, `crawl_generation`) aus der Suche ausblenden oder ersetzen, damit der Index kontrollierbar bleibt.

### Auflösung für Agents

- Tools und Agents lesen **materialisierte Collection-Namen** aus der **Team-Registry** (beim Team-Init gesetzt), keine in Agent-Code fest verdrahteten Namen.

---

## Chat-Verlauf: SQLite pro Team

### Ziel

- Der **Chat-Verlauf** (Nutzer ↔ Agents; optional auch interne Agent-/Tool-Logs, falls gewünscht) wird **persistent** gespeichert — nicht nur im RAM.
- **Pro Team genau eine SQLite-Datei** (z. B. `data/{team_slug}/chat.sqlite`), damit Daten **team-isoliert**, **einfach backupbar** und bei Team-Export/Delete **als Ganzes** handhabbar sind.

### Inhalt & Schema (konzeptionell)

- Mindestens Tabelle **`messages`**: `id` (UUID), `agent_id`, `role` (`user` / `assistant` / `system` / …), `content`, `created_at`, `metadata` (JSON für Anhänge, Modellname, Token-Hinweise), optional `thread_id` / `conversation_id` für mehrere Fäden.
- Indizes auf `created_at`, `agent_id`, `thread_id`; Migrationen (z. B. Alembic oder SQL-Skripte) versionieren das Schema.
- Bei großen Löschaktionen: **Batch**-`DELETE` + später `VACUUM` in einem **Wartungsfenster**, damit die UI nicht blockiert.

### Rechte (RBAC)

- **Lesen, einzelne Messages löschen, Verlauf teilweise oder komplett leeren:** nur **Team-Mitglieder** (bzw. Rollen mit explizitem „Chat-Verwaltung“-Recht innerhalb des Teams).
- **Admin** kann je nach Organisations-Policy **Team-Reset** (z. B. Team löschen inkl. SQLite) — klar von „nur Chat leeren“ trennen.

### GUI (Komfort)

- **Verlaufsbrowser:** Filter nach Agent, Zeitraum, Freitext; Vorschau + Detailansicht.
- **Selektives Löschen:** Checkboxen + „Ausgewählte löschen“; Kontextmenü auf einzelner Nachricht; optional „**alles vor Datum …** löschen“.
- **Komplett leeren:** eigener Button mit **zweistufiger Bestätigung** („Team-Chat wirklich vollständig leeren?“), damit keine Fehlklicks passieren.
- Optional: **Audit-Log** (wer hat wann wie viele Zeilen gelöscht / geleert) **ohne** den gelöschten Inhalt — für interne Nachvollziehbarkeit.

### Betrieb

- SQLite liegt im **Team-Datenverzeichnis**; Datei in **Backups** einschließen. Bei extremen Größen später: Archiv-Tabellen oder Export — **kein** MVP-Zwang.

---

## Browser-Automation: Playwright (global, Remote oder lokal)

### Ziel

- Agents (und optional die GUI) sollen **Browser-Automation** einheitlich über **Playwright** nutzen können — wahlweise über einen **dedizierten Server** mit **festgelegten Ports / WebSocket-Endpoints** oder **lokal** auf dem Rechner des Nutzers.

### Global (`playwright_global` in der System-Config)

- **`mode`: `remote` | `local`**
  - **`remote`:** Anbindung an einen **Browser-/Playwright-Worker** im Netzwerk — z. B. feste **Ports** pro Profil (Chromium/Firefox/WebKit), oder ein dokumentierter **Playwright-WebSocket-Endpoint** (typisch `ws://host:PORT/...`). Felder: `base_host`, `ports` oder `ws_endpoints[]`, TLS, `secret_ref` für Token/mTLS.
  - **`local`:** Standard für „**ab lokal**“: Über die GUI-Aktion („**Playwright lokal starten**“ / „Lokaler Browser“) wird auf dem **Rechner des Nutzers** eine Playwright-Session gestartet (Voraussetzung: installierte Browser-Binaries). Gut für Entwicklung, kleine Teams oder wenn kein zentraler Browser-Server existiert.

### Team-Overrides (wie bei Medien / Qdrant-Konvention)

- Pro Team: `playwright.source`: `global` | `custom` — bei `custom` eigene `mode`/`endpoints`/Ports (z. B. eigener Browser-Pool für ein Kunden-Team).

### Sicherheit (Remote)

- Remote-Browser **nicht** ungeschützt ins offene Internet; mindestens **VPN/mTLS/Token**, strikte **Team-Isolation** (Sessions nur mit `team_id`-Kontext), Logging ohne sensible Seiteninhalte.

### MVP-Hinweis

- Zentrale Browserfarm ist **betrieblich** anspruchsvoller; MVP oft **`local`** zuerst, **`remote`** nachziehen — beide Pfade im **Config-Schema** und in der **GUI** vorsehen (Schalter „Systemstandard“ vs. „eigener Endpoint“).

---

## Deployment-Variante: Team als Linux-User + systemd (hart isoliert)

### Idee (Design-Alternative zur „alles unter einem OS-User“)

- Jedes **Team** kann als **eigener Linux-Account** (eigener Systembenutzer mit **Homeverzeichnis** `/home/team_<slug>/` o. Ä.) betrieben werden — das Team ist damit ein **hartes Isolations-Primitive** auf OS-Ebene (Dateirechte, Ressourcen, Prozessbaum).
- Der **Agent-/Team-Prozess** läuft **nicht** unter dem Login des Menschen, der die UI bedient, sondern unter diesem **Team-User**; Daten (`data/`, SQLite, Inboxen, Crawl-Snapshots) liegen **im Home** des Team-Users.
- **systemd** (User-Unit oder System-Unit pro Team): Dienst **„Team Rubber“** startet beim Boot **selbstständig** den Team-Agent-Controller und hält ihn am Leben (`Restart=on-failure`).
- **Kopplung an die zentrale UI / den „Agent Controller“ oben:** die GUI kennt **`server_ip`** (oder Hostname) und einen **gemeinsamen Geheim-`hashkey`** (besser: **API-Token** / **mTLS** — der Begriff *Hashkey* steht hier für einen **langen, nicht erratbaren Shared Secret**, der beim Provisionieren erzeugt wird). Der **Controller** auf dem Team-Host exponiert einen **HTTPS-API-Port** (nur intern/VPN), authentisiert Anfragen mit diesem Secret, und steuert den lokalen Supervisor.

### Ablauf (skizzenhaft)

1. **Provisioning:** Admin legt Team an → Skript erstellt Linux-User, Home, Verzeichnisstruktur, schreibt `team.env` mit `TEAM_SECRET`, installiert **systemd-Unit**.
2. **Laufzeit:** systemd startet `agent-team@rubber` → Prozess lädt Config aus `~team_rubber/...`, öffnet nur diese Pfade.
3. **UI:** Operator trägt in der **obersten** Steuerungs-GUI „**Remote-Team-Host**“ + **Secret** ein → Panel spricht per TLS mit dem Team-Controller → Status, Chat, Dateien (über definierte APIs), **kein** direktes SSH für normale Nutzer nötig.

### Vorteile

- **Isolation:** Kompromittierung eines Teams reißt nicht sofort alle anderen Team-Homes mit.
- **Fairness / Limits:** `systemd` **CPUQuota=**, **MemoryMax=**, **TasksMax=** pro Team-Dienst.
- **Klare Pfade:** Backup = Home des Users archivieren.

### Nachteile / Kosten

- **Mehr Betrieb:** User-Anlage, systemd-Politik, Secret-Rotation, Monitoring pro Host.
- **Nicht jede Kleininstallation** will System-User — daher **optional**: gleiche Software auch im **Single-User-Modus** (alles unter einem Dienst) weiter anbieten.

### Empfehlung

- **Produkt:** beide Modi vorsehen — **`deployment.topology`**: `single_user` | `linux_user_per_team` (Namen final bei Implementierung).
- **Sicherheit:** *Hashkey* in der Praxis als **hochentropisches Token** (z. B. 256 Bit) behandeln, **TLS**, **kein** Secret in Git; optional **mTLS** zwischen zentraler UI und Team-Host.
- **Begriff „Primitive“:** im Sinne von **Isolation-Primitive** auf OS-Ebene (Team = User), nicht als eigene Programmiersprache.

---

## Hinweis zur „Reihenfolge“

Wenn du „nervst“ bis alles läuft — gut: dann dient diese Datei als **Referenz**, gegen die wir Iterationen spiegeln. Reihenfolge ist **anpassbar**, solange der **MVP-Kern** oben nicht dauerhaft übersprungen wird.

---

*Status: verbindliche Planungs-Defaults (können bei Bedarf revidiert werden)*  
*Letzte Änderung: 2026-05-27*

