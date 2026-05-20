# Kimi Code CLI Anbindung

## Prinzip

Kimi spricht nicht direkt mit Ollama, sondern mit dem Router. Der Router entscheidet über Backend und echtes Modell.

## Konfiguration in ~/.kimi/config.toml

```toml
default_model = "kimi-cli-default"

[providers.local-llm-router]
type = "openai_legacy"
base_url = "http://ROUTER_VM_IP:18080/v1"
api_key = "ollama"

[models.kimi-cli-default]
provider = "local-llm-router"
model = "kimi-cli-default"
max_context_size = 131072
capabilities = ["thinking"]
```

Kimi interpretiert `openai_legacy` als OpenAI-kompatiblen Provider. Der Wert von `api_key` wird an den Router gesendet. Fuer lokale Ollama-Backends ist der Wert normalerweise nur ein Client-Platzhalter.

## Router-Konfiguration

Stelle sicher, dass `configs/router.local.yaml` folgendes Modell definiert:

```yaml
models:
  kimi-cli-default:
    provider_model: "kimi-k2.6:cloud"
    backends: ["vm", "pi"]
    policy: "interactive"
```

Wichtig: Der Modellname in `config.toml` (`kimi-cli-default`) muss ein bekannter Alias im Router sein.

### Empfohlene Policy

Fuer die Kimi-CLI empfehlen wir `policy: interactive` (falls in der Config definiert)
oder `policy: standard` mit `fallback_on_5xx: true`. Kimi ist ein interaktiver Client;
Fallbacks sollen schnell greifen, damit die Nutzererfahrung stabil bleibt.

## Test

```bash
# Router starten
llm-router serve --config configs/router.local.yaml

# In anderem Terminal
kimi --model kimi-cli-default
```

## Streaming

Kimi nutzt `stream: true`. Der Router leitet den SSE-Stream direkt weiter – Tokens erscheinen sofort, nicht erst am Ende.
Wenn der letzte verfuegbare Backend-Versuch bei einem Streaming-Request mit
einem HTTP-Fehler endet, gibt der Router den Fehler ebenfalls als
`text/event-stream` mit einem `data: {...}`-Chunk zurueck. Dadurch sieht ein
SSE-Client den Fehler im erwarteten Stream-Format; die
`x-llm-router-returned-last-error`-Header bleiben zusaetzlich gesetzt.
