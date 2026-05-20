# Schachsystem-Anbindung

## Prinzip

Das Schachsystem spricht nicht direkt mit Ollama. Es spricht nur mit dem Router.

Das Schachsystem kennt:
- logische Rollen (`router`, `small`, `large`, `task`, `coach`, `analyst`, `critic`, `vision`, `scribe`, `researcher`)
- Modell-Aliase (`chess-router`, `chess-small`, `chess-large`, `chess-task`, `chess-coach`, `chess-analyst`, `chess-critic`, `chess-vision`, `chess-scribe`, `chess-researcher`)

Es weiß **nicht**, welches echte Modell dahinter steht und ob es lokal oder auf dem Pi läuft.
Rollenverhalten wie Didaktik, Spoilerarmut, Quellenattribution oder vorsichtiger Umgang mit Diagrammen bleibt Aufgabe des aufrufenden Schachsystems bzw. seiner Prompts. Der Router mappt nur Aliase auf Provider-Modelle und Backends.
Alle Schachrollen sollten vom Client so gepromptet werden, dass Nutzerantworten auf Deutsch erfolgen.

## Env-Konfiguration im Schachsystem

```env
LLM_BASE_URL=http://ROUTER_VM_IP:18080/v1
LLM_API_KEY=ollama

LLM_MODEL_ROUTER=chess-router
LLM_MODEL_SMALL=chess-small
LLM_MODEL_LARGE=chess-large
LLM_MODEL_TASK=chess-task
LLM_MODEL_COACH=chess-coach
LLM_MODEL_ANALYST=chess-analyst
LLM_MODEL_CRITIC=chess-critic
LLM_MODEL_VISION=chess-vision
LLM_MODEL_SCRIBE=chess-scribe
LLM_MODEL_RESEARCHER=chess-researcher
```

## Modellzuordnung

| Rolle | Modell-Alias | Provider-Modell | Zweck |
|---|---|---|---|
| router | `chess-router` | `deepseek-v4-flash:cloud` | Aufgabenklasse, Analyseweg |
| small | `chess-small` | `deepseek-v4-flash:cloud` | Klassifikation, Zugbewertung |
| large | `chess-large` | `gemma4:31b-cloud` | Lange Analyse, Kommentierung |
| task | `chess-task` | `deepseek-v4-pro:cloud` | PGN-Kommentare, Zusammenfassungen |
| coach | `chess-coach` | `gemma4:31b-cloud` | Didaktischer Trainingscoach, deutsch, spoilerarm, Nutzerstaerke beachten |
| analyst | `chess-analyst` | `qwen3.5:397b-cloud` | Tiefe Analyse aus Engine-, Maia-, Board-Truth-, PGN- und Trainingskontext |
| critic | `chess-critic` | `deepseek-v4-pro:cloud` | Widersprueche, unbelegte Aussagen und riskante Tool-/Analyseausgaben pruefen |
| vision | `chess-vision` | `gemma4:31b-cloud` | OCR-, Bild- und Diagrammkontext; vorsichtig, keine geratenen FENs |
| scribe | `chess-scribe` | `deepseek-v4-flash:cloud` | Strukturierte deutsche Berichte, PGN-Kommentare, Lernkarten und Konsolentexte |
| researcher | `chess-researcher` | `deepseek-v4-pro:cloud` | Vorhandene Quellen-, Such- und Knowledge-Kontexte mit Attribution verdichten |

Diese Zuordnung lebt **nur im Router** – das Schachsystem fragt einfach `chess-small` und bekommt eine Antwort.

## Empfohlene Policies

| Alias | Empfohlene Policy | Begründung |
|---|---|---|
| `chess-router` | `standard` | Schnelle Klassifikation, max. 300s |
| `chess-small` | `standard` | Schnelle Zugbewertung, max. 300s |
| `chess-large` | `long_running` | Lange Analyse, max. 900s |
| `chess-task` | `standard` | PGN-Kommentare, max. 300s |
| `chess-coach` | `long_running` | Didaktische Ausführung, max. 900s |
| `chess-analyst` | `long_running` | Umfangreiche Analyse, max. 900s |
| `chess-critic` | `standard` | Prüfung auf Konsistenz, max. 300s |
| `chess-vision` | `long_running` | OCR-/Diagramm-Analyse, max. 900s |
| `chess-scribe` | `standard` | Berichtserstellung, max. 300s |
| `chess-researcher` | `standard` | Recherche-Verdichtung, max. 300s |

**Kimi-CLI** verwendet `kimi-cli-default` mit `policy: interactive`
(max. 300s, `fallback_on_5xx: true`), da es als interaktiver Client
schnell antworten und bei Fehlern schnell wechseln muss.

## Router-Konfiguration für Chess

```yaml
models:
  chess-router:
    provider_model: "deepseek-v4-flash:cloud"
    backends: ["vm", "pi"]
    policy: "standard"

  chess-small:
    provider_model: "deepseek-v4-flash:cloud"
    backends: ["vm", "pi"]
    policy: "standard"

  chess-large:
    provider_model: "gemma4:31b-cloud"
    backends: ["vm", "pi"]
    policy: "long_running"

  chess-task:
    provider_model: "deepseek-v4-pro:cloud"
    backends: ["vm", "pi"]
    policy: "standard"

  chess-coach:
    provider_model: "gemma4:31b-cloud"
    backends: ["vm", "pi"]
    policy: "long_running"

  chess-analyst:
    provider_model: "qwen3.5:397b-cloud"
    backends: ["vm", "pi"]
    policy: "long_running"

  chess-critic:
    provider_model: "deepseek-v4-pro:cloud"
    backends: ["vm", "pi"]
    policy: "standard"

  chess-vision:
    provider_model: "gemma4:31b-cloud"
    backends: ["vm", "pi"]
    policy: "long_running"

  chess-scribe:
    provider_model: "deepseek-v4-flash:cloud"
    backends: ["vm", "pi"]
    policy: "standard"

  chess-researcher:
    provider_model: "deepseek-v4-pro:cloud"
    backends: ["vm", "pi"]
    policy: "standard"
```

## Test

```bash
# Direkter Test via curl
curl -s http://ROUTER_VM_IP:18080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-LLM-Client: chess-system" \
  -d '{
    "model": "chess-small",
    "messages": [{"role":"user","content":"Evaluate 1.e4"}]
  }'
```
