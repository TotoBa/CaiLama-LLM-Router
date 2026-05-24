# Backends

## Unterstützte Backend-Typen

### openai_compatible (Version 0.1)

Jeder Server, der die OpenAI-compatible Chat-Completions-API spricht:

- **Ollama** (lokal, auf RasPi, im Netzwerk)
- **llama.cpp-Server**
- **OpenRouter**, **OpenAI**, **Kimi** (über eigene Env-Keys)

```yaml
backends:
  openrouter:
    type: "openai_compatible"
    base_url: "https://openrouter.ai/api/v1"
    api_key_env: "OPENROUTER_API_KEY"
    priority: 30
    enabled: true
```

## Ollama-Spezialfälle

### Zwei lokale Ollama-Container auf einer VM

Für längere Benchmarks kann der Router zwei lokale Ollama-Instanzen auf
derselben VM ansprechen. Das ersetzt langsame entfernte Backends, bleibt aber
reine Infrastrukturkonfiguration:

```bash
cp docker/docker-compose.dual-ollama.example.yml docker-compose.ollama.local.yml
cp configs/router.vm-dual-ollama.example.yaml configs/router.local.yaml
```

Die echte lokale `.env` darf API-Keys enthalten und bleibt unversioniert:

```bash
OLLAMA_VM_A_API_KEY=...
OLLAMA_VM_B_API_KEY=...
```

Danach laufen die Cloud-Backends typischerweise auf `127.0.0.1:11435` und
`127.0.0.1:11436`. Sie dienen als zwei getrennte Ollama-Cloud-Ausgaenge mit
separaten API-Keys. Lokale Benchmarkmodelle laufen dagegen nicht in diesen
Containern, sondern ueber den bestehenden Host-Ollama auf
`127.0.0.1:11434`. Dadurch muessen lokale Modelle nur einmal geladen werden
und die VM versucht nicht, zwei lokale Modelle parallel zu betreiben.
Ollamas lokale API ist standardmaessig nicht durch einen Bearer-Key
abgesichert; die Keys werden fuer Ollama-Cloud-Zugriff beziehungsweise
Client-/Router-Konventionen durchgereicht.

Die Compose-Datei setzt `restart: unless-stopped`. Wenn Docker selbst beim
Systemstart enabled ist, kommen die beiden Container nach einem Reboot wieder
hoch. Nach Aenderungen an `.env` muessen die Container neu erstellt werden,
damit neue `OLLAMA_VM_A_API_KEY`-/`OLLAMA_VM_B_API_KEY`-Werte in der
Containerumgebung landen:

```bash
docker compose --env-file .env -f docker-compose.ollama.local.yml up -d
systemctl --user restart llm-router.service
```

### Lokaler Ollama

```yaml
backends:
  local:
    type: "openai_compatible"
    base_url: "http://127.0.0.1:11434/v1"
    api_key_env: "OLLAMA_LOCAL_API_KEY"
```

Setze in `.env`:
```bash
OLLAMA_LOCAL_API_KEY=ollama   # Ollama ignoriert ihn, OpenAI-Clients brauchen ihn
```

### Ollama auf Raspberry Pi im LAN

Auf dem RasPi muss Ollama auf `0.0.0.0` lauschen:

```bash
sudo systemctl edit ollama
```

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

Danach:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

Vom Hauptrechner testen:
```bash
curl http://OLLAMA_PI_IP:11434/api/tags
curl http://OLLAMA_PI_IP:11434/v1/models
```

Sicherheitsregel: Kein Port-Forwarding ins Internet. Nur Heimnetz oder VPN.

Wenn der Pi als dauerhaftes Backend laufen soll, muss der Dienst aktiviert sein:

```bash
sudo systemctl enable --now ollama
systemctl is-enabled ollama
systemctl is-active ollama
```

## Healthcheck der Backends

```bash
llm-router test-backends --config configs/router.local.yaml
```

Dies ruft pro Backend `GET <base_url>/models` auf. Bei einer Ollama-Config mit `base_url: http://OLLAMA_PI_IP:11434/v1` ist das also `GET /v1/models`.

## Endpoint-Pfad pro Backend

Standardmaessig sendet der Router an `POST /chat/completions` – der OpenAI-
Standard. Spezialisierte Backends (z.B. Bildgenerierung, Embeddings) koennen
ueber `endpoint_path` einen anderen Pfad erhalten. Der Alias und die Client-
Anfrage bleiben unveraendert OpenAI-kompatibel; nur der Backend-Endpoint
passt sich an.

```yaml
backends:
  image-gen:
    type: "openai_compatible"
    base_url: "https://api.example-provider.com"
    api_key_env: "IMAGE_API_KEY"
    priority: 10
    endpoint_path: "/v1/images/generations"

models:
  image-model:
    provider_model: "dall-e-3"
    backends: ["image-gen"]
    policy: "standard"
```

Ohne `endpoint_path` wird `/chat/completions` verwendet. Der Router
vermeidet jede produktspezifische Logik – Prompt-Aufbereitung, Parameter-
Mapping und Antwort-Transformation bleiben dem Backend und dem aufrufenden
Client ueberlassen.

## Verteilung ueber mehrere Backends

Backends koennen priorisiert oder verteilt genutzt werden:

- `routing_strategy: "priority"` nutzt die Reihenfolge aus `models.*.backends` bzw. die Backend-Prioritaet.
- `routing_strategy: "round_robin"` rotiert den ersten Versuch ueber alle verfuegbaren Backends des Modellalias.

Ein Backend gilt temporaer als nicht verfuegbar, wenn es die Fehlerschwelle aus der Policy erreicht:

```yaml
policies:
  standard:
    max_attempts_per_backend: 2
    max_backend_failures_before_cooldown: 2
    backend_cooldown_seconds: 300
```
