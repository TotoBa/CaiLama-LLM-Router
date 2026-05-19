# TODO - CaiLama-LLM-Router

Diese Datei sammelt operative Folgearbeiten fuer den eigenstaendigen
LLM-Router. Sie ersetzt keine Master-Planung und enthaelt keine Secrets.

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

## Kimi-Arbeitsregeln

- [ ] Vor Arbeitsbeginn `README.md`, diese `TODO.md`, `docs/architecture.md`,
  `docs/backends.md`, `docs/configuration.md`, `docs/fallback.md`,
  `docs/security.md` und `plan.md` lesen.
- [ ] Keine separaten Prompt- oder Handoff-Dateien anlegen. Operative
  Folgearbeit gehoert in diese `TODO.md`; groessere Konzepte duerfen nur als
  klar benannte `*.plan.md` abgelegt werden.
- [ ] Keine Schachproduktlogik in den Router verschieben.
- [ ] Live-Zugriffe auf Backends nur auf ausdruecklichen Auftrag.
- [ ] Abschlusspruefung ausfuehren: `pytest -q`, `ruff check .`,
  `mypy src`, `git status --short`, `git diff --check`. Nicht verfuegbare
  Tools im Abschluss klar nennen.
