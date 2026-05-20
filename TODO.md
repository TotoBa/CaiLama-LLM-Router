# TODO - CaiLama-LLM-Router

Diese Datei sammelt operative Folgearbeiten fuer den eigenstaendigen
LLM-Router. Sie ersetzt keine Master-Planung und enthaelt keine Secrets.

## Ecosystem-Doku

- [x] Gemeinsame Human-/LLM-Referenz aus `CaiLama-Master` in `README.md`
  verlinkt: `https://cailama.org/reference.php`, `https://cailama.org/llms.txt`,
  `https://cailama.org/ecosystem-reference.md` und
  `https://cailama.org/data/ecosystem.json`.

## Betriebs- und Fallback-Haertung

- [ ] Backend-Zustandsmodell pruefen: Round-Robin, Cooldown,
  Fehlerzaehlung und Recovery muessen fuer lokale und entfernte Backends
  nachvollziehbar bleiben.
- [ ] Fallback-Verhalten dokumentieren und testen: Rate-Limits,
  Connection-Errors, 5xx-Antworten und ausgeschoepfte Backends muessen
  vorhersagbare Client-Antworten liefern.
- [ ] Exhausted-Backend-Verhalten pruefen: Policies muessen klar festlegen, ob
  der letzte Backend-Fehler unveraendert an Clients zurueckgegeben wird oder
  ein Router-Fehler entsteht.
- [ ] Health- und Smoke-Checks fuer CaiLama-Verbraucher stabil halten:
  `/health`, `/v1/models` und `/v1/chat/completions` duerfen keine lokalen
  Provider-Secrets voraussetzen.
- [ ] JSONL-Logging regelmaessig gegen Datenschutzregeln pruefen:
  Prompt-Inhalte, Responses und Header bleiben standardmaessig aus Logs.
- [ ] Router-Observability definieren: privacy-safe KPIs fuer Backend-Ausfaelle,
  Fallbacks, Cooldowns, Modellalias-Nutzung und Latenzen sammeln, ohne
  Prompt-/Response-Inhalte zu loggen.

## CaiLama-Integration

- [ ] Rollen-Aliase gegen CaiLama-Erwartungen abgleichen:
  `chess-router`, `chess-small`, `chess-large`, `chess-task`, `chess-coach`,
  `chess-analyst`, `chess-critic`, `chess-vision`, `chess-scribe`,
  `chess-researcher`.
- [ ] Dokumentieren, welche Alias-Policies fuer Training, Analyse,
  Recherche und Kimi-CLI empfohlen sind.
- [ ] `researcher`- und `analyst`-Rollen fuer RAG-gestuetzte Analysepakete
  stabil halten; Retrieval-Kontext bleibt Aufgabe von CaiLama/CaiLama-Search,
  nicht des Routers.
- [ ] Smoke-Test-Befehl fuer das CaiLama-Setup ohne echte Provider-Secrets
  dokumentieren.

## Qualitaetssicherung

- [ ] `pytest`, `ruff` und `mypy` fuer betroffene Aenderungen ausfuehren.
- [ ] Config-Beispiele pruefen, ohne echte lokale Configs zu committen.
- [ ] Keine `.env`, Keys, Tokens oder lokalen Host-spezifischen Secrets
  versionieren.

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
3. Privacy-safe Observability definieren und vorbereiten: Backend-Ausfaelle,
   Fallbacks, Cooldowns, Alias-Nutzung und Latenzen erfassen, ohne Prompt-,
   Response- oder Header-Inhalte zu loggen.
4. Smoke-/Config-Pruefung ohne echte Provider-Secrets dokumentieren und
   automatisierbar halten.

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

- [ ] Vor Arbeitsbeginn `AGENTS.md`, `README.md`, diese `TODO.md`,
  `docs/architecture.md`, `docs/backends.md`, `docs/configuration.md`,
  `docs/fallback.md`, `docs/security.md` und `plan.md` lesen.
- [ ] Keine separaten Prompt- oder Handoff-Dateien anlegen. Operative
  Folgearbeit gehoert in diese `TODO.md`; groessere Konzepte duerfen nur als
  klar benannte `*.plan.md` abgelegt werden.
- [ ] Keine Schachproduktlogik in den Router verschieben.
- [ ] Live-Zugriffe auf Backends nur auf ausdruecklichen Auftrag.
- [ ] Abschlusspruefung ausfuehren: `pytest -q`, `ruff check .`,
  `mypy src`, `git status --short`, `git diff --check`. Nicht verfuegbare
  Tools im Abschluss klar nennen.
