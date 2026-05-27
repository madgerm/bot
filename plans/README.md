# Pläne

Hier legt ihr **Entwürfe, Roadmaps und technische Pläne** ab, bevor sie ins Ticket-System oder in die Doku wandern.

## Konvention

- Ein Plan = eine Datei, z. B. `2026-05-feature-x.md` oder `feature-x-architektur.md`.
- Kurz halten: Ziel, Annahmen, offene Fragen, nächste Schritte.
- Verlinkte Issues/PRs am Anfang der Datei nennen.

## Vorlage

Siehe `TEMPLATE.md` — kopieren und umbenennen.

## Aktuelle Pläne

- [`mvp-und-entscheidungen.md`](mvp-und-entscheidungen.md) — **MVP-Kern, Reihenfolge, Trigger, Web-Zugang, Auth, technische Defaults**; Erweiterung **Team-Medien** + **Qdrant** (globale Instanz, **Collections** pro Team: Projekt-/Codebasis, Hintergrundwissen; optional **Crawl4AI**-Domains mit periodischem Re-Index; Medien **pro Kanal global oder individuell**); **Chat:** **SQLite pro Team** + GUI zum selektiven Löschen/Leeren (RBAC); **Playwright:** global **Remote** (Ports/WS) oder **lokal** (GUI), Team-Override möglich; **optional:** Team als **Linux-User + systemd** (UI mit IP + Secret an Team-Controller).
- [`runtime-teams.md`](runtime-teams.md) — **übergreifend:** ein System, Teams, Supervisor, Hot-Reload, Bedarfsgesteuerte Agents (gilt für Coding- und Story-Setup).
- [`2026-05-26-coding-agent-system.md`](2026-05-26-coding-agent-system.md) — verteiltes Multi-Agent-Coding-System (Vision, Architektur, Phasen).
- [`2026-05-26-story-agent-system.md`](2026-05-26-story-agent-system.md) — Multi-Agent-Storytelling (80k+ Wörter, StoryDB, World/Character).
