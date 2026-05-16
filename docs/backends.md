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
