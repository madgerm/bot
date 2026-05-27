# Runtime, Teams und Supervisor

Dieses Dokument fasst **übergreifende Architektur-Entscheidungen** zusammen, die für **Coding**- und **Story**-Setups gleichermaßen gelten. Die domänenspezifischen Details stehen in `2026-05-26-coding-agent-system.md` und `2026-05-26-story-agent-system.md`.

---

## Ein System, spezialisierte Teams

- Es gibt **eine gemeinsame Code-Basis** und **eine Agent-Runtime** (ein zu startender Dienst bzw. ein klar definierter Einstieg wie `agent_system.py`).
- **Teams** sind die fachliche und organisatorische Einheit (z. B. „Code · Webseite 1“, „Story · Projekt X“): jeweils eigener **Orchestrator** (oder gleichwertige Team-Leitung), eigene **Subagents**, eigene **Daten** und Konfiguration.
- **Coding** und **Story** sind **keine getrennten Produkte im Sinne zweier Repos**, sondern **Spezialisierungen / Presets** desselben Systems (andere Rollen, Ports, `task_models`, Datenpfade).

---

## Hierarchie

```
Agent-System (Runtime / Supervisor)
└── Team A (z. B. Coding · Webseite 1)
│   └── Orchestrator + Subagents (Coder, Tester, …)
└── Team B (z. B. Story · Roman Y)
    └── Orchestrator + Subagents (Drehbuch, Logik-Prüfer, …)
```

- **Agent-System:** läuft dauerhaft; lädt Konfiguration; verwaltet Lebenszyklus der Worker.
- **Team:** Konfiguration + Grenzen (Wer darf mit wem sprechen? Welcher Datenraum?).
- **Agent:** konkreter Worker (LLM-Schleife, Tools). **Bedienoberfläche** für Menschen: ein gemeinsames Web-Panel (siehe `mvp-und-entscheidungen.md`); keine Pflicht zu „einem öffentlichen Port pro Agent“.

---

## Einmal starten, Teams arbeiten lassen

- Der **Nutzer startet nur das Agent-System** (ein Befehl / ein Dienst).
- Danach können **Teams arbeiten**, sobald Aufgaben, Chat oder der Orchestrator **Bedarf** signalisieren.
- **Neue Teams** können **ohne vollständigen Neustart** der Runtime angelegt werden: Konfiguration (z. B. neue Ordner / `agent.json` / API-Call) wird **zur Laufzeit** registriert (**Hot-Reload** bzw. dynamisches Nachladen).
- **Einzelne Agents** müssen nicht alle beim Hochfahren des Systems laufen; sie können **on demand** gestartet werden (Ressourcen, Kosten, Last).

*Wer startet wen intern?* — Ein **Supervisor** (Teil der Runtime oder klar abgegrenztes Modul) entscheidet anhand von Regeln, **welches Team** und **welcher Agent** aktiv werden. Der Nutzer startet nicht jeden Agent von Hand.

---

## Prozessmodell (Implementierungsdetail)

Ob ein Agent als **eigener OS-Prozess**, als **Subprozess** oder als **async Task** in wenigen Prozessen läuft, ist eine **technische Wahl** (Isolation vs. Overhead). Die **fachlichen Anforderungen** oben gelten unabhängig davon; die konkrete Variante wird bei der Implementierung festgelegt und dokumentiert.

---

## Orchestrator und LLM-Server

- Jeder Schritt, der ein LLM braucht, folgt grob dem Muster: **Kontext bauen → Anfrage an den LLM-Server (z. B. LiteLLM/Ollama) → Antwort (ggf. mit Tools) verarbeiten**.
- Der **Orchestrator** ist damit **nicht** „nur ein dünner Proxy“, sondern übernimmt u. a. **Zerlegung der Ziele**, **Delegation** an Subagents, **Zustand** offener Arbeit, **Routing** (Model/Task), **Retries** und Anbindung an Dateien, Qdrant, Git usw. — oft über **Tools** und Nachrichten an andere Agents.

---

## Verteilung auf mehrere Rechner

- **Ein Host, gemeinsame Pfade:** oft ausreichend mit **Direct Mode** (Datei-Inboxen), wie in den domänen-Plänen skizziert.
- **Mehrere Maschinen / Lastverteilung:** Nachrichten und ggf. Aufträge sollten über einen **Broker** (z. B. Redis) und explizite **Adressierung** laufen; reines Schreiben in ein **lokales** `inbox/`-Verzeichnis reicht dann nicht mehr für alle Fälle.

Details und Beispiel-JSON bleiben in den jeweiligen System-Plänen unter Kommunikation / `system.json`.

---

## Betriebs-Isolation (optional)

- Statt alle Team-Daten unter **demselben OS-Benutzer** zu mischen, kann jedes Team als **eigener Linux-Account** mit **systemd** laufen (Homeverzeichnis pro Team, Secret für die Anbindung der zentralen UI). Zusätzlich: **einmalige** Installation oft **als root**, danach wahlweise **systemweiter** Team-Dienst oder **pro-login-user** (`systemctl --user`). Details: **`mvp-und-entscheidungen.md`** (*Deployment-Variante …*).

---

## Trigger, Web-Zugang, Auth (festgelegt)

Konkrete Defaults (Inbox, Webhook, Polling, ein öffentliches Panel, Admin vs. Team-Nutzer, MVP-Reihenfolge, Secrets, Prozessmodell-Empfehlung, Story/Modell-Haltung): **`mvp-und-entscheidungen.md`**.

---

*Status: ergänzende übergreifende Planung*  
*Letzte Änderung: 2026-05-27*
