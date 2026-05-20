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

## Verifizierter Stand

- `uv run --extra dev pytest -q`: 55 Tests passed.
- `uv run --extra dev mypy src`: no issues found.
- `uv run --extra dev ruff check .`: All checks passed.

## Kimi-Handoff

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
