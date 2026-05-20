# Historischer Plan: CaiLama-LLM-Router initialisieren

> Archivhinweis: Diese Datei dokumentiert den Initialplan vor der
> Umbenennung. Der aktuelle Repository-Name ist
> `TotoBa/CaiLama-LLM-Router`; alte Bezeichnungen wie `TotoBa/LLM-Router`
> oder `LLM-Router/` sind in diesem Dokument historische Referenzen.

Status: Der ursprüngliche Ziel-Repository-Check bezog sich auf den alten Namen
`TotoBa/LLM-Router`.

Der Router soll als **eigenständiges, generisches LLM-Gateway** gebaut werden. Er darf keine fest verdrahteten Schach-Spezialfälle, keine Credentials und keine lokalen IPs im Code enthalten. Kimi-cli, das Schachsystem und später weitere Tools sprechen nur noch diesen Router an. Die konkrete lokale Umgebung wird über nicht eingecheckte Konfigurationsdateien gesteuert.

Kimi Code CLI kann Provider und Modelle über `~/.kimi/config.toml` konfigurieren; für OpenAI-kompatible Anbieter ist `openai_legacy` vorgesehen. Kimi speichert Konfigurationen in `~/.kimi/config.toml` und unterstützt Modell-Capabilities wie `thinking`. ([Kimi][1]) Ollama bietet OpenAI-kompatible Endpunkte wie `/v1/chat/completions`; der API-Key ist bei lokaler Ollama-Nutzung zwar erforderlich, wird aber ignoriert. ([Ollama Dokumentation][2])

---

## 1. Zielarchitektur

```text
kimi-cli
   \
    \
     -> LLM-Router -> Backend 1: lokales Ollama, Account A
    /               -> Backend 2: Raspberry Pi Ollama, Account B
   /                -> später: OpenAI, Kimi, OpenRouter, Anthropic, lokale Spezialserver
Schachsystem
```

Der Router ist der einzige stabile LLM-Endpunkt für lokale Tools:

```text
http://127.0.0.1:18080/v1
```

Kimi-cli und Schachsystem verwenden also denselben OpenAI-kompatiblen Base-URL:

```text
http://127.0.0.1:18080/v1
```

Der Router entscheidet anhand der Konfiguration:

```text
logisches Modell       echtes Backend-Modell       Backend-Reihenfolge
---------------------------------------------------------------------
kimi-cli-default       kimi-k2.5:cloud             local -> pi
chess-router           gemma4:e4b                  local -> pi
chess-small            gemma4:e4b                  local -> pi
chess-large            gemma4:26b                  local -> pi
chess-task             kimi-k2.5:cloud             local -> pi
```

Wichtig: Diese Namen sind nur Beispielkonfigurationen. Der Router-Code kennt keine Schachlogik. `chess-small`, `chess-large` usw. sind nur frei definierbare Modell-Aliase in der lokalen Konfiguration.

---

## 2. Grundprinzipien

### 2.1 Strikte Trennung von Logik und Konfiguration

Im Repository liegen:

```text
- generischer Router-Code
- Config-Schema
- Beispielkonfigurationen
- Tests
- Dokumentation
- systemd-Beispiele
- Docker/Compose optional
```

Nicht im Repository liegen:

```text
- echte API-Keys
- private Ollama-Account-Daten
- echte lokale IPs, außer als Platzhalter
- produktive lokale Konfiguration
- Logs
- Cache-Dateien
```

### 2.2 Der Router verwaltet keine Accounts

Die Ollama-Accounts bleiben auf den jeweiligen Maschinen:

```text
Hauptrechner:
  lokales Ollama
  Account A

Raspberry Pi:
  Ollama im LAN erreichbar
  Account B
```

Der Router selbst kennt keine Ollama-Login-Daten. Er leitet nur HTTP-Anfragen an die konfigurierten Backends weiter.

### 2.3 Der Router ist generisch

Der Router darf nicht so gebaut werden:

```python
if model == "chess-large":
    ...
```

Sondern so:

```yaml
models:
  chess-large:
    provider_model: "gemma4:26b"
    backends: ["local", "pi"]
```

Der Code liest nur:

```text
Modell-Alias -> echtes Modell -> Backend-Liste -> Policy
```

---

## 3. Repository anlegen und initialisieren

```bash
git clone git@github.com:TotoBa/LLM-Router.git
cd LLM-Router
```

Empfohlene Struktur:

```text
LLM-Router/
├── README.md
├── LICENSE
├── pyproject.toml
├── .gitignore
├── .env.example
├── configs/
│   ├── router.example.yaml
│   ├── router.chess-system.example.yaml
│   └── logging.example.yaml
├── docs/
│   ├── architecture.md
│   ├── configuration.md
│   ├── backends.md
│   ├── kimi-cli.md
│   ├── chess-system.md
│   ├── fallback.md
│   ├── logging.md
│   ├── deployment-systemd.md
│   └── security.md
├── src/
│   └── llm_router/
│       ├── __init__.py
│       ├── app.py
│       ├── config.py
│       ├── schemas.py
│       ├── routing.py
│       ├── backends.py
│       ├── openai_compat.py
│       ├── fallback.py
│       ├── logging_jsonl.py
│       ├── health.py
│       ├── errors.py
│       └── cli.py
├── tests/
│   ├── test_config.py
│   ├── test_routing.py
│   ├── test_model_aliases.py
│   ├── test_fallback_detection.py
│   ├── test_openai_chat_proxy.py
│   ├── test_models_endpoint.py
│   └── conftest.py
├── scripts/
│   ├── run-dev.sh
│   ├── check-config.sh
│   └── smoke-test.sh
├── systemd/
│   └── llm-router.service.example
└── docker/
    ├── Dockerfile
    └── docker-compose.example.yml
```

---

## 4. `.gitignore`

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
dist/
build/

# Local configuration
.env
router.local.yaml
configs/router.local.yaml
configs/*.local.yaml

# Logs
logs/
*.log
*.jsonl

# Runtime
.run/
.cache/

# IDE
.vscode/
.idea/
```

---

## 5. `pyproject.toml`

Ziel: modernes, kleines Python-Projekt.

```toml
[project]
name = "llm-router"
version = "0.1.0"
description = "Generic local LLM routing gateway with OpenAI-compatible API, backend fallback, model aliases and JSONL logging."
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pydantic>=2.8",
    "pyyaml>=6.0",
    "typer>=0.12",
    "rich>=13.7"
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "respx>=0.21",
    "ruff>=0.6",
    "mypy>=1.10"
]

[project.scripts]
llm-router = "llm_router.cli:main"

[tool.ruff]
line-length = 100

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## 6. Konfigurationsmodell

### 6.1 Beispiel: `configs/router.example.yaml`

Diese Datei wird eingecheckt und enthält keine echten Credentials.

```yaml
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  request_timeout_seconds: 600
  connect_timeout_seconds: 10
  reload_config_on_request: false

backends:
  local:
    type: "openai_compatible"
    base_url: "http://127.0.0.1:11434/v1"
    api_key_env: "OLLAMA_LOCAL_API_KEY"
    priority: 10
    enabled: true

  pi:
    type: "openai_compatible"
    base_url: "http://PI-IP:11434/v1"
    api_key_env: "OLLAMA_PI_API_KEY"
    priority: 20
    enabled: true

models:
  default:
    provider_model: "llama3.1:8b"
    backends: ["local", "pi"]
    policy: "standard"

policies:
  standard:
    max_attempts_per_backend: 1
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: false
    fallback_on_4xx: false
    timeout_seconds: 300

  long_running:
    max_attempts_per_backend: 1
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: true
    fallback_on_4xx: false
    timeout_seconds: 900

limit_detection:
  status_codes: [402, 403, 429]
  body_markers:
    - "rate limit"
    - "quota"
    - "limit"
    - "volume"
    - "insufficient quota"
    - "too many requests"
    - "usage limit"

logging:
  level: "INFO"
  jsonl_path: "logs/llm-router.jsonl"
  log_request_body: false
  log_response_body: false
  log_prompt_chars: false
  log_headers: false
```

### 6.2 Lokale produktive Konfiguration

Lokal wird daraus kopiert:

```bash
cp configs/router.example.yaml configs/router.local.yaml
```

Dann lokal anpassen:

```yaml
backends:
  local:
    base_url: "http://127.0.0.1:11434/v1"

  pi:
    base_url: "http://pi-ollama.example.local:11434/v1"
```

`configs/router.local.yaml` wird nicht eingecheckt.

---

## 7. Beispielkonfiguration für dein Setup

Datei: `configs/router.chess-system.example.yaml`

```yaml
server:
  host: "127.0.0.1"
  port: 18080

runtime:
  request_timeout_seconds: 900
  connect_timeout_seconds: 10
  reload_config_on_request: false

backends:
  local:
    type: "openai_compatible"
    base_url: "http://127.0.0.1:11434/v1"
    api_key_env: "OLLAMA_LOCAL_API_KEY"
    priority: 10
    enabled: true

  pi:
    type: "openai_compatible"
    base_url: "http://PI-IP:11434/v1"
    api_key_env: "OLLAMA_PI_API_KEY"
    priority: 20
    enabled: true

models:
  kimi-cli-default:
    provider_model: "kimi-k2.5:cloud"
    backends: ["local", "pi"]
    policy: "interactive"

  chess-router:
    provider_model: "gemma4:e4b"
    backends: ["local", "pi"]
    policy: "fast"

  chess-small:
    provider_model: "gemma4:e4b"
    backends: ["local", "pi"]
    policy: "fast"

  chess-large:
    provider_model: "gemma4:26b"
    backends: ["local", "pi"]
    policy: "long_running"

  chess-task:
    provider_model: "kimi-k2.5:cloud"
    backends: ["local", "pi"]
    policy: "standard"

policies:
  interactive:
    max_attempts_per_backend: 1
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: true
    fallback_on_4xx: false
    timeout_seconds: 300

  fast:
    max_attempts_per_backend: 1
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: false
    fallback_on_4xx: false
    timeout_seconds: 120

  standard:
    max_attempts_per_backend: 1
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: true
    fallback_on_4xx: false
    timeout_seconds: 300

  long_running:
    max_attempts_per_backend: 1
    retry_on_connection_error: true
    retry_on_timeout: false
    fallback_on_limit: true
    fallback_on_5xx: true
    fallback_on_4xx: false
    timeout_seconds: 900

limit_detection:
  status_codes: [402, 403, 429]
  body_markers:
    - "rate limit"
    - "quota"
    - "limit"
    - "volume"
    - "insufficient quota"
    - "too many requests"
    - "usage limit"

logging:
  level: "INFO"
  jsonl_path: "logs/llm-router.jsonl"
  log_request_body: false
  log_response_body: false
  log_prompt_chars: false
  log_headers: false
```

---

## 8. `.env.example`

```env
# For local Ollama, the value is usually required by OpenAI clients
# but ignored by Ollama.
OLLAMA_LOCAL_API_KEY=ollama
OLLAMA_PI_API_KEY=ollama

# Optional default config path
LLM_ROUTER_CONFIG=configs/router.local.yaml
```

Echte `.env` nicht einchecken.

---

## 9. Router-Funktionalität

### 9.1 Muss-Funktionen Version 0.1

Der Router soll folgende Endpunkte bereitstellen:

```text
GET  /health
GET  /v1/models
POST /v1/chat/completions
```

Optional generisch durchreichen:

```text
POST /v1/embeddings
POST /v1/responses
```

Aber Version 0.1 sollte primär `/v1/chat/completions` stabil können, weil das für Kimi-cli und das Schachsystem am wichtigsten ist.

### 9.2 `/health`

Antwort:

```json
{
  "ok": true,
  "version": "0.1.0",
  "config_loaded": true,
  "models": ["kimi-cli-default", "chess-small", "chess-large"],
  "backends": {
    "local": {
      "enabled": true,
      "base_url": "http://127.0.0.1:11434/v1"
    },
    "pi": {
      "enabled": true,
      "base_url": "http://PI-IP:11434/v1"
    }
  }
}
```

Keine API-Keys ausgeben.

### 9.3 `/v1/models`

Der Router gibt die logischen Modell-Aliase aus:

```json
{
  "object": "list",
  "data": [
    {
      "id": "kimi-cli-default",
      "object": "model",
      "owned_by": "llm-router"
    },
    {
      "id": "chess-small",
      "object": "model",
      "owned_by": "llm-router"
    }
  ]
}
```

### 9.4 `/v1/chat/completions`

Eingang:

```json
{
  "model": "chess-small",
  "messages": [
    {
      "role": "user",
      "content": "Klassifiziere diesen Zug..."
    }
  ]
}
```

Router intern:

```text
request model: chess-small
provider_model: gemma4:e4b
backends: local -> pi
```

Weiterleitung an Backend:

```json
{
  "model": "gemma4:e4b",
  "messages": [
    {
      "role": "user",
      "content": "Klassifiziere diesen Zug..."
    }
  ]
}
```

Antwort wird unverändert zurückgegeben, ergänzt um Router-Header:

```text
x-llm-router-backend: local
x-llm-router-request-model: chess-small
x-llm-router-provider-model: gemma4:e4b
x-llm-router-fallback-used: false
```

---

## 10. Fallback-Logik

### 10.1 Fallback-Fälle

Fallback auf das nächste Backend, wenn:

```text
- HTTP 402
- HTTP 403 mit Limit-/Quota-Hinweis
- HTTP 429
- Connection Error
- Backend nicht erreichbar
- optional HTTP 5xx, abhängig von Policy
```

Kein Fallback bei:

```text
- ungültigem Request
- unbekanntem Modell ohne passende Default-Policy
- Auth-Fehler, wenn nicht als Limit erkennbar
- 400 Bad Request
- 404 Model not found, außer Policy erlaubt es ausdrücklich
```

### 10.2 Limit-Erkennung

Die Erkennung soll konfigurierbar sein:

```yaml
limit_detection:
  status_codes: [402, 403, 429]
  body_markers:
    - "rate limit"
    - "quota"
    - "limit"
    - "volume"
    - "insufficient quota"
    - "too many requests"
    - "usage limit"
```

Implementierungsidee:

```python
def looks_like_limit_error(status_code: int, body: bytes, config: LimitDetectionConfig) -> bool:
    if status_code in config.status_codes:
        return True

    text = body.decode("utf-8", errors="ignore").lower()
    return any(marker.lower() in text for marker in config.body_markers)
```

### 10.3 Backend-Reihenfolge

Backends werden nicht hart codiert. Die Reihenfolge kommt aus:

```yaml
models:
  chess-large:
    backends: ["local", "pi"]
```

Falls keine Backends gesetzt sind:

```text
alle enabled Backends sortiert nach priority
```

---

## 11. Streaming

Streaming ist wichtig, weil Kimi-cli interaktiv arbeitet.

### Version 0.1

Ziel:

```text
Non-Streaming stabil
Streaming möglichst direkt durchreichen
```

Für `stream: true` soll der Router nicht erst die ganze Antwort puffern, sondern mit `StreamingResponse` weiterleiten.

Zu beachten:

```text
- Bei Streaming kann ein Fallback nur vor Beginn des Antwortstreams sauber passieren.
- Wenn das Backend erst während des Streams abbricht, ist ein transparenter Retry schwierig.
- Deshalb: bei Streaming zuerst Backend-Verfügbarkeit prüfen oder Fehler bis zum ersten Chunk erkennen.
```

Plan:

```text
1. Non-Streaming vollständig testen.
2. Streaming-Passthrough implementieren.
3. Fallback vor erstem Chunk erlauben.
4. Kein automatischer Mid-Stream-Retry in Version 0.1.
```

---

## 12. Logging

### 12.1 Ziel

Logs sollen helfen, später zu sehen:

```text
- Welcher Client hat gefragt?
- Welches logische Modell wurde angefordert?
- Welches echte Modell wurde genutzt?
- Welches Backend wurde genutzt?
- Gab es Fallback?
- Wie lange dauerte der Request?
- Welcher Status kam zurück?
- War es ein Limit-Fehler?
```

### 12.2 JSONL-Format

Beispiel:

```json
{
  "ts": "2026-05-16T20:15:30+02:00",
  "request_id": "01HY...",
  "client": "chess-system",
  "path": "/v1/chat/completions",
  "request_model": "chess-large",
  "provider_model": "gemma4:26b",
  "backend": "local",
  "status_code": 429,
  "limit_detected": true,
  "fallback_used": false,
  "duration_ms": 823,
  "prompt_chars": null,
  "response_chars": null
}
```

Fallback-Zweiter Versuch:

```json
{
  "ts": "2026-05-16T20:15:31+02:00",
  "request_id": "01HY...",
  "client": "chess-system",
  "path": "/v1/chat/completions",
  "request_model": "chess-large",
  "provider_model": "gemma4:26b",
  "backend": "pi",
  "status_code": 200,
  "limit_detected": false,
  "fallback_used": true,
  "duration_ms": 5720
}
```

### 12.3 Datenschutz

Standardmäßig:

```yaml
log_request_body: false
log_response_body: false
log_prompt_chars: false
log_headers: false
```

Für Debugging lokal optional aktivierbar.

Keine Prompts standardmäßig loggen, weil das Schachsystem später komplette Partieanalysen, Trainingsnotizen und eventuell private Daten senden kann.

---

## 13. Client-Erkennung

Der Router soll Clients optional über Header erkennen:

```text
X-LLM-Client: kimi-cli
X-LLM-Client: chess-system
X-LLM-Client: manual-test
```

Wenn kein Header gesetzt ist:

```text
client = "unknown"
```

Optional kann aus dem Modellnamen grob geschlossen werden:

```text
chess-* -> chess-system
kimi-*  -> kimi-cli
```

Aber das darf nur Logging beeinflussen, nicht die Routing-Logik.

---

## 14. Kimi-cli-Anbindung

Datei lokal:

```bash
nano ~/.kimi/config.toml
```

Beispiel:

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

Danach kann Kimi-cli den Router wie einen OpenAI-kompatiblen Provider nutzen. Der Router leitet intern auf Ollama weiter.

Test:

```bash
kimi --model kimi-cli-default
```

---

## 15. Schachsystem-Anbindung

Im Schachsystem sollten keine echten Backend-URLs mehr im Analysecode stehen.

### 15.1 `.env` im Schachsystem

```env
LLM_BASE_URL=http://127.0.0.1:18080/v1
LLM_API_KEY=ollama

LLM_MODEL_ROUTER=chess-router
LLM_MODEL_SMALL=chess-small
LLM_MODEL_LARGE=chess-large
LLM_MODEL_TASK=chess-task
```

Oder, falls das System OpenAI-kompatible Standardvariablen nutzt:

```env
OPENAI_BASE_URL=http://127.0.0.1:18080/v1
OPENAI_API_KEY=ollama

CHESS_LLM_ROUTER_MODEL=chess-router
CHESS_LLM_SMALL_MODEL=chess-small
CHESS_LLM_LARGE_MODEL=chess-large
CHESS_LLM_TASK_MODEL=chess-task
```

### 15.2 Rollen im Schachsystem

Das Schachsystem soll nur noch logische Rollen kennen:

```text
router:
  entscheidet Aufgabenklasse, Modellklasse, Analyseweg

small:
  schnelle Klassifikation
  Zugbewertung
  Fehlerart
  Ausgenutzt/nicht ausgenutzt
  Stellungsschärfe
  Themenlabels

large:
  lange menschenähnliche Analyse
  Zug-für-Zug-Kommentierung
  Vergleich mit alten Partien
  Trainingshinweise

task:
  PGN-Kommentare
  Variantenformulierung
  Zusammenfassungen
  Aufgabenextraktion
  Prompt-Umbau
```

Das Schachsystem soll nicht wissen:

```text
- ob gemma4:e4b lokal oder auf dem Pi läuft
- ob Account A oder Account B benutzt wird
- ob Kimi, Ollama Cloud oder später OpenRouter dahinterliegt
```

---

## 16. Pi-Ollama im LAN

Auf dem Raspberry Pi muss Ollama im lokalen Netz lauschen.

Systemd-Override:

```bash
sudo systemctl edit ollama
```

Eintragen:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Dann:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

Vom Hauptrechner testen:

```bash
curl http://PI-IP:11434/api/tags
curl http://PI-IP:11434/v1/models
```

Ollama dokumentiert, dass `OLLAMA_HOST` steuert, auf welcher Adresse der Server bindet; standardmäßig ist Ollama lokal auf `127.0.0.1:11434` gebunden. ([Ollama Dokumentation][3])

Sicherheitsregel:

```text
Kein Port-Forwarding ins Internet.
Nur Heimnetz.
Später optional Firewall-Regel: Zugriff nur vom Hauptrechner.
```

---

## 17. CLI für den Router

Der Router soll eine kleine CLI bekommen:

```bash
llm-router serve --config configs/router.local.yaml
llm-router check-config --config configs/router.local.yaml
llm-router list-models --config configs/router.local.yaml
llm-router test-backends --config configs/router.local.yaml
llm-router smoke-test --model chess-small --prompt "Antworte nur OK."
```

### 17.1 `check-config`

Prüft:

```text
- YAML valide
- alle Models referenzieren existierende Policies
- alle Models referenzieren existierende Backends
- alle Backends haben base_url
- api_key_env ist gesetzt oder optional erlaubt
- keine offensichtlichen Secret-Werte in Beispielconfigs
```

### 17.2 `test-backends`

Ruft pro Backend auf:

```text
GET /v1/models
```

oder Ollama-spezifisch optional:

```text
GET /api/tags
```

Der Router selbst sollte aber primär OpenAI-kompatibel bleiben.

---

## 18. Tests

### 18.1 Config-Tests

`tests/test_config.py`

Prüfen:

```text
- example config lädt
- fehlende Backend-Referenz wird erkannt
- fehlende Policy wird erkannt
- disabled Backends werden ignoriert
- Priorität wird korrekt sortiert
```

### 18.2 Routing-Tests

`tests/test_routing.py`

Prüfen:

```text
- Alias chess-small wird zu provider_model gemma4:e4b
- unbekanntes Modell wird je nach Policy abgelehnt oder als passthrough behandelt
- Backend-Reihenfolge kommt aus Modellconfig
```

### 18.3 Fallback-Tests

`tests/test_fallback_detection.py`

Prüfen:

```text
- 429 löst Fallback aus
- 402 löst Fallback aus
- 403 mit "quota" löst Fallback aus
- 403 ohne Limit-Hinweis löst nicht zwingend Fallback aus
- 400 löst keinen Fallback aus
- Connection Error löst Fallback aus
```

### 18.4 OpenAI-Proxy-Tests

`tests/test_openai_chat_proxy.py`

Mit `respx` oder Mock-Backend:

```text
- /v1/chat/completions wird weitergeleitet
- model-Feld wird ersetzt
- messages bleiben unverändert
- temperature bleibt unverändert
- stream=false funktioniert
- Antwort wird unverändert zurückgegeben
- Router-Header werden gesetzt
```

### 18.5 `/v1/models`

`tests/test_models_endpoint.py`

Prüfen:

```text
- gibt logische Modellnamen aus
- gibt keine Backend-URLs oder Secrets aus
```

---

## 19. Fehlerverhalten

### 19.1 Unbekanntes Modell

Option A, strenger Modus:

```json
{
  "error": {
    "message": "Unknown router model alias: xyz",
    "type": "unknown_model_alias"
  }
}
```

Option B, Passthrough-Modus:

```text
Unbekanntes Modell wird unverändert an Standard-Backends weitergeleitet.
```

Empfehlung:

```yaml
runtime:
  unknown_model_strategy: "error"
```

Für dein Setup ist `error` besser, weil Tippfehler sonst schwer zu finden sind.

### 19.2 Alle Backends fehlgeschlagen

```json
{
  "error": {
    "message": "All configured backends failed for model chess-large.",
    "type": "all_backends_failed"
  }
}
```

Header:

```text
x-llm-router-error: all_backends_failed
```

### 19.3 Backend-Modell fehlt

Wenn ein Backend `model not found` liefert:

```text
- Standard: Fehler zurückgeben
- optional: nächstes Backend versuchen, wenn Policy fallback_on_model_not_found=true
```

Für dein Setup sinnvoll:

```yaml
policies:
  long_running:
    fallback_on_model_not_found: true
```

Begründung: `gemma4:26b` könnte auf dem Pi fehlen, dann ist die Meldung eindeutig. Im produktiven Betrieb würde ich aber darauf achten, dass beide Backends dieselben Modellnamen bereitstellen oder bewusst unterschiedlich gemappt werden.

---

## 20. Spätere Erweiterung: Backend-spezifische Modellnamen

Falls lokal und Pi unterschiedliche Modellnamen nutzen:

```yaml
models:
  chess-large:
    backends: ["local", "pi"]
    backend_models:
      local: "gemma4:26b"
      pi: "gemma4:12b"
    policy: "long_running"
```

Dann gilt:

```text
request model: chess-large
local -> gemma4:26b
pi    -> gemma4:12b
```

Das ist besser als Modellnamen im Schachsystem zu ändern.

---

## 21. Spätere Erweiterung: Provider-Typen

Version 0.1:

```yaml
type: "openai_compatible"
```

Später:

```yaml
backends:
  openrouter:
    type: "openai_compatible"
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"

  kimi:
    type: "openai_compatible"
    base_url: "https://api.moonshot.ai/v1"
    api_key_env: "KIMI_API_KEY"

  local_ollama:
    type: "openai_compatible"
    base_url: "http://127.0.0.1:11434/v1"
    api_key_env: "OLLAMA_LOCAL_API_KEY"
```

Der Router sollte nicht an Ollama gebunden sein. Ollama ist nur der erste Backend-Typ.

---

## 22. Security

### 22.1 Standard-Binding

Router standardmäßig nur lokal:

```yaml
server:
  host: "127.0.0.1"
  port: 18080
```

Nicht standardmäßig:

```yaml
host: "0.0.0.0"
```

### 22.2 Keine Secrets in Logs

Nie loggen:

```text
Authorization
api_key
Cookie
Set-Cookie
```

Headers nur loggen, wenn explizit aktiviert, und dann mit Redaction.

### 22.3 API-Key für Router selbst

Optional später:

```yaml
server:
  require_api_key: true
  api_key_env: "LLM_ROUTER_API_KEY"
```

Für lokalen Betrieb zunächst nicht zwingend, weil nur `127.0.0.1`.

---

## 23. Systemd-Service

Datei im Repo:

```text
systemd/llm-router.service.example
```

Inhalt:

```ini
[Unit]
Description=Local LLM Router
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/DEIN_USER/LLM-Router
Environment=LLM_ROUTER_CONFIG=/home/DEIN_USER/LLM-Router/configs/router.local.yaml
EnvironmentFile=-/home/DEIN_USER/LLM-Router/.env
ExecStart=/home/DEIN_USER/LLM-Router/.venv/bin/llm-router serve --config /home/DEIN_USER/LLM-Router/configs/router.local.yaml
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Installation lokal:

```bash
sudo cp systemd/llm-router.service.example /etc/systemd/system/llm-router.service
sudo nano /etc/systemd/system/llm-router.service
sudo systemctl daemon-reload
sudo systemctl enable --now llm-router
```

Status:

```bash
systemctl status llm-router
journalctl -u llm-router -f
```

---

## 24. Docker optional

Nicht für Phase 1 zwingend, aber als spätere saubere Deployment-Option.

`docker/docker-compose.example.yml`:

```yaml
services:
  llm-router:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "127.0.0.1:18080:18080"
    environment:
      LLM_ROUTER_CONFIG: /app/configs/router.local.yaml
    volumes:
      - ../configs/router.local.yaml:/app/configs/router.local.yaml:ro
      - ../logs:/app/logs
    restart: unless-stopped
```

---

## 25. README-Struktur

`README.md` soll knapp und praktisch sein:

```markdown
# LLM-Router

Generic local LLM routing gateway with OpenAI-compatible API, model aliases, backend fallback and JSONL logging.

## Features

- OpenAI-compatible `/v1/chat/completions`
- logical model aliases
- backend fallback
- quota/rate-limit detection
- JSONL logging
- config-driven routing
- no credentials in repository
- usable by Kimi CLI, chess systems and other local tools

## Quickstart

...

## Configuration

...

## Kimi CLI

...

## Chess System Example

...

## Security Notes

...
```

---

## 26. Umsetzung in Phasen

## Phase 1: Repository-Grundgerüst

Ziel: leeres Repo in ein sauberes Python-Projekt verwandeln.

Aufgaben:

```text
1. pyproject.toml erstellen
2. src/llm_router/ Paketstruktur erstellen
3. tests/ anlegen
4. configs/router.example.yaml anlegen
5. .gitignore anlegen
6. README.md mit Minimalinhalt anlegen
7. .env.example anlegen
8. systemd/llm-router.service.example anlegen
```

Abnahmekriterien:

```bash
python -m pip install -e ".[dev]"
pytest
llm-router --help
```

---

## Phase 2: Config-Lader und Schema

Ziel: Konfiguration sauber validieren.

Module:

```text
src/llm_router/config.py
src/llm_router/schemas.py
```

Aufgaben:

```text
1. Pydantic-Modelle für ServerConfig, BackendConfig, ModelRouteConfig, PolicyConfig bauen
2. YAML laden
3. ENV-Variablen für API-Keys nur zur Laufzeit auflösen
4. Validierung:
   - Model referenziert existierende Backends
   - Model referenziert existierende Policy
   - Backend base_url endet optional sauber ohne Slash
   - mindestens ein enabled Backend
5. CLI-Befehl check-config bauen
```

Abnahmekriterien:

```bash
llm-router check-config --config configs/router.example.yaml
pytest tests/test_config.py
```

---

## Phase 3: Minimaler FastAPI-Server

Ziel: Router startet und liefert Health/Models.

Module:

```text
src/llm_router/app.py
src/llm_router/health.py
src/llm_router/cli.py
```

Aufgaben:

```text
1. FastAPI-App erzeugen
2. /health implementieren
3. /v1/models implementieren
4. CLI serve implementieren
5. Config-Pfad über --config und LLM_ROUTER_CONFIG erlauben
```

Abnahmekriterien:

```bash
llm-router serve --config configs/router.example.yaml
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/v1/models
```

---

## Phase 4: OpenAI-kompatibler Chat-Proxy

Ziel: `/v1/chat/completions` funktioniert non-streaming.

Module:

```text
src/llm_router/openai_compat.py
src/llm_router/backends.py
src/llm_router/routing.py
```

Aufgaben:

```text
1. Request JSON lesen
2. model-Feld extrahieren
3. Modell-Alias auf provider_model mappen
4. Backend-Liste bestimmen
5. Request an erstes Backend weiterleiten
6. model-Feld im JSON auf provider_model umschreiben
7. Antwort unverändert zurückgeben
8. Router-Header ergänzen
```

Abnahmekriterien:

```bash
curl http://127.0.0.1:18080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-LLM-Client: manual-test" \
  -d '{
    "model": "default",
    "messages": [{"role": "user", "content": "Antworte nur OK."}]
  }'
```

---

## Phase 5: Fallback

Ziel: Bei Limit oder Backend-Ausfall automatisch nächstes Backend nutzen.

Module:

```text
src/llm_router/fallback.py
src/llm_router/errors.py
```

Aufgaben:

```text
1. Limit-Erkennung aus Config implementieren
2. Connection Error als fallbackfähig behandeln
3. Policy-Felder auswerten:
   - fallback_on_limit
   - fallback_on_5xx
   - fallback_on_4xx
   - retry_on_connection_error
   - retry_on_timeout
4. Fehler sauber als OpenAI-kompatible Error Response zurückgeben
5. Tests mit simulierten Backends bauen
```

Abnahmekriterien:

```text
- Backend local gibt 429 -> Router nutzt pi
- Backend local nicht erreichbar -> Router nutzt pi
- Backend local gibt 400 -> kein Fallback
- Alle Backends down -> klare Fehlermeldung
```

---

## Phase 6: JSONL-Logging

Ziel: jedes Routing-Ereignis nachvollziehbar machen.

Modul:

```text
src/llm_router/logging_jsonl.py
```

Aufgaben:

```text
1. request_id erzeugen
2. pro Backend-Versuch Logzeile schreiben
3. Client aus X-LLM-Client lesen
4. sensible Header nie loggen
5. optional prompt_chars/response_chars nur bei Config-Freigabe
6. logs/ automatisch anlegen
```

Abnahmekriterien:

```bash
tail -f logs/llm-router.jsonl
```

Es muss sichtbar sein:

```text
client
request_model
provider_model
backend
status_code
fallback_used
duration_ms
```

---

## Phase 7: Streaming

Ziel: `stream: true` für Kimi-cli sauber unterstützen.

Aufgaben:

```text
1. stream=true erkennen
2. httpx streaming request nutzen
3. StreamingResponse zurückgeben
4. Fallback vor erstem Chunk erlauben
5. keine Mid-Stream-Retry-Magie in Version 0.1
6. Tests für Streaming-Passthrough
```

Abnahmekriterien:

```text
Kimi-cli zeigt Tokens laufend an, nicht erst am Ende.
```

---

## Phase 8: Dokumentation

Ziel: Repo ist ohne Chat-Kontext verständlich.

Dokumente:

```text
docs/architecture.md
docs/configuration.md
docs/backends.md
docs/kimi-cli.md
docs/chess-system.md
docs/fallback.md
docs/logging.md
docs/deployment-systemd.md
docs/security.md
```

Besonders wichtig:

```text
- Keine Credentials ins Repo
- Lokale Config kopieren und anpassen
- Kimi-cli-Konfigurationsbeispiel
- Schachsystem-Konfigurationsbeispiel
- Pi-Ollama-LAN-Konfiguration
- Troubleshooting bei 429/Quota/Limit
```

---

## Phase 9: Lokale Integration

### 9.1 Router installieren

```bash
git clone git@github.com:TotoBa/LLM-Router.git
cd LLM-Router
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp configs/router.chess-system.example.yaml configs/router.local.yaml
nano configs/router.local.yaml
```

### 9.2 `.env`

```bash
cp .env.example .env
nano .env
```

Für Ollama:

```env
OLLAMA_LOCAL_API_KEY=ollama
OLLAMA_PI_API_KEY=ollama
```

### 9.3 Start

```bash
llm-router serve --config configs/router.local.yaml
```

### 9.4 Test

```bash
curl http://127.0.0.1:18080/health
curl http://127.0.0.1:18080/v1/models
```

### 9.5 Kimi-cli umstellen

`~/.kimi/config.toml`:

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

### 9.6 Schachsystem umstellen

Im Schachsystem:

```env
LLM_BASE_URL=http://127.0.0.1:18080/v1
LLM_API_KEY=ollama

LLM_MODEL_ROUTER=chess-router
LLM_MODEL_SMALL=chess-small
LLM_MODEL_LARGE=chess-large
LLM_MODEL_TASK=chess-task
```

---

## 27. Nicht-Ziele für Version 0.1

Nicht in die erste Version packen:

```text
- Web-UI
- komplexes Kosten-Tracking
- Multi-Tenant-Auth
- dynamische Lastverteilung
- automatische Modellinstallation
- persistente Datenbank
- RAG
- Schachlogik
- Prompt-Optimierung
- komplexe Agentensteuerung
```

Der Router soll zuerst stabil, klein und durchschaubar sein.

---

## 28. Spätere Versionen

### Version 0.2

```text
- Backend-spezifische Modellnamen
- /v1/responses Passthrough
- bessere Streaming-Tests
- Healthcheck pro Backend
- optionales Backend-Warmup
```

### Version 0.3

```text
- Kosten-/Token-Logging, falls Provider usage liefert
- tägliche Nutzungszusammenfassung
- einfache Provider-Prioritäten nach Uhrzeit oder Client
- Fallback-Statistiken
```

### Version 0.4

```text
- weitere Provider-Beispiele:
  - OpenRouter
  - direkte Kimi API
  - OpenAI
  - Anthropic-kompatible Adapter, falls nötig
```

### Version 0.5

```text
- lokale kleine Admin-CLI:
  - letzte Requests anzeigen
  - Fallback-Häufigkeit anzeigen
  - Backend-Verfügbarkeit anzeigen
```

---

## 29. Architekturentscheidung für dein Gesamtsystem

Die wichtigste Entscheidung:

```text
Kimi-cli und Schachsystem sprechen nie direkt mit Ollama.
Sie sprechen nur mit dem LLM-Router.
```

Dadurch bleiben beide Systeme einfach:

```text
kimi-cli:
  kennt nur kimi-cli-default

Schachsystem:
  kennt nur router/small/large/task

LLM-Router:
  kennt Backends, Modellnamen, Fallback, Logs, Policies
```

Das ist genau die richtige Trennung:

```text
Schachsystem = Fachlogik
LLM-Router   = Infrastruktur
Ollama/Pi    = konkrete Runtime
```

---

## 30. Kompakter Umsetzungsauftrag für Codex/Kimi-cli

```text
Arbeite im Repository git@github.com:TotoBa/LLM-Router.git.

Ziel:
Baue einen generischen lokalen LLM-Router als eigenständiges Python-Projekt. Der Router stellt eine OpenAI-kompatible API bereit, insbesondere /v1/chat/completions und /v1/models. Er soll Modell-Aliase, Backend-Fallback, konfigurierbare Policies und JSONL-Logging unterstützen. Der Router darf keine Credentials, keine echten lokalen IPs und keine Schachlogik im Code enthalten. Alle lokalen Details müssen über nicht eingecheckte Config-Dateien steuerbar sein.

Wichtige Architektur:
- Code und Konfiguration strikt trennen.
- Beispielconfigs einchecken, lokale configs gitignorieren.
- Backends generisch konfigurieren.
- Modelle als Aliase konfigurieren.
- Fallback-Regeln über Policies konfigurieren.
- JSONL-Logging ohne Prompt-/Response-Inhalte als Default.
- Kimi-cli und ein Schachsystem sollen den Router später beide über http://127.0.0.1:18080/v1 nutzen können.
- Schachmodellnamen wie chess-small, chess-large, chess-task dürfen nur als Beispielkonfiguration vorkommen, nicht als Spezialfälle im Code.

Setze schrittweise um:
1. Projektstruktur mit pyproject.toml, src/llm_router, tests, configs, docs, scripts, systemd anlegen.
2. Pydantic-Konfigurationsschema und YAML-Lader implementieren.
3. CLI mit serve, check-config, list-models, test-backends vorbereiten.
4. FastAPI-App mit /health und /v1/models implementieren.
5. /v1/chat/completions als OpenAI-kompatiblen Proxy implementieren.
6. Modell-Alias auf provider_model umschreiben.
7. Backend-Reihenfolge aus Config bestimmen.
8. Fallback bei Limitfehlern, Connection Errors und optional 5xx gemäß Policy implementieren.
9. JSONL-Logging pro Backend-Versuch implementieren.
10. Streaming-Passthrough für stream=true ergänzen, ohne Mid-Stream-Retry.
11. Tests für Config, Routing, Fallback, /v1/models und Chat-Proxy schreiben.
12. Dokumentation für Architektur, Konfiguration, Kimi-cli, Schachsystem, Fallback, Logging, systemd und Security schreiben.
13. Keine Secrets einchecken. .env, router.local.yaml, logs und lokale Configs müssen in .gitignore stehen.

Akzeptanz:
- pytest läuft grün.
- llm-router check-config --config configs/router.example.yaml funktioniert.
- llm-router serve --config configs/router.example.yaml startet.
- GET /health funktioniert.
- GET /v1/models zeigt logische Modell-Aliase.
- POST /v1/chat/completions leitet an ein konfiguriertes Backend weiter.
- Bei simuliertem 429 auf Backend local wird Backend pi genutzt.
- Logs zeigen request_model, provider_model, backend, status_code, fallback_used und duration_ms.
- README erklärt Quickstart, Kimi-cli-Anbindung und Schachsystem-Anbindung.
```

[1]: https://www.kimi.com/code/docs/en/kimi-code-cli/configuration/providers-and-models.html "Providers and Models | Kimi Code Docs"
[2]: https://docs.ollama.com/openai "OpenAI compatibility - Ollama"
[3]: https://docs.ollama.com/faq "FAQ - Ollama"
