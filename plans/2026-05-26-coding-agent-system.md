# Planung: Coding Agent System

## Vision

Ein distributed multi-agent Coding-System. Eine Code-Basis, N Agents über JSON-Configs. Web Panel mit Agent Manager, File Editor, Qdrant-Config. Alles konfigurierbar über die Web-Oberfläche.

---

## Architektur

### Eine Code-Basis, N Agents

```
/home/worker-test-llm/coder/
├── agent_system.py              # EIN mal Python Code
├── agents/                      # Agents werden via JSON definiert
│   ├── orchestrator/
│   │   ├── agent.json           # Port 8765, LLM, capabilities...
│   │   ├── memory/
│   │   └── inbox/
│   ├── coder/
│   │   ├── agent.json           # Port 8766
│   │   └── inbox/
│   └── [beliebig viele weitere agents...]
├── shared/
│   └── lib/
│       ├── base_agent.py        # Alle Agents erben davon
│       ├── model_router.py
│       ├── litellm_client.py
│       └── qdrant_client.py
├── config/
│   ├── system.json              # Global config
│   └── task_models.json        # Model-Routing
└── data/
    └── [projekte...]
```

**Start:**
```bash
python agent_system.py --type coder
```
→ Liest alle `agent.json` in `agents/`, startet für jeden einen Port + Web Panel.

---

## Multi-Orchestrator (je Projekt ein Orchestrator)

```
/coder/
├── agents/
│   ├── orchestrator-projekt-a/ (Port 8765)
│   │   └── subagents: coder-a, tester-a, doku-a
│   └── orchestrator-projekt-b/ (Port 8780)
│       └── subagents: coder-b, tester-b, doku-b
```

Jeder Orchestrator verwaltet seine eigenen Subagents. Getrennte Ports, getrennte Inboxes, getrennte Daten.

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
        "inbox_path": "/home/worker-test-llm/coder/{agent}/inbox/"
      },
      "multi_machine": {
        "enabled": true,
        "agents": [
          { "name": "coder", "host": "10.95.60.219", "ssh_key": "~/.ssh/id_ed25519" }
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

## Web Panel (pro Agent)

### Ports (konfigurierbar)

| Agent | Port | URL |
|-------|------|-----|
| Orchestrator | 8765 | http://10.95.60.219:8765 |
| Coder | 8766 | http://10.95.60.219:8766 |
| Tester | 8767 | http://10.95.60.219:8767 |
| Doku | 8768 | http://10.95.60.219:8768 |
| Admin | 8769 | http://10.95.60.219:8769 |

### Web Panel Screens

**1. Dashboard**
- Alle Agents (running/stopped)
- Aktive Tasks
- Letzte Activity
- System-Status (CPU, Memory, LLM-Verbindung)

**2. Agent Manager**
- Liste aller Agents
- [Neuer Agent erstellen]
- Subagents hierarchisch unter Orchestrator
- Agent bearbeiten/löschen/starten/stoppen

**3. Task Board**
- ToDo / In Progress / Done
- Tasks erstellen
- Tasks an Agents zuweisen

**4. Chat**
- Mit allen Agents kommunizieren
- Nachrichten an spezifische Agents

**8. File Browser + Editor**
- Verzeichnisstruktur durchsuchen
- Dateien lesen/schreiben
- Syntax Highlighting (Python, JS, Markdown...)
- Suche in Dateien

**9. Projekt erstellen**
- [Neues Projekt] Button im Dashboard
- Erstellt automatisch die Struktur:
  ```
  projekt/
  ├── AGENTS.md              # Projekt-Context
  ├── features/
  │   └── INDEX.md           # Feature-Tracking
  ├── www/
  │   └── www.example.com/
  │       └── public/
  ├── api/
  │   └── api.example.com/
  │       └── public/
  ├── docs/
  │   └── PRD.md
  └── .codex/
      └── prompts/
  ```
- AGENTS.md wird mit User-Input gefüllt: Tech-Stack, Domains, Deployment
- Optional: Skeleton von Git klonen

**10. Qdrant Config**
- Global Qdrant oder per Orchestrator
- Collection erstellen/auswählen
- LLM für Vector DB zuordnen
- Memory durchsuchen

**7. Git Config**
- Remote: Github oder Gitea
- URL, Token eintragen
- Repo klonen/pushen

---

## Agent erstellen (im Web Panel)

```
Neuer Agent
├── Name: [___________]
├── Port: [8765]          # automatisch nächster freier
├── Master Agent: [Orchestrator]
├── LLM Model: [Dropdown aller verfügbaren Modelle]
│   └── Verfügbare: qwen3-14b-tools-thinking, qwen2.5-coder-14b-tools-insert, etc.
├── Task Category: [coding|debugging|testing|...]
├── Capabilities: 
│   ├── [x] code_generation
│   ├── [x] git
│   ├── [ ] docker
│   ├── [ ] database
│   └── ...
├── Contact Other Agents: [ ] orchestrator [x] tester [x] doku
├── Server Access:
│   └── Host: [10.95.60.219] User: [worker-test-llm]
└── [Erstellen] [Abbrechen]
```

→ Erstellt:
- `/coder/agents/[name]/agent.json`
- `/coder/agents/[name]/inbox/`
- `/coder/agents/[name]/memory/`
- Startet auf konfiguriertem Port

---

## Subagents unter Orchestrator

```
Orchestrator (Master - Port 8765)
├── Subagents:
│   ├── coder (Port 8766)
│   ├── tester (Port 8767)
│   ├── doku (Port 8768)
│   └── admin (Port 8769)
│
└── [B] Orchestrator auf Port 8780 (anderes Projekt)
    └── Subagents:
        ├── coder-b (Port 8781)
        └── tester-b (Port 8782)
```

Jeder Orchestrator verwaltet seine eigenen Subagents. Subagents können nur mit ihrem Master und anderen Subagents desselben Masters kommunizieren (konfigurierbar).

---

## Config (config/system.json)

```json
{
  "system": {
    "name": "coding-agents",
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
    "database": {
      "dev": "sqlite",
      "docker_mariadb": {
        "image": "mariadb:latest",
        "port": 3307,
        "root_password": "dev_root"
      },
      "mariadb": {
        "host": "10.95.60.51",
        "port": 3306,
        "user": "project_user",
        "password": "project_pass",
        "database": "project_db"
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
        "coder-memory": {
          "description": "Memory für alle Coder Agents",
          "llm": "ollama/qwen3-14b-tools-thinking"
        }
      }
    }
  },
  "git": {
    "remote": {
      "type": null,
      "url": null,
      "token": null
    }
  }
}
```

---

## Qdrant Konfiguration

### Global (config/system.json)

```json
{
  "qdrant": {
    "global": {
      "enabled": true,
      "host": "http://10.95.60.51:6333",
      "collections": {
        "coder-memory": {
          "description": "Memory für alle Coder Agents",
          "llm": "ollama/qwen3-14b-tools-thinking"
        },
        "projekt-x-memory": {
          "description": "Memory für Projekt X",
          "llm": "ollama/qwen2.5-coder-14b-tools-insert"
        }
      }
    }
  }
}
```

### Per Orchestrator (agent.json)

```json
{
  "agent": {
    "name": "orchestrator",
    "qdrant": {
      "use_global": true,
      "collection": "coder-memory"
    }
  }
}
```

oder individuell:

```json
{
  "agent": {
    "name": "orchestrator",
    "qdrant": {
      "use_global": false,
      "host": "http://10.95.60.51:6334",
      "collection": "mein-projekt-memory",
      "llm": "ollama/qwen3-14b-tools-thinking"
    }
  }
}
```

### Im Web Panel

```
Qdrant Einstellungen
├── Global:
│   ├── Host: [http://10.95.60.51:6333]
│   └── Collections: [coder-memory] [projekt-x-memory]
│
├── Dieser Orchestrator:
│   ├── Use Global: [x]
│   ├── Collection: [coder-memory dropdown]
│   └── LLM: [qwen3-14b-tools-thinking]
│
└── [Speichern]
```

---

## Task-basiertes Model-Routing

```json
{
  "task_models": {
    "planning": {
      "default": "ollama/qwen3-14b-tools-thinking",
      "alternatives": ["ollama/llama3.1-8b-tools"]
    },
    "coding": {
      "default": "ollama/qwen2.5-coder-14b-tools-insert",
      "alternatives": ["ollama/qwen3-14b-tools-thinking"]
    },
    "debugging": {
      "default": "ollama/qwen3-14b-tools-thinking",
      "alternatives": ["ollama/qwen2.5-14b-tools"]
    },
    "testing": {
      "default": "ollama/qwen2.5-14b-tools",
      "alternatives": ["ollama/mistral-nemo-12b-tools"]
    },
    "documentation": {
      "default": "ollama/qwen2.5-7b-instruct-uncensored",
      "alternatives": ["ollama/qwen2.5-abliterate"]
    }
  }
}
```

### Message mit Model Override

```json
{
  "from": "orchestrator",
  "to": "coder",
  "task_category": "coding",
  "model_override": "ollama/devstral-24b-vision-tools",
  "subject": "Implementiere API"
}
```

→ Nutzt `devstral-24b` statt Default `qwen2.5-coder-14b-tools-insert`

---
### Orchestrator - Autonomer Manager

**Der User ist der Designer/Architekt** — er weiß was er will (Goals, Design, Features), aber nicht wie man es technisch umsetzt.

**Der Orchestrator trifft alle technischen Entscheidungen automatisch:**

```python
# User sagt nur:
goal = {
  "type": "forum",
  "features": ["login", "profile", "posts", "comments"],
  "domains": ["www.domain.de", "api.domain.de"],
  "tech_preference": "php"  # oder "python" oder "egal"
}

# Orchestrator plant selbst:
plan = {
  "framework": "Laravel",  # weil PHP + Forum = Laravel
  "database": "MariaDB",
  "domains": {
    "www": { "target": "server-web", "path": "/var/www/mein-forum" },
    "api": { "target": "server-api", "path": "/opt/api" }
  },
  "architecture": "monolith"  # oder "microservices" wenn komplex
}
```

**Der Orchestrator fragt nur wenn's kritisch ist:**
- "Soll api.domain.de auf einem anderen Server sein?"
- "Design-Variante A oder B für das Frontend?"
- "Welches Payment-System: Stripe oder PayPal?"

**Wenn User "keine Ahnung" sagt → Orchestrator entscheidet mit Best-Practice**

---

### Multi-Domain Projekt-Setup

```python
# config/projects/mein-forum.json
{
  "project": {
    "name": "mein-forum",
    "type": "php",  # php | python | mixed
    "domains": [
      {
        "subdomain": "www",
        "target": "server-web-1",
        "port": 80,
        "path": "/var/www/mein-forum",
        "service": "frontend"
      },
      {
        "subdomain": "api",
        "target": "server-web-1",  # oder anderer server
        "port": 8080,
        "path": "/opt/api",
        "service": "api"
      },
      {
        "subdomain": "admin",
        "target": "server-web-1",
        "port": 8081,
        "path": "/var/www/admin",
        "service": "admin"
      }
    ],
    "reverse_proxy": "nginx",  # nginx | caddy
    "database": {
      "type": "mariadb",
      "host": "10.95.60.51",
      "port": 3306
    }
  }
}
```

**Architecture:**

```
                        User
                          |
                    nginx reverse proxy
                    (server-web-1:80)
                          |
            +-------------+-------------+
            |             |             |
         /www/*       /api/*       /admin/*
            |             |             |
            v             v             v
      Frontend      API Backend     Admin Panel
    (Laravel/PHP)  (PHP/FastAPI)   (Laravel/PHP)
            |             |             |
            +-------------+-------------+
                          |
                        MariaDB
                    (server-db:3306)
```

---

## Agent JSON Schema

```json
{
  "agent": {
    "name": "coder",
    "role": "Coder Agent",
    "enabled": true,
    "master": "orchestrator",
    "llm": {
      "provider": "litellm",
      "model": "ollama/qwen2.5-coder-14b-tools-insert",
      "api_base": "http://10.95.60.51:11434",
      "fallback": "ollama/qwen3-14b-tools-thinking"
    },
    "web": {
      "enabled": true,
      "port": 8766
    },
    "task_category": "coding",
    "capabilities": [
      "code_generation",
      "refactoring",
      "git",
      "docker",
      "nginx_config",
      "multi_domain_setup"
    ],
    "autonomous": true,  # Agent trifft eigene Entscheidungen wenn nicht anders gesagt
    "ask_before": ["database_schema", "framework_choice", "deployment_strategy"],
    "tools": ["terminal", "file", "browser", "git"],
    "contact_other_agents": ["orchestrator", "tester", "doku"],
    "server_access": [
      { "host": "10.95.60.219", "user": "worker-test-llm" }
    ],
    "qdrant": {
      "use_global": true
    },
    "auto_install": true,
    "sudo_password": "<nur über Secret-Store / Umgebung, nie im Klartext in Git>"
  }
}
```

---

## Database pro Projekt

```
/coder/data/
├── projekt-a/
│   └── db.sqlite  (oder Docker MariaDB)
├── projekt-b/
│   └── db.sqlite
└── projekt-c/
    └── db.sqlite
```

Jedes Projekt hat seine eigene DB. Konfigurierbar in Projekt-Settings.

---

## Message Queue (File-based)

```
outbox/
├── to-orchestrator-001.json
├── to-coder-001.json
└── ...

inbox/orchestrator/
├── msg-001.json
└── processed/

inbox/coder/
├── msg-001.json
└── processed/
```

### Message Format

```json
{
  "id": "msg-001",
  "from": "tester",
  "to": "coder",
  "type": "fix_required",
  "task_category": "debugging",
  "model_override": null,
  "priority": "high",
  "subject": "Login funktioniert nicht",
  "content": "Fehler: Cannot connect to DB...",
  "attachments": ["/coder/data/projekt/error.log"],
  "timestamp": "2026-05-26T22:45:00Z",
  "status": "pending",
  "retry_count": 0,
  "max_retries": 3
}
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

## Agent Loop (permanent, polling)

```python
while True:
    messages = read_inbox()
    for msg in messages:
        # Retry Logic
        if msg.get("retry_count", 0) >= msg.get("max_retries", 3):
            notify_user(f"Message {msg['id']} failed after {msg.get('max_retries', 3)} retries")
            continue
        
        # Model-Routing
        task = msg.get("task_category", "planning")
        model = router.get_model(task, msg.get("model_override"))
        
        try:
            result = llm.complete(model=model, messages=build_messages(msg))
            process_result(result, msg)
        except Exception as e:
            msg["retry_count"] += 1
            save_to_inbox(msg)  # für nächsten loop
            sleep(exponential_backoff(msg["retry_count"]))
    
    # Permanent Review wenn keine Tasks
    # - Code Quality
    # - Performance
    # - Todo-Update
    
    sleep(polling_interval)
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
| ORM | SQLAlchemy |
| DB Dev | SQLite oder Docker MariaDB |
| Migrations | Alembic |
| Git | GitPython |
| Testing | pytest + Playwright |

---

## Phase 1: Core System

- [ ] Verzeichnis-Struktur erstellen
- [ ] agent_system.py (startet alle agents)
- [ ] Base Agent Klasse
- [ ] Message Queue
- [ ] LiteLLM Client
- [ ] Model Router
- [ ] Config-System (system.json, task_models.json)

## Phase 2: Web Panel

- [ ] FastAPI Setup
- [ ] Login/Auth
- [ ] Dashboard
- [ ] Agent Manager (CRUD)
- [ ] Task Board
- [ ] Chat Interface
- [ ] File Browser + Editor

## Phase 3: Qdrant Integration

- [ ] Qdrant Client
- [ ] Collection Management
- [ ] Memory speichern/laden
- [ ] Config UI im Web Panel

## Phase 4: Agenten

- [ ] Orchestrator
- [ ] Coder
- [ ] Tester
- [ ] Doku
- [ ] Admin

## Phase 5: Features

- [ ] Git Integration (Github/Gitea)
- [ ] Docker DB Setup
- [ ] Self-Debugging Loop
- [ ] Permanent Review Loop
- [ ] Retry + Error Handling

## Phase 6: Erweiterungen

- [ ] Telegram Adapter
- [ ] Matrix Adapter

---

*Status: In Planung*
*Letzte Änderung: 2026-05-26*
