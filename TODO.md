# TODO - CaiLama-LLM-Router

Diese Datei sammelt operative Folgearbeiten fuer den eigenstaendigen
LLM-Router. Sie ersetzt keine Master-Planung und enthaelt keine Secrets.

## Ecosystem-Doku

- [x] Gemeinsame Human-/LLM-Referenz aus `CaiLama-Master` in `README.md`
  verlinkt: `https://cailama.org/reference.php`, `https://cailama.org/llms.txt`,
  `https://cailama.org/ecosystem-reference.md` und
  `https://cailama.org/data/ecosystem.json`.

## Betriebs- und Fallback-Haertung

- [x] Backend-Zustandsmodell pruefen: Round-Robin, Cooldown,
  Fehlerzaehlung und Recovery muessen fuer lokale und entfernte Backends
  nachvollziehbar bleiben.
    - Abgedeckt: Round-Robin-Verteilung, Cooldown-Skip, Cooldown-Recovery,
      Retry auf Connection-Error, 5xx-Fallback, exhausted backends.
- [x] Fallback-Verhalten dokumentieren und testen: Rate-Limits,
  Connection-Errors, 5xx-Antworten und ausgeschoepfte Backends muessen
  vorhersagbare Client-Antworten liefern.
    - Doku: `docs/fallback.md`. Tests: `tests/test_fallback_detection.py`,
      `tests/test_openai_chat_proxy.py`.
- [x] Exhausted-Backend-Verhalten pruefen: Policies muessen klar festlegen, ob
  der letzte Backend-Fehler unveraendert an Clients zurueckgegeben wird oder
  ein Router-Fehler entsteht.
    - `return_last_error_on_exhausted_backends` ist konfigurierbar und getestet.
- [x] Health- und Smoke-Checks fuer CaiLama-Verbraucher stabil halten:
  `/health`, `/v1/models` und `/v1/chat/completions` duerfen keine lokalen
  Provider-Secrets voraussetzen.
    - `/health` und `/v1/models` sind stateless. `smoke-test` nutzt die
      Router-URL ohne Backend-Secrets pro Request.
- [ ] JSONL-Logging regelmaessig gegen Datenschutzregeln pruefen:
  Prompt-Inhalte, Responses und Header bleiben standardmaessig aus Logs.
    - Kein Code-Change nötig; es fehlt ein automatisierter Test, der die
      JSONL-Output-Struktur auf sensitive Felder prueft.
- [ ] Router-Observability definieren: privacy-safe KPIs fuer Backend-Ausfaelle,
  Fallbacks, Cooldowns, Modellalias-Nutzung und Latenzen sammeln, ohne
  Prompt-/Response-Inhalte zu loggen.
    - `log_backend_state_change` fuer Cooldown-Events ist implementiert.
    - Offen: aggregierte In-Memory-Metriken Endpoint (`/metrics`) oder
      Prometheus-kompatible Metriken.

## CaiLama-Integration

- [x] Rollen-Aliase gegen CaiLama-Erwartungen abgleichen:
  `chess-router`, `chess-small`, `chess-large`, `chess-task`, `chess-coach`,
  `chess-analyst`, `chess-critic`, `chess-vision`, `chess-scribe`,
  `chess-researcher`.
    - Aliase in Beispiel-Configs und `test_chess_alias_examples` geprueft.
- [x] Dokumentieren, welche Alias-Policies fuer Training, Analyse,
  Recherche und Kimi-CLI empfohlen sind.
    - `docs/chess-system.md`: Empfohlene Policy-Tabelle fuer alle 10 Schach-Aliase.
    - `docs/kimi-cli.md`: Empfehlung fuer `interactive` oder `standard` mit
      `fallback_on_5xx: true`, Begruendung als interaktiver Client.
    - Kurze Empfehlung in `docs/chess-system.md` ergaenzen:
      `standard` fuer schnelle Tasks, `long_running` fuer Analyse/Coach,
      `interactive` fuer Kimi-CLI.
- [x] `researcher`- und `analyst`-Rollen fuer RAG-gestuetzte Analysepakete
  stabil halten; Retrieval-Kontext bleibt Aufgabe von CaiLama/CaiLama-Search,
  nicht des Routers.
    - Router delegiert nur Modell-Aliase; RAG-Logik ist nicht im Router.
- [x] Smoke-Test-Befehl fuer das CaiLama-Setup ohne echte Provider-Secrets
  dokumentieren.
    - `scripts/smoke-test.sh` und `scripts/check-config.sh` vorhanden;
      `check-config` prueft Env-Vars offline.

## Qualitaetssicherung

- [ ] `pytest`, `ruff` und `mypy` fuer betroffene Aenderungen ausfuehren.
    - Automatisiert: `pytest -q` und `ruff check .` gruen.
    - Offen: `mypy src` hat 6 praexistente Fehler (RootModel, YAML-Stubs,
      RouterError-Args); nicht aufgeschoben, aber nicht durch aktuelle
      Aenderungen verursacht.
- [x] Config-Beispiele pruefen, ohne echte lokale Configs zu committen.
    - `tests/test_config.py::test_chess_alias_examples_include_dedicated_roles`
      prueft `configs/router.chess-system.example.yaml` und
      `configs/router.vm-pi.example.yaml`.
- [x] Keine `.env`, Keys, Tokens oder lokalen Host-spezifischen Secrets
  versionieren.
    - `.gitignore` enthaelt `.env`, `configs/*.local.yaml`, Logs.

## Kimi-Handoff: aktuelle Prioritaeten

Arbeite diese Reihenfolge ab und halte den Router strikt als Infrastruktur:

1. [x] Fallback-Verhalten absichern: Round-Robin, Cooldown, Fehlerzaehlung,
   Recovery, Rate-Limits, Connection-Errors, 5xx und exhausted backends mit
   Tests und klaren Client-Antworten pruefen.
    - Round-Robin: vorhanden (`test_chat_completions_round_robin_distribution`).
    - Cooldown: vorhanden (`test_chat_completions_skips_backend_during_cooldown`).
    - Recovery nach Cooldown: neu (`test_chat_completions_recovered_backend_available_again`).
    - Retry auf Connection-Error: neu (`test_chat_completions_retries_connection_error`).
    - 5xx-Fallback: neu (`test_chat_completions_fallback_on_5xx`).
    - Exhausted backends: vorhanden (`test_chat_completions_returns_last_backend_error_when_exhausted`).
2. [x] Rollen- und Modell-Aliase gegen CaiLama-Erwartungen abgleichen:
   `chess-router`, `chess-small`, `chess-large`, `chess-task`,
   `chess-coach`, `chess-analyst`, `chess-critic`, `chess-vision`,
   `chess-scribe`, `chess-researcher`.
    - Aliase sind in beiden Example-Configs vorhanden (`test_chess_alias_examples_include_dedicated_roles`).
    - `unknown_model_strategy: passthrough` ist jetzt validiert und getestet;
      das erlaubt dynamische Rollen ohne harte Router-Konfiguration.
    - Bugfix: `resolve_backend_model` gibt jetzt den Alias selbst zurück, wenn kein
      Router-Eintrag existiert, anstatt einen KeyError zu werfen.
3. [x] Privacy-safe Observability definieren und vorbereiten: Backend-Ausfaelle,
   Fallbacks, Cooldowns, Alias-Nutzung und Latenzen erfassen, ohne Prompt-,
   Response- oder Header-Inhalte zu loggen.
    - `log_backend_state_change` eingefuehrt: erzeugt JSONL-Events bei Cooldown-Starts
      (`event: backend_state_change`, `state: cooldown_started`, `cooldown_seconds`)
      ohne jegliche Prompt-/Response-Inhalte.
    - Neu: `tests/test_logging_jsonl.py` – 3 Tests:
      - `test_json_formatter_outputs_dict_directly`
      - `test_log_backend_state_change_no_sensitive_content`
      - `test_log_request_privacy_defaults`
4. [x] Smoke-/Config-Pruefung ohne echte Provider-Secrets dokumentieren und
   automatisierbar halten.
    - `check-config` erweitert: prueft referenzierte Env-Vars (`api_key_env`)
      ohne Live-Anfragen.
    - Tests: `tests/test_cli.py` – 4 Tests fuer `_check_env_vars`.
    - Dokumentation: `docs/configuration.md` erweitert.

## Naester Arbeitsschritt

- [ ] `/metrics` Endpunkt fuer privacy-safe In-Memory-Observability:
  Backend-Ausfaelle, Fallbacks, Cooldowns, Alias-Nutzung, Latenzen.
  Keine Prompt-/Response-Inhalte. JSON-Output fuer einfache Integration.

## Einheitlicher Kimi-Prompt

```text
Du arbeitest im aktuellen CaiLama-Repository. Lies zuerst AGENTS.md, README.md
und TODO.md vollstaendig. Wenn es MODULES.md oder passende docs/ bzw.
Modul-READMEs gibt, lies die fuer den naechsten offenen Punkt relevanten
Dateien ebenfalls.

Arbeite danach ausschliesslich die offenen Punkte im Abschnitt
"Kimi-Handoff: aktuelle Prioritaeten" der TODO.md ab. Beginne mit dem ersten
offenen Punkt, mache eine kleine, testbare Aenderung, verifiziere sie und
aktualisiere danach TODO.md.

Harte Vorgaben:
- Halte dich strikt an AGENTS.md.
- Keine Secrets, Tokens, lokalen Pfade oder produktiven Zugangsdaten ausgeben
  oder committen.
- Keine Live-Zugriffe, keine echten externen Dienste und keine laufenden
  Runtime-Services benutzen, ausser der Nutzer verlangt es ausdruecklich.
- Vorhandene Module, Tests und lokale Architektur wiederverwenden; keine
  Parallelstruktur fuer vorhandene Logik bauen.
- Keine separaten Handoff- oder Prompt-Dateien anlegen. Operative Folgearbeit
  gehoert in TODO.md.

Nach jeder erledigten Aufgabe:
1. Den konkreten TODO-Punkt als erledigt markieren oder einen neuen offenen
   Folgepunkt ergaenzen.
2. Nur die direkt betroffene Doku knapp nachziehen.
3. Gezielt passende Tests ohne Live-Abhaengigkeiten ausfuehren.
4. `git diff --check` und `git status --short` ausfuehren.
5. Commit und Push im aktuellen Repository ausfuehren.
```

## Kimi-Arbeitsregeln

- [x] Vor Arbeitsbeginn `AGENTS.md`, `README.md`, diese `TODO.md`,
  `docs/architecture.md`, `docs/backends.md`, `docs/configuration.md`,
  `docs/fallback.md`, `docs/security.md` und `plan.md` lesen.
- [x] Keine separaten Prompt- oder Handoff-Dateien anlegen. Operative
  Folgearbeit gehoert in diese `TODO.md`; groessere Konzepte duerfen nur als
  klar benannte `*.plan.md` abgelegt werden.
- [x] Keine Schachproduktlogik in den Router verschieben.
- [x] Live-Zugriffe auf Backends nur auf ausdruecklichen Auftrag.
- [x] Abschlusspruefung ausfuehren: `pytest -q`, `ruff check .`,
  `mypy src`, `git status --short`, `git diff --check`. Nicht verfuegbare
  Tools im Abschluss klar nennen.
