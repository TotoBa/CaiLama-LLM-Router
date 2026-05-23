# CaiLama-LLM-Router

<p align="center">
  <img src="https://raw.githubusercontent.com/TotoBa/CaiLama/main/img/logo-big.png" alt="CaiLama Logo" width="600">
</p>

Webseite: <https://cailama.org/>

Ecosystem-Doku:

- Human-Referenz: <https://cailama.org/reference.php>
- LLM-Einstieg: <https://cailama.org/llms.txt>
- LLM-Markdown: <https://cailama.org/ecosystem-reference.md>
- Maschinenlesbar: <https://cailama.org/data/ecosystem.json>

Generic local LLM routing gateway for the CaiLama ecosystem with OpenAI-compatible API, model aliases, backend fallback and JSONL logging.

## Was macht der Router?

Du hast mehrere LLM-Backends (z.B. Ollama lokal, Ollama auf einem RasPi, später OpenRouter). Deine Tools (Kimi CLI, Schachsystem, Skripte) sollen nicht wissen, welches Backend gerade verfügbar ist und welches Modell dort läuft.

Der Router schafft eine Abstraktionsschicht:

```
Dein Tool -> "chess-small" -> CaiLama-LLM-Router -> Backend "vm" (gemma4:31b-cloud)
                                falls down -> Backend "pi" (gemma4:31b-cloud)
```

## Features

- **OpenAI-compatible API** – `/v1/chat/completions`, `/v1/models`, `/health`
- **Modell-Aliase** – dein Tool fragt `chess-small`, der Router weiß, welches Provider-Modell gemeint ist
- **Backend-Fallback** – bei Rate-Limits, Verbindungsfehlern oder Crashs automatisch nächstes Backend
- **Optionale Verteilung** – `round_robin` verteilt Requests ueber alle verfuegbaren Backends
- **Streaming** – SSE-Stream wird transparent durchgereicht (wichtig für Kimi CLI)
- **JSONL-Logging** – jede Anfrage wird protokolliert, ohne Prompt-Inhalte (standardmäßig)
- **Keine Secrets im Repo** – echte Configs und API-Keys werden nie eingecheckt

---

## Schnellinstallation

```bash
git clone git@github.com:TotoBa/CaiLama-LLM-Router.git
cd CaiLama-LLM-Router
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Erste Schritte

### 1. Konfiguration anlegen

```bash
cp configs/router.example.yaml configs/router.local.yaml
cp .env.example .env
```

Bearbeite `configs/router.local.yaml` und passe `backends` an deine Hosts an.

### 2. Router starten

```bash
llm-router serve --config configs/router.local.yaml
```

### 3. Testen

```bash
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/v1/models
```

### 4. Smoke-Test

```bash
llm-router smoke-test --model default --prompt "Antworte nur OK."
```

Für einen dauerhaften Router-VM + Pi-Ollama Rollout siehe:

- [VM + Pi Rollout](docs/rollout-vm-pi.md)
- [systemd-Deployment](docs/deployment-systemd.md)

---

## CLI-Befehle

```bash
llm-router --help                       # Alle Befehle anzeigen
llm-router serve --config ...           # Router starten
llm-router check-config --config ...    # Config validieren
llm-router list-models --config ...     # Modell-Aliase auflisten
llm-router test-backends --config ...   # Backends testen
llm-router usage --metrics-url URL      # Aggregierte Metriken (Requests, Fallbacks, Tokens, Thinking) anzeigen
llm-router benchmark-export --metrics-url URL # Secretfreie Benchmark-JSON mit Git-Ref, Rates und Tokenwerten
```

---

## Für Kimi CLI

Kimi spricht nicht mehr direkt mit Ollama, sondern mit dem Router.

Füge in `~/.kimi/config.toml` ein:

```toml
default_model = "kimi-cli-default"

[providers.local-llm-router]
type = "openai_legacy"
base_url = "http://127.0.0.1:18080/v1"
api_key = "ollama"

[models.kimi-cli-default]
provider = "local-llm-router"
model = "kimi-cli-default"
max_context_size = 131072
capabilities = ["thinking"]
```

Dann: `kimi --model kimi-cli-default`

[Mehr Details in docs/kimi-cli.md](docs/kimi-cli.md)

---

## Für das Schachsystem

Im Schachsystem:

```env
LLM_BASE_URL=http://127.0.0.1:18080/v1
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

Das Schachsystem kennt nur logische Rollen (`small`, `large`, `task`, `coach`, `analyst`, `critic`, `vision`, `scribe`, `researcher`). Der Router kümmert sich um das echte Modell und das Backend. Rollenverhalten wird vom Schachsystem gepromptet; der Router erzwingt keine Schachlogik.

[Mehr Details in docs/chess-system.md](docs/chess-system.md)

---

## Beispiel-Konfiguration

```yaml
server:
  host: "127.0.0.1"
  port: 18080

backends:
  local:
    type: "openai_compatible"
    base_url: "http://127.0.0.1:11434/v1"
    api_key_env: "OLLAMA_LOCAL_API_KEY"
    priority: 10
    enabled: true

  pi:
    type: "openai_compatible"
    base_url: "http://pi-ollama.example.local:11434/v1"
    api_key_env: "OLLAMA_PI_API_KEY"
    priority: 20
    enabled: true

models:
  default:
    provider_model: "deepseek-v4-flash:cloud"
    backends: ["local", "pi"]
    policy: "standard"

  chess-small:
    provider_model: "gemma4:31b-cloud"
    backends: ["local", "pi"]
    policy: "long_running"
    routing_strategy: "round_robin"

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

limit_detection:
  status_codes: [402, 403, 429]
  body_markers: ["rate limit", "quota", "limit"]

logging:
  level: "INFO"
  jsonl_path: "logs/llm-router.jsonl"
  log_request_body: false
  log_response_body: false
  log_prompt_chars: false
  log_headers: false
```

Für langsame lokale LLMs kann `runtime.request_timeout_seconds: null` gesetzt bleiben. Dann begrenzt der Router nur den Verbindungsaufbau, bricht eine laufende Antwort aber nicht wegen eines Read-Timeouts ab.

Wenn alle sofort nutzbaren Backends mit Fehlern antworten, gibt der Router standardmaessig den letzten Backend-Fehler unveraendert an den Client zurueck. Das verhindert, dass Clients wie Kimi auf einen generischen Router-Fehler warten oder unklar weiterlaufen. Pro Policy kann das mit `return_last_error_on_exhausted_backends: false` deaktiviert werden.

Ein Modell kann gezielt nur auf einem Backend angeboten werden, z.B. `backends: ["vm"]`. Fuer knappe Ollama-Hosts setzen die systemd-Beispiele `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1` und `OLLAMA_MAX_QUEUE=2`.

---

## Sicherheit

- Router bindet standardmäßig an `127.0.0.1`
- API-Keys werden nur via Env-Variablen referenziert (`api_key_env`)
- Keine Secrets im Code, keine Secrets in Logs
- Prompts und Responses werden standardmäßig nicht geloggt

[Mehr in docs/security.md](docs/security.md)

---

## Troubleshooting

| Problem | Lösung |
|---|---|
| Config-Fehler | `llm-router check-config --config configs/router.local.yaml` |
| Backend nicht erreichbar | `llm-router test-backends --config configs/router.local.yaml` |
| Modell unbekannt | Alias in Config prüfen oder `unknown_model_strategy: passthrough` |
| Logs lesen | `tail -f logs/llm-router.jsonl \| jq .` |
| Kimi CLI antwortet nicht | Router läuft? Modellname in Kimi Config = Alias im Router? |

---

## Dokumentation

- [Architektur](docs/architecture.md) – Systemdesign
- [Konfiguration](docs/configuration.md) – Alle Config-Optionen
- [Backends](docs/backends.md) – Ollama, RasPi, Netzwerk
- [Kimi CLI](docs/kimi-cli.md) – Anbindung Kimi
- [Schachsystem](docs/chess-system.md) – Anbindung Schachsystem
- [Fallback](docs/fallback.md) – Fehlerbehandlung
- [Logging](docs/logging.md) – Logs und Datenschutz
- [systemd-Deployment](docs/deployment-systemd.md) – Autostart
- [VM + Pi Rollout](docs/rollout-vm-pi.md) – Beispielhafter Betrieb auf zwei Hosts
- [Security](docs/security.md) – Best Practices

---

## Lizenz

AGPL-3.0-or-later
