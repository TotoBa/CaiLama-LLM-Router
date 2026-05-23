# Konfiguration

## Überblick

Der Router wird über eine oder mehrere YAML-Dateien konfiguriert. Die Konfiguration ist in Bereiche aufgeteilt:

```yaml
server:      # Host/Port
runtime:     # Timeouts, Reload
backends:    # Liste der LLM-Backends
models:      # Logische Modell-Aliase
policies:    # Verhaltensregeln
limit_detection:   # Fallback bei Rate-Limits
logging:     # Log-Level und Dateipfade
```

## Schnellstart

```bash
# Kopieren und anpassen
cp configs/router.example.yaml configs/router.local.yaml
nano configs/router.local.yaml
```

`configs/router.local.yaml` ist in `.gitignore` – eure echte Config landet nie im Repository.

## Runtime

```yaml
runtime:
  request_timeout_seconds: null
  connect_timeout_seconds: 10
  reload_config_on_request: false
  unknown_model_strategy: "error"
```

- `request_timeout_seconds: null` oder `0` bedeutet: kein Timeout fuer einen laufenden Backend-Request. Das ist fuer lokale oder langsame LLMs sinnvoll, weil der Router nicht abbrechen soll, solange das Backend die Verbindung haelt.
- `connect_timeout_seconds` begrenzt nur den Verbindungsaufbau. Damit werden tote Hosts weiter schnell erkannt und Fallback kann greifen.
- Ein positiver Wert fuer `request_timeout_seconds` setzt wieder einen Read/Write/Pool-Timeout fuer Backend-Requests.
- `reload_config_on_request: true` laedt die YAML-Datei vor jedem Request neu,
  wenn der Router ueber `LLM_ROUTER_CONFIG` oder `llm-router serve --config`
  aus einer Datei gestartet wurde. Das aktualisiert Routing, Aliase und
  Policies ohne Prozessneustart; bestehende HTTP-Client-Timeouts werden erst
  beim Neustart neu aufgebaut.
- `unknown_model_strategy` definiert das Verhalten, wenn ein Client ein Modell anfragt, das in `models` nicht definiert ist. `error` (Standard) gibt 400 zurück. `passthrough` leitet den Request an das erste verfügbare Backend durch; der Modell-Name wird unverändert an das Backend weitergereicht. Das ist nützlich, wenn CaiLama dynamische Rollen oder neue Modell-Namen verwendet, die noch nicht hart im Router konfiguriert sind.

## Server

```yaml
server:
  host: "127.0.0.1"   # Oder "0.0.0.0" für alle Interfaces
  port: 18080
```

## Backends

```yaml
backends:
  local:
    type: "openai_compatible"
    base_url: "http://127.0.0.1:11434/v1"
    endpoint_path: "/chat/completions"   # Default, kann weggelassen werden
    priority: 10        # Niedriegere Zahl = höhere Priorität
    enabled: true

  image-gen:
    type: "openai_compatible"
    base_url: "https://api.example-provider.com"
    endpoint_path: "/v1/images/generations"
    priority: 20
    enabled: true
```

- `base_url` zeigt auf die OpenAI-kompatible API, bei Ollama also mit `/v1`
- `endpoint_path` ist optional; Standard ist `/chat/completions`. Spezialisierte
  Backends (Bildgenerierung, Embeddings) koennen hier abweichende Pfade setzen.
- `api_key_env` ist optional; falls gesetzt, enthält es den Namen der Env-Variablen, nicht den Key selbst
- `priority` sortiert: niedrigere Zahl = höhere Priorität
- `enabled: false` deaktiviert das Backend komplett

## Modelle (Aliases)

```yaml
models:
  chess-small:
    provider_model: "gemma4:31b-cloud"
    backends: ["local", "pi"]
    policy: "long_running"
    routing_strategy: "round_robin"

  chess-large:
    provider_model: "kimi-k2.6:cloud"
    backends: ["local", "pi"]
    policy: "long_running"

  chess-task:
    provider_model: "kimi-k2.6:cloud"
    backends: ["local", "pi"]
    policy: "long_running"

  chess-analysis:
    provider_model: "fallback-model"
    backend_models:
      local: "qwen2.5:14b"
      pi: "qwen2.5:7b"
    backends: ["local", "pi"]
    policy: "standard"
```

- **Logisches Modell** (`chess-small`) ist das, was der Client anfragt
- **Provider-Modell** (`gemma4:31b-cloud`) ist das, was das Backend versteht
- **Backends**: Reihenfolge ist Fallback-Reihenfolge. Fehlt sie, werden alle `enabled` Backends nach `priority` sortiert.
- Provider-Modelle muessen auf jedem Backend verfuegbar sein, das in `backends` genannt ist
- `backend_models` ueberschreibt den Provider-Modellnamen je Backend. Das ist
  fuer heterogene Hosts sinnvoll, wenn derselbe Alias auf der VM und auf einem
  kleineren Host unterschiedliche Modellnamen nutzen soll.
- Soll ein Modell nur ueber einen Host verfuegbar sein, wird nur dieser Backend-Name gesetzt, z.B. `backends: ["vm"]`.
- Fachliche Rollen wie `chess-coach` oder `chess-vision` sind normale Alias-Namen. Der Router injiziert keine Rollenprompts; Verhalten steuert der aufrufende Client.

## Verteilung

Standardmaessig nutzt der Router `routing_strategy: "priority"`: der erste verfuegbare Backend-Eintrag wird zuerst versucht, danach kommt Fallback.

Optional kann ein Modell auf alle verfuegbaren Backends verteilt werden:

```yaml
models:
  default:
    provider_model: "deepseek-v4-flash:cloud"
    backends: ["vm", "pi"]
    policy: "standard"
    routing_strategy: "round_robin"
```

`round_robin` rotiert den ersten Versuch pro Modellalias ueber alle nicht deaktivierten und nicht im Cooldown befindlichen Backends. Wenn der gewaehlte Host fehlschlaegt, wird im selben Request auf ein anderes Backend aus der Liste ausgewichen.

## Policies

Definiert, bei welchen Fehlern Fallback passiert und wie Retry/Timeout gehandhabt werden:

```yaml
policies:
  standard:
    max_attempts_per_backend: 2
    max_backend_failures_before_cooldown: 2
    backend_cooldown_seconds: 300
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: true
    fallback_on_4xx: false
    return_last_error_on_exhausted_backends: true
    timeout_seconds: 300
```

| Feld | Beschreibung |
|---|---|
| `max_attempts_per_backend` | Wie oft dasselbe Backend bei Verbindungs- oder Timeoutfehlern innerhalb eines Requests versucht wird |
| `max_backend_failures_before_cooldown` | Nach wie vielen fehlgeschlagenen Backend-Versuchen ein Backend temporaer uebersprungen wird |
| `backend_cooldown_seconds` | Wie lange ein Backend nach Erreichen der Fehlerschwelle uebersprungen wird |
| `retry_on_connection_error` | Gleiches Backend nochmal versuchen bei Verbindungsfehler |
| `fallback_on_limit` | Fallback bei 429 / Quota / Limit |
| `fallback_on_5xx` | Fallback bei Serverfehlern |
| `fallback_on_4xx` | Fallback bei Client-Fehlern (rarely true) |
| `return_last_error_on_exhausted_backends` | Wenn kein weiteres Backend sofort versucht werden kann, den letzten Backend-Fehler mit Status und Body an den Client zurueckgeben |
| `timeout_seconds` | Reserviert fuer policy-spezifische Timeouts; aktuell steuert `runtime.request_timeout_seconds` den HTTP-Client-Timeout |

## Limit Detection

```yaml
limit_detection:
  status_codes: [402, 403, 429]
  body_markers:
    - "rate limit"
    - "quota"
    - "insufficient quota"
```

## Logging

```yaml
logging:
  level: "INFO"
  jsonl_path: "logs/llm-router.jsonl"
  log_request_body: false
  log_response_body: false
  log_prompt_chars: false
  log_headers: false
```

Hinweis: Standardmäßig werden keine Prompts oder Antworten geloggt. Für Debugging lokal freischaltbar.

## Metrics

`GET /metrics` liefert standardmaessig privacy-safe JSON. Fuer Prometheus kann
das Textformat explizit angefordert werden:

```bash
curl -H 'Accept: text/plain' http://127.0.0.1:18080/metrics
curl http://127.0.0.1:18080/metrics?format=prometheus
```

Die Metriken enthalten Zaehler fuer Requests, Fehler, Fallbacks, Aliase,
Backends, Cooldowns und Limit-Erkennung, aber keine Prompt-, Response- oder
Header-Inhalte.

Seit Version 0.1.0 aggregiert der Router auch privacy-safe Token-Usage aus
OpenAI-kompatiblen Backend-Antworten:

- `usage.prompt_tokens` – summierte Prompt-Tokens aller erfolgreicher Requests
- `usage.completion_tokens` – summierte Completion-Tokens aller erfolgreicher Anfragen
- `usage.output_tokens` – Alias fuer Completion-/Output-Tokens, passend fuer
  Modellrollen-Benchmarks
- `usage.reasoning_tokens` – summierte Reasoning-/Thinking-Tokens, wenn der
  Backend-Provider diese in `usage`, `completion_tokens_details` oder
  `output_tokens_details` liefert
- `usage.thinking_tokens` – Alias fuer Reasoning-/Thinking-Tokens, passend fuer
  Website-Feedback und Benchmark-Tabellen
- `usage.total_tokens` – Gesamtsumme

Im Prometheus-Textformat erscheinen diese als:

- `llm_router_usage_prompt_tokens_total`
- `llm_router_usage_completion_tokens_total`
- `llm_router_usage_output_tokens_total`
- `llm_router_usage_reasoning_tokens_total`
- `llm_router_usage_thinking_tokens_total`
- `llm_router_usage_total_tokens_total`

Fehlerhafte Anfragen (Backend-Fehler, Limits, Timeouts) erhoehen keine
Usage-Zaehler.

## Env-Variablen

```bash
OLLAMA_LOCAL_API_KEY=ollama         # für lokale Ollama
OLLAMA_PI_API_KEY=ollama            # für Pi-Ollama
LLM_ROUTER_CONFIG=configs/router.local.yaml
```

Erstelle `.env` im Projekt-Root – es wird nicht eingecheckt.

Ollama ignoriert den Wert eines Bearer-Tokens normalerweise. Fuer reine Ollama-Backends kann `api_key_env` daher weggelassen werden; manche OpenAI-Clients erwarten trotzdem einen API-Key-Wert in ihrer eigenen Konfiguration.
