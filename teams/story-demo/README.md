# Story-Demo-Team

Vorkonfiguriertes Team für **Story-Workflows** mit file-basierter Agent-Kommunikation.

## Agents (9)

| Agent | Rolle | Aufgabe |
|-------|--------|---------|
| `orchestrator` | orchestrator | Story-Plan → `drehbuch-autor` |
| `drehbuch-autor` | story_writer | Szene schreiben → **alle 7 Prüfer** (parallel Inbox) |
| `logik-pruefer` | logik-pruefer | Logik-Check |
| `worldkeeper` | worldkeeper | World-Konsistenz |
| `character-manager` | character-manager | Charaktere |
| `stil-pruefer` | stil-pruefer | Stil |
| `deutsch-pruefer` | deutsch-pruefer | Grammatik |
| `zeit-pruefer` | zeit-pruefer | Tempus |
| `detail-pruefer` | detail-pruefer | Details |

## Schnellstart

```bash
bot team init story-demo
bot story init --team story-demo --title "Demo-Roman"
bot run --team story-demo

# Aufgabe an Orchestrator
bot msg send --team story-demo --from orchestrator --to orchestrator \
  --subject "Szene 1" --content "Max betritt das Labor in München 2045."

bot run --team story-demo --once
```

Web-Panel: `/teams/story-demo/story` (Plot, Graph, Memory, paralleles Review).

## Daten

- Story-Dateien: `data/story-demo/story/`
- Inboxen: `teams/story-demo/agents/<id>/inbox/`
- Prüfer-Config: `teams/story-demo/story_review.json`
