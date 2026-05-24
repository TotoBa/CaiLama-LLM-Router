# TODO - CaiLama-LLM-Router

Diese Datei sammelt operative Folgearbeiten fuer den eigenstaendigen
LLM-Router. Sie ersetzt keine Master-Planung und enthaelt keine Secrets.

Erledigte TODOs werden nur auf ausdrueckliche Nutzeranweisung entfernt; TODO
ist nicht gleich Handoff. Diese Bereinigung wurde am 2026-05-20 auf
ausdrueckliche Nutzeranweisung durchgefuehrt.

## Arbeitskontext

Vor Arbeitsbeginn lesen:

- `AGENTS.md`, `README.md`, diese `TODO.md`.
- `docs/architecture.md`, `docs/backends.md`, `docs/configuration.md`,
  `docs/fallback.md`, `docs/security.md` und `plan.md`.
- Fuer Ecosystem-Kontext: `https://cailama.org/reference.php`,
  `https://cailama.org/llms.txt`,
  `https://cailama.org/ecosystem-reference.md` und
  `https://cailama.org/data/ecosystem.json`.

## Naechster Arbeitsschritt

Aktueller Stand 2026-05-22: Fuer den Router ist der bisherige Aufgabenplan abgearbeitet.
Eine neue Infrastruktur-Welle wird fuer Betriebsrobustheit und Transparenz
aufgenommen:

- [x] Backend-API-Key-Weitergabe aktivieren und testen: `api_key_env` muss
  ueber `resolve_api_key()` in den `Authorization`-Header fuer Backend-Requests
  fliessen, ohne Secrets zu loggen. Betroffene Dateien:
  `src/llm_router/openai_compat.py`, `src/llm_router/config.py`.
  Tests decken vorhandene und fehlende Env-Variable ab; Test-Key erscheint
  nicht in der Router-Antwort.
- [x] Privacy-safe Token-/Usage-Metriken ergaenzen: OpenAI-kompatibles `usage`
  aus Antworten aggregieren, `/metrics` JSON und Prometheus-Text erweitern.
  Keine Prompt- oder Response-Inhalte speichern.
  Update 2026-05-23: Reasoning-/Thinking-Tokens werden zusaetzlich aus
  `usage.reasoning_tokens`, `usage.thinking_tokens`,
  `completion_tokens_details.reasoning_tokens` oder
  `output_tokens_details.reasoning_tokens` aggregiert. `output_tokens` und
  `thinking_tokens` stehen als benchmarkfreundliche Aliasfelder in Metrics,
  CLI-Usage und Benchmark-Export.
- [x] Optionalen `llm-router usage` Diagnosebefehl ergaenzen:
  `llm-router usage --metrics-url URL` zeigt Requests, Fallbacks, Latenz,
  Alias-/Backend-Verteilung und Token-Gesamtwerte lesbar an.
  Implementiert in `src/llm_router/cli.py`; `_format_usage()` ist einzeln testbar.
- [x] Benchmark-Export fuer den Master vorbereiten: eine secretfreie
  Zusammenfassung aus `/metrics` oder CLI liefern, die Git-Ref, Alias,
  Backend, Latenz, Fehler-/Fallback-Rate, Cooldowns und Usage-Werte ausweist.
  Keine Prompts, Responses, Provider-Keys oder lokalen Runtime-Pfade.
  Implementiert als `llm-router benchmark-export --metrics-url URL --git-ref REF`
  mit Auto-Detection des Git-Refs via `git rev-parse HEAD`.
- [x] Spaetere spezialisierte Modellbackends als generischen Router-Fall
  vorbereiten: spezialisierte Modelle duerfen nur als Backend-/Alias-
  Konfiguration erscheinen, muessen gegen dieselben Benchmarks antreten und
  duerfen keine Schachproduktlogik in den Router ziehen.
  `endpoint_path` in `BackendConfig` ermoeglicht beliebige Backend-Endpoints
  (z.B. Bildgenerierung / Embeddings) als reine YAML-Konfiguration, ohne
  dass der Router produktspezifische Logik anfaesst.

- [x] Observability fuer Cooldowns schaerfen: `cooldowns` in `/metrics` zaehlt
  nur noch tatsaechlich gestartete Backend-Cooldown-Transitionen. Einzelne
  Backend-Fehler bleiben separat unter `backend_failures` sichtbar.
- [x] Streaming-Fehlerbehandlung klaeren und implementieren: `500`-Antworten
  innerhalb eines `stream: true`-Flows werden transparent durchgereicht, aber
  Clients erkennen den Router-Header `x-llm-router-returned-last-error` nicht im
  SSE-Format. Entscheiden und testen, ob ein `data: {"error": ...}` Chunk oder
  ein regulaerer `503`-Abbruch der richtige Vertrag ist.
- [x] Config-Hot-Reload pruefen: `reload_config_on_request: true` ist definiert,
  aber die Config wird beim App-Start einmalig geladen. Entscheiden, ob
  Hot-Reload sinnvoll ist, und `_get_config()` entsprechend testen und
  implementieren.
- [x] Backend-spezifisches Modell-Mapping per Alias absichern:
  `backend_models` existiert in `ModelRouteConfig`, aber es fehlt ein echter
  Test fuer unterschiedliche Provider-Modellnamen je Backend, z.B.
  `chess-small` auf `vm` und `pi`.
- [x] Optionalen Prometheus-Exporter bewerten: `/metrics` liefert aktuell JSON.
  Wenn noetig, zusaetzliches `text/plain`-Format bereitstellen.
- [x] `mypy src` bereinigen: bekannte Typfehler bei RootModel-Typen,
  YAML-Stubs und RouterError-Argumentreihenfolge beheben.
- [x] Beispiel-Aliase und Docker-Beispiel auf aktuellen Teststand bringen:
  `chess-small` nutzt `gemma4:31b-cloud`; `chess-large`, `chess-task`,
  `chess-critic` und `chess-researcher` nutzen `kimi-k2.6:cloud`.
  `deepseek-v4-pro:cloud` ist aus den aktiven Beispielkonfigurationen und
  Config-Tests entfernt. `docker/Dockerfile` baut aus dem Repo-Root-Kontext.
- [x] Dual-Ollama-VM-Konfiguration fuer vollstaendige Benchmarks vorbereiten:
  `configs/router.vm-dual-ollama.example.yaml` routet Benchmarkmodelle ueber
  zwei lokale VM-Ollama-Container (`ollama-vm-a`, `ollama-vm-b`) statt ueber
  den Pi. `docker/docker-compose.dual-ollama.example.yml` startet zwei
  lokale Ollama-Instanzen auf Loopback-Ports und nimmt API-Keys nur ueber
  lokale Env-Variablen (`OLLAMA_VM_A_API_KEY`, `OLLAMA_VM_B_API_KEY`) auf.
  Die zusaetzlichen Testmodelle `deepseek-v4-pro:cloud`,
  `hemanth/chessplayer:latest`, `starling-lm:7b`, `gemma4:e2b` und
  `gemma4:e4b` sowie `qwen3.6:27b` sind als Aliase vorbereitet.
  Cloud-Aliase gehen ueber die Docker-Ollamas; lokale Aliase gehen nur ueber
  den vorhandenen Host-Ollama `127.0.0.1:11434`, damit lokale Modelle nur
  einmal geladen werden muessen. Keine Keys im Repo.
- [x] Thinking-Mode-Benchmarkvarianten vorbereiten: `ModelRouteConfig`
  unterstuetzt jetzt `request_overrides`, damit Ollama-kompatible
  Requestfelder wie `think: false`, `think: true`, `think: "low"`,
  `think: "medium"` und `think: "high"` als eigene Aliase getestet werden
  koennen. `model`, `messages` und `stream` sind reserviert und werden in der
  Config-Validierung abgelehnt. Die VM-Dual-Ollama-Beispielconfig enthaelt
  Qwen-3.6-27B-Aliase fuer alle genannten Thinking-Modi.

## Verifizierter Stand

- `uv run --extra dev pytest -q`: 69 Tests passed.
- `uv run --extra dev mypy src`: no issues found.
- `uv run --extra dev ruff check .`: All checks passed.

## Kimi-Handoff

Stand 2026-05-23: Alle Punkte unter "Naechster Arbeitsschritt" sind umgesetzt.
Zusatzstand: Chess-Aliase sind fuer die naechste Testphase auf Gemma/Kimi
umgestellt, `deepseek-v4-pro:cloud` ist aus Beispielconfigs und Tests entfernt,
das Docker-Beispiel baut wieder aus dem Repo-Root-Kontext, und die
Benchmark-/Usage-Metriken liefern jetzt auch `output_tokens`,
`reasoning_tokens` und `thinking_tokens`, sofern Backends diese Usage-Daten
bereitstellen. Keine direkte Router-Folgearbeit beginnen, bis ein Live-Smoke,
ein neuer Benchmark-Bedarf oder ein neues Backend-/Alias-Profil beauftragt
wird. Keine echten Backends
oder Live-Runtime-Services ohne ausdruecklichen Nutzerauftrag verwenden.

Arbeite die Punkte unter "Naechster Arbeitsschritt" von oben nach unten ab.
Der Router bleibt Infrastruktur: keine Schachproduktlogik, keine RAG-Logik,
keine Prompt-Inhalte in Logs.

```text
Du arbeitest im aktuellen CaiLama-LLM-Router-Repository. Lies zuerst
AGENTS.md, README.md und TODO.md vollstaendig. Lies danach die fuer den ersten
offenen Punkt relevanten Dateien unter docs/ und src/.

Arbeite danach ausschliesslich die offenen Punkte im Abschnitt
"Naechster Arbeitsschritt" der TODO.md ab. Beginne mit dem ersten offenen
Punkt, mache eine kleine, testbare Aenderung, verifiziere sie und aktualisiere
danach TODO.md.

Harte Vorgaben:
- Halte dich strikt an AGENTS.md.
- Keine Secrets, Tokens, lokalen Pfade oder produktiven Zugangsdaten ausgeben
  oder committen.
- Keine Live-Zugriffe, keine echten externen Dienste und keine laufenden
  Runtime-Services benutzen, ausser der Nutzer verlangt es ausdruecklich.
- Vorhandene FastAPI-, Pydantic-, Typer- und Config-Strukturen
  wiederverwenden; keine Parallelstruktur fuer vorhandene Logik bauen.
- Keine separaten Handoff- oder Prompt-Dateien anlegen. Operative Folgearbeit
  gehoert in TODO.md.
- Erledigte TODO-Punkte nicht loeschen, ausser der Nutzer fordert diese
  Bereinigung ausdruecklich an. TODO ist nicht gleich Handoff.

Nach jeder erledigten Aufgabe:
1. Den konkreten TODO-Punkt als erledigt markieren oder einen neuen offenen
   Folgepunkt ergaenzen.
2. Nur die direkt betroffene Doku knapp nachziehen.
3. Gezielt passende Tests ohne Live-Abhaengigkeiten ausfuehren.
4. `pytest -q`, `ruff check .`, `git diff --check` und `git status --short`
   ausfuehren; `mypy src` nur dann gruen erwarten, wenn der mypy-Punkt
   bearbeitet wurde.
5. Commit und Push im aktuellen Repository ausfuehren.
```

## Codex-Arbeitsregeln

- [ ] Vor Arbeitsbeginn die Dateien aus "Arbeitskontext" lesen.
- [ ] Keine separaten Prompt- oder Handoff-Dateien anlegen. Operative
  Folgearbeit gehoert in diese `TODO.md`; groessere Konzepte duerfen nur als
  klar benannte `*.plan.md` abgelegt werden.
- [ ] Keine Schachproduktlogik in den Router verschieben.
- [ ] Live-Zugriffe auf Backends nur auf ausdruecklichen Auftrag.
- [ ] Abschlusspruefung ausfuehren: `pytest -q`, `ruff check .`,
  `mypy src`, `git status --short`, `git diff --check`. Nicht verfuegbare
  Tools oder bekannte praexistente Fehler im Abschluss klar nennen.
