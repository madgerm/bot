# Planung: Story Agent System

## Vision

Ein distributed multi-agent Storytelling-System für große Projekte (80.000+ Worte). Eine Code-Basis, N Agents über JSON-Configs. Web Panel mit Agent Manager, File Editor, Character Builder, World Editor, Qdrant-Config. Alles konfigurierbar über die Web-Oberfläche.

**Übergreifend (ein System, Teams, Supervisor, kein Full-Restart für neue Teams):** siehe [`runtime-teams.md`](runtime-teams.md).

---

## Architektur

### Eine Code-Basis, N Agents

```
/home/worker-test-llm/story/
├── agent_system.py              # EIN mal Python Code
├── agents/                      # Agents werden via JSON definiert
│   ├── orchestrator/
│   │   ├── agent.json           # Port 8770, LLM, capabilities...
│   │   ├── memory/
│   │   └── inbox/
│   ├── drehbuch-autor/
│   │   ├── agent.json           # Port 8771
│   │   └── inbox/
│   └── [beliebig viele weitere agents...]
├── shared/
│   └── lib/
│       ├── base_agent.py
│       ├── model_router.py
│       ├── litellm_client.py
│       ├── story_db.py          # Zentraler Data Layer
│       └── qdrant_client.py
├── config/
│   ├── system.json              # Global config
│   └── task_models.json        # Model-Routing
└── data/
    └── [stories...]
```

**Start:**
```bash
python agent_system.py --type story
```
→ Liest alle `agent.json` in `agents/`, startet für jeden einen Port + Web Panel.

---

## Multi-Orchestrator (je Story ein Orchestrator)

```
/story/
├── agents/
│   ├── orchestrator-meine-story/ (Port 8770)
│   │   └── subagents: drehbuch-autor, drehbuch-ausarbeiter, logik-pruefer...
│   └── orchestrator-andere-story/ (Port 8790)
│       └── subagents: drehbuch-autor-2, logik-pruefer-2...
```

Jeder Orchestrator verwaltet seine eigenen Subagents. Getrennte Ports, getrennte Daten.

---

## Hot-Reload

Wenn neuer Agent im Web Panel erstellt:
1. agent.json + inbox/ + memory/ werden angelegt
2. Agent-Prozess startet sofort auf konfiguriertem Port
3. Kein Neustart des gesamten Systems nötig
4. Dashboard zeigt neuen Agent sofort an

---

## Auth

```json
{
  "system": {
    "auth": {
      "enabled": true,
      "users": [
        { "username": "admin", "password": "hashed_password" }
      ]
    }
  }
}
```

Web Panel: Login-Screen mit User/Passwort. Session-Cookies.

---

## Agent-Kommunikation (konfigurierbar)

```json
{
  "system": {
    "communication": {
      "mode": "direct",  // "direct" | "broker"
      "broker": {
        "host": null,
        "port": null,
        "type": "redis"
      },
      "direct": {
        "inbox_path": "/home/worker-test-llm/story/{agent}/inbox/"
      },
      "multi_machine": {
        "enabled": true,
        "agents": [
          { "name": "drehbuch-ausarbeiter", "host": "10.95.60.219", "ssh_key": "~/.ssh/id_ed25519" }
        ]
      }
    }
  }
}
```

**Direct Mode:** Agent schreibt direkt in Target-Agent's inbox/ via Dateisystem.

**Broker Mode:** Redis/Rabbitmq als Message-Queue dazwischen (für Multi-Machine).

**Multi-Machine:** SSH-Zugriff auf andere Server, Agents können remote laufen.

---

## Web Panel Screens

**1. Dashboard**
- Alle Agents (running/stopped)
- Aktive Kapitel/Szenen
- Story-Progress
- Letzte Activity

**2. Agent Manager**
- Liste aller Agents
- [Neuer Agent erstellen]
- Subagents hierarchisch unter Orchestrator
- Agent bearbeiten/löschen/starten/stoppen

**3. Story Planner**
- Neue Story erstellen
- Genre, Setting, Hauptcharaktere
- Plot-Builder
- Kapitel-Outlines

**4. Character Manager**
- Alle Charaktere
- Beziehungen visualisieren
- Character-Arc Tracker
- Neu erstellen/bearbeiten

**5. World Editor**
- Orte erstellen/bearbeiten
- World-Regeln
- Timeline
- Logik-Regeln

**6. Szenen-Editor**
- Aktuelle Szene bearbeiten
- Kapitel-Vorschau
- Szene-Status (in Bearbeitung/Review/Fertig)

**7. Review Panel**
- Issues von allen Prüfern
- Logik-Fehler
- World-Inkonsistenzen
- Stil-Probleme

**9. Chat**
- Mit allen Agents kommunizieren
- Orchestrator Anweisungen

**10. File Browser + Editor**
- Alle Dateien durchsuchen
- Direkt editieren
- Syntax Highlighting

**11. Story erstellen**
- [Neue Story] Button im Dashboard
- Erstellt automatisch die Struktur:
  ```
  story/
  ├── AGENTS.md              # Story-Context (Genre, Setting, Ton)
  ├── meta.json              # Metadaten
  ├── world/
  │   ├── orte.md            # Alle Orte
  │   └── regeln.md          # World-Regeln
  ├── characters/
  │   ├── protagonist.json   # Hauptcharakter
  │   └── [weitere].json
  └── chapters/
      └── kapitel-001/
          ├── szene-001.md
          └── szene-002.md
  ```
- AGENTS.md wird mit User-Input gefüllt: Genre, Setting, Hauptcharaktere
- Optional: Vorlage wählen (Sci-Fi, Fantasy, Thriller...)

**12. Qdrant Config**
- Global oder per Orchestrator
- Collection Management
- LLM-Zuordnung
- Memory durchsuchen

---

## Agent erstellen (im Web Panel)

```
Neuer Agent
├── Name: [___________]
├── Port: [8770]          # automatisch nächster freier
├── Master Agent: [Orchestrator]
├── LLM Model: [Dropdown]
├── Task Category: [plot_structure|scene_writing|logic_check|...]
├── Capabilities:
│   ├── [x] creative_writing
│   ├── [x] world_building
│   ├── [x] character_development
│   └── ...
├── Contact Other Agents: [ ] orchestrator [x] drehbuch-ausarbeiter [x] logik-pruefer
└── [Erstellen]
```

→ Erstellt:
- `/story/agents/[name]/agent.json`
- `/story/agents/[name]/inbox/`
- `/story/agents/[name]/memory/`

---

## Subagents unter Orchestrator

```
Orchestrator (Master - Port 8770)
├── Subagents:
│   ├── drehbuch-autor (Port 8771)
│   ├── drehbuch-ausarbeiter (Port 8772)
│   ├── logik-pruefer (Port 8773)
│   ├── worldkeeper (Port 8774)
│   ├── detail-pruefer (Port 8775)
│   ├── character-manager (Port 8776)
│   ├── stil-pruefer (Port 8777)
│   ├── deutsch-pruefer (Port 8778)
│   └── zeit-pruefer (Port 8779)
```

---

## Config (config/system.json)

```json
{
  "system": {
    "name": "story-agents",
    "host": "10.95.60.219",
    "auth": {
      "enabled": true,
      "users": [
        { "username": "admin", "password": "hashed_password" }
      ]
    },
    "communication": {
      "mode": "direct",
      "multi_machine": {
        "enabled": false
      }
    },
    "polling": {
      "interval_seconds": 5
    },
    "llm": {
      "provider": "litellm",
      "api_base": "http://10.95.60.51:11434"
    }
  },
  "qdrant": {
    "global": {
      "enabled": true,
      "host": "http://10.95.60.51:6333",
      "collections": {
        "story-memory": {
          "description": "Memory für alle Story Agents",
          "llm": "ollama/qwen3.5-9b-heretic"
        },
        "world-consistency": {
          "description": "Worldkeeper Checks",
          "llm": "ollama/qwen2.5-7b-instruct-uncensored"
        }
      }
    }
  },
  "story": {
    "target_word_count": 80000,
    "scene_target_words": 1500,
    "max_review_loops": 5
  }
}
```

---
## Task-basiertes Model-Routing

```json
{
  "task_models": {
    "story_planning": {
      "default": "ollama/qwen3-14b-tools-thinking",
      "alternatives": ["ollama/llama3.1-8b-tools"]
    },
    "plot_structure": {
      "default": "ollama/qwen3.5-9b-heretic",
      "alternatives": ["ollama/llama-3.1-8b-dolphin-uncensored"]
    },
    "scene_writing": {
      "default": "ollama/llama-3.1-8b-dolphin-uncensored",
      "alternatives": ["ollama/qwen3.5-9b-heretic", "ollama/gemma2-9b-dirty-muse-writer-x"]
    },
    "dialog": {
      "default": "ollama/qwen3.5-9b-heretic",
      "alternatives": ["ollama/llama-3-8b-lexi-uncensored"]
    },
    "world_consistency": {
      "default": "ollama/qwen2.5-7b-instruct-uncensored",
      "alternatives": ["ollama/qwen2.5-abliterate"]
    },
    "logic_check": {
      "default": "ollama/qwen2.5-14b-tools",
      "alternatives": ["ollama/qwen3-14b-tools-thinking"]
    },
    "character_consistency": {
      "default": "ollama/qwen2.5-7b-instruct-uncensored",
      "alternatives": ["ollama/qwen2.5-14b-tools"]
    },
    "style_check": {
      "default": "ollama/llama-3.1-8b-dolphin-uncensored",
      "alternatives": ["ollama/gemma2-9b-dirty-muse-writer-x"]
    },
    "grammar_check": {
      "default": "ollama/qwen2.5-coder-14b-tools-insert",
      "alternatives": ["ollama/qwen2.5-14b-tools"]
    },
    "tense_check": {
      "default": "ollama/qwen2.5-14b-tools",
      "alternatives": ["ollama/qwen2.5-coder-14b-tools-insert"]
    },
    "detail_check": {
      "default": "ollama/qwen2.5-abliterate",
      "alternatives": ["ollama/qwen3.5-9b-heretic"]
    }
  }
}
```

---

### Orchestrator - Autonomer Manager

**Der User ist der Designer/Architekt** — er weiß was er will (Story-Idee, Genre, Charaktere), aber nicht wie man es technisch umsetzt.

**Der Orchestrator trifft alle kreativen und technischen Entscheidungen automatisch:**

```python
# User sagt nur:
goal = {
  "type": "sci-fi roman",
  "setting": "München 2045",
  "main_characters": ["Max", "Anna"],
  "word_count": 80000,
  "tone": "düster aber hoffnungsvoll"
}

# Orchestrator plant selbst:
plan = {
  "chapters": 20,
  "scenes_per_chapter": 5,
  "plot_structure": "3-aktstruktur",
  "world_details": {...},
  "character_arcs": {...}
}
```

**Der Orchestrator fragt nur wenn's kritisch ist:**
- "Soll der Character Max ein Android sein oder ein Mensch mit KI-Implantaten?"
- "Mehr Action oder mehr Dialoge?"
- "Welches Ende: gut oder bitter-süß?"

**Wenn User "keine Ahnung" sagt → Orchestrator entscheidet mit Best-Practice**

---

## Agent JSON Schema

```json
{
  "agent": {
    "name": "logik-pruefer",
    "role": "Logik Prüfer",
    "enabled": true,
    "master": "orchestrator",
    "llm": {
      "provider": "litellm",
      "model": "ollama/qwen2.5-14b-tools",
      "api_base": "http://10.95.60.51:11434",
      "fallback": "ollama/qwen3-14b-tools-thinking"
    },
    "web": {
      "enabled": true,
      "port": 8773
    },
    "task_category": "logic_check",
    "capabilities": [
      "scene_logic",
      "position_tracking",
      "temporal_consistency"
    ],
    "autonomous": true,
    "ask_before": ["world_rules", "character_behavior"],
    "tools": ["terminal", "file"],
    "contact_other_agents": ["orchestrator", "drehbuch-ausarbeiter", "worldkeeper"],
    "qdrant": {
      "use_global": true
    }
  }
}
```

---

## StoryDB - Zentraler Data Layer

```python
class StoryDB:
    """Alle Agents nutzen dieselben Daten"""
    
    def __init__(self, story_path):
        self.path = story_path
    
    # Szene für Szene arbeiten (Performance)
    def get_scene(self, chapter, scene_id):
        """Einzelne Szene laden"""
        
    def update_scene(self, chapter, scene_id, content):
        """Szene updaten"""
        
    def add_scene(self, chapter, scene_number, content):
        """Neue Szene"""
    
    # Global für Full-Checks (bei Bedarf)
    def get_all_scenes(self):
        """Komplette Story laden"""
        
    def get_characters(self):
        """Alle Character-Definitionen"""
        
    def get_world(self):
        """Komplette World-Definition"""
        
    def search_memory(self, query):
        """Qdrant Semantic Search"""
    
    # Story pro Projekt/Orchestrator
    def get_story(self, story_name):
        """Story-Daten für bestimmten Orchestrator"""
```

---

## Error Handling & Retry

```python
# LLM Call fehlschlägt:
1. Retry mit exponential backoff (3 Versuche)
2. Falls Modell nicht verfügbar -> Fallback Modell
3. Falls immer noch fehlschlägt -> User benachrichtigen (Chat + Dashboard)
4. Message status = "failed" -> kann manuell wiederholt werden
```

---

## Workflow (Parallel & Szenenweise)

```
Kapitel 1:
├── Szene 1: Drehbuch-Ausarbeiter (model: scene_writing)
│            └── Parallel:
│                ├── Logik-Prüfer (logic_check)
│                ├── Worldkeeper (world_consistency)
│                ├── Detail-Prüfer (detail_check)
│                └── Character-Manager (character_consistency)
│
├── Szene 2-10: ...
│
└── Review Loop pro Szene (max 5x)
    → Fix -> Prüfer erneut -> OK -> nächste Szene

Kapitel 2-N: Gleiche Struktur

Final: Global-Check über alle Kapitel
```

---

## Character-Definition

```json
{
  "character": {
    "id": "max_mueller",
    "name": "Max Müller",
    "role": "Protagonist",
    "age": 35,
    "appearance": {
      "height": "180cm",
      "hair": "kurz, blond",
      "eyes": "blau",
      "special": "kleine Narbe am Kinn"
    },
    "personality": {
      "traits": ["mutig", "nerdiös", "loyal"],
      "strengths": ["analytisch", "geduldig"],
      "weaknesses": ["perfektionistisch", "überschätzt sich"]
    },
    "background": "Aufgewachsen in München, Studium der Informatik...",
    "relationships": [
      { "to": "anna_schmidt", "type": "Freundin", "dynamic": "unterstützend aber kritisch" },
      { "to": "thomas_wagner", "type": "bester Freund", "dynamic": "konkurrierend" }
    ],
    "speech_pattern": "kurze Sätze, oft mit Fachbegriffen",
    "goals": ["Welt verbessern", "Anerkennung bekommen"],
    "arc": "vom Perfektionisten zum Teamplayer",
    "status": "active"
  }
}
```

---

## Worldkeeper - Welt Definition

```json
{
  "world": {
    "id": "muenchen_2045",
    "name": "München 2045",
    "orte": {
      "wohnung_max": {
        "beschreibung": "Kleine 2-Zimmer-Wohnung im 3. OG, Altbau, hohe Decken, schmale Dielen",
        "stockwerk": "3. OG",
        "details": {
          "kueche": "Retro-Küche mit Gasherd, kleinem Tisch, Fenster zum Hof",
          "wohnzimmer": "Sofa, Bücherregal, Panoramafenster, Krimskrams",
          "schlafzimmer": "Bett, Nachttisch, Fenster zum Hof",
          "badezimmer": "Wanne, Waschbecken, kein Fenster"
        },
        "accessed_from": "Treppenhaus (kein Aufzug)"
      },
      "labor": {
        "beschreibung": "Hochmodernes IT-Labor, grelles Licht, Server-Rack",
        "stockwerk": "Keller",
        "details": {
          "arbeitsplatz": "3 Monitore, mechanische Tastatur",
          "lager": "Regale mit Bauteilen",
          "pausenzone": "Kaffeemaschine, Sofa"
        },
        "accessed_from": "Hauptgang"
      }
    },
    "regeln": [
      "Kein Essen im Labor",
      "Besucher müssen sich anmelden",
      "KI-Assistenten sind allgegenwärtig aber nicht sentient"
    ],
    "logik_regeln": [
      "Personen können nicht durch Wände gehen",
      "Treppen brauchen Zeit (2 Stockwerke = ~1 Minute)",
      "Keine Telefonate wenn Handy keinen Empfang hat"
    ],
    "timeline": [
      { "event": "Max kommt in München an", "date": "2045-03-15" },
      { "event": "Labor eröffnet", "date": "2045-04-01" }
    ]
  }
}
```

---

## Tech-Stack

| Komponente | Tech |
|------------|------|
| Backend | FastAPI |
| Frontend | HTMX + TailwindCSS + Alpine.js |
| LLM | LiteLLM |
| Message Queue | File-based JSON |
| Vector DB | Qdrant |
| Story DB | File-based (Markdown/JSON) |

---

## Phase 1: Core System

- [ ] Verzeichnis-Struktur erstellen
- [ ] agent_system.py
- [ ] Base Agent Klasse
- [ ] StoryDB
- [ ] Message Queue
- [ ] LiteLLM Client
- [ ] Model Router
- [ ] Config-System

## Phase 2: Web Panel

- [ ] FastAPI Setup
- [ ] Login/Auth
- [ ] Dashboard
- [ ] Agent Manager (CRUD)
- [ ] Story Planner
- [ ] Character Manager
- [ ] World Editor
- [ ] Szenen-Editor
- [ ] Review Panel
- [ ] Chat
- [ ] File Browser + Editor

## Phase 3: Qdrant Integration

- [ ] Qdrant Client
- [ ] Collection Management
- [ ] Memory speichern/laden

## Phase 4: Agenten

- [ ] Orchestrator
- [ ] Drehbuch-Autor
- [ ] Drehbuch-Ausarbeiter
- [ ] Logik-Prüfer
- [ ] Worldkeeper
- [ ] Detail-Prüfer
- [ ] Character-Manager
- [ ] Stil-Prüfer
- [ ] Deutsch-Prüfer
- [ ] Zeit-Prüfer

## Phase 5: Export

- [ ] Markdown Export
- [ ] PDF Export (später)
- [ ] Epub Export (später)

## Phase 6: Erweiterungen

- [ ] Telegram Adapter
- [ ] Matrix Adapter

---

*Status: In Planung*
*Letzte Änderung: 2026-05-26*
