# Fallback

## Wann passiert Fallback?

Der Router versucht Backends in der konfigurierten Reihenfolge. Wenn ein Backend versagt, wird das nächste versucht.

### Fallback wird ausgelöst bei:

| Situation | HTTP-Code | Policy-Einstellung |
|---|---|---|
| Rate Limit | 429 | `fallback_on_limit` |
| Quota überschritten | 402 | `fallback_on_limit` |
| Limit-Erkennung in Body | 403 + Marker | `fallback_on_limit` |
| Verbindungsfehler | — | `retry_on_connection_error` |
| Timeout | — | `retry_on_timeout` |
| Server-Fehler | 5xx | `fallback_on_5xx` |

### Standardmaessig kein Fallback bei:

- 400 Bad Request (Client-Fehler)
- 404 Model not found, sofern `fallback_on_model_not_found: false`
- Unbekanntes Modell ohne Default (je nach `unknown_model_strategy`)

## Limit-Erkennung

Erkennung kombiniert Status-Codes und Body-Inhalt:

```yaml
limit_detection:
  status_codes: [402, 403, 429]
  body_markers:
    - "rate limit"
    - "quota"
    - "insufficient quota"
    - "too many requests"
```

## Retry, Fallback und Cooldown

- **Retry** = dasselbe Backend innerhalb desselben Requests nochmal versuchen
- **Fallback** = nächstes Backend in der Reihenfolge wählen
- **Cooldown** = ein fehlerhaftes Backend fuer eine konfigurierte Zeit aus der Auswahl nehmen

Beispiel:

```yaml
policies:
  standard:
    max_attempts_per_backend: 2
    max_backend_failures_before_cooldown: 2
    backend_cooldown_seconds: 300
```

Damit wird ein Backend bei Verbindungsfehlern bis zu zweimal im selben Request versucht. Nach zwei fehlgeschlagenen Backend-Versuchen wird es fuer 300 Sekunden uebersprungen. Danach wird es automatisch wieder versucht.

HTTP-Fehler wie 429 oder 5xx werden nicht auf demselben Backend wiederholt, sondern zaehlen als fehlgeschlagener Backend-Versuch und fuehren bei passender Policy direkt zum Fallback.

```
Anfrage -> Backend vm -> Connection Error
                     |
                     +-> Backend pi
```

## Beispiel-Log

```json
{"timestamp":1778962130.123,"request_id":"01HY...","client":"chess-system",
 "request_model":"chess-large","provider_model":"gemma4:31b-cloud","backend":"vm",
 "status_code":429,"limit_detected":true,"fallback_used":false,"duration_ms":823}

{"timestamp":1778962131.456,"request_id":"01HY...","client":"chess-system",
 "request_model":"chess-large","provider_model":"gemma4:31b-cloud","backend":"pi",
 "status_code":200,"limit_detected":false,"fallback_used":true,"duration_ms":5720}
```

## Troubleshooting

| Problem | Ursache | Lösung |
|---|---|---|
| Kein Fallback trotz 429 | `fallback_on_limit: false` | Policy anpassen |
| Endlosschleife | Falscher `base_url` | `llm-router check-config` |
| Alle Backends rot | Netzwerkproblem | `llm-router test-backends` |
| Ein Backend wird nicht genutzt | Cooldown aktiv | Nach `backend_cooldown_seconds` wird es automatisch wieder versucht |
