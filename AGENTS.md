# AGENTS.md - CaiLama-LLM-Router

## Zweck

Dieses Repository enthaelt den eigenstaendigen LLM-Router fuer das CaiLama-
Oekosystem. Der Router stellt eine OpenAI-kompatible API bereit, verwaltet
Modell-Aliase, Backend-Routing, Fallbacks, Policies und JSONL-Betriebsdaten.

Der Router ist Infrastruktur. Er enthaelt keine Schachproduktlogik.

## Harte Regeln

- Keine Secrets, Tokens, API-Keys, lokalen IPs, produktiven URLs oder echten
  Zugangsdaten in Code, Doku, Beispiele oder Tests schreiben.
- Lokale Dateien wie `.env`, `configs/router.local.yaml`, Logs, `.venv` und
  Runtime-Daten sind nicht versionierbar.
- Beispielkonfigurationen muessen Platzhalter oder Env-Variablen nutzen.
- Keine Prompt-Inhalte oder Antwortinhalte in Logs aktivieren, ausser der
  Nutzer verlangt genau das fuer eine lokale Diagnose.
- Keine Live-Abfragen gegen Ollama, Cloud-Provider oder den laufenden Router,
  ausser der Nutzer verlangt das ausdruecklich.
- Keine Schachrollenlogik im Router einbauen. CaiLama formuliert Rollen und
  Systemprompts; der Router routet Modelle.

## Runtime- und Live-Betrieb

- Dieses Repository ist die Quellcodebasis. Der laufende Router kann aus einer
  separaten Runtime-Kopie ausserhalb der sich aendernden Codebasis gestartet
  werden.
- Runtime-Kopien sollen keine Git-Repositories sein. Sie duerfen nicht
  automatisch verschoben, geloescht oder normalisiert werden.
- Tests duerfen den laufenden Router nicht stoeren. Nutze fuer Tests eine
  separate Konfiguration und einen separaten Port.
- Offizielle Doku darf nur beschreiben, dass Live-Runtime ausserhalb des
  Code-Checkouts liegt. Keine echten lokalen Pfade dokumentieren.
- systemd-Beispiele duerfen Platzhalterpfade verwenden; echte lokale Units
  bleiben ausserhalb des Repos.

## Arbeitsweise

Vor Aenderungen:

1. `pwd` und `git rev-parse --show-toplevel` ausfuehren.
2. `git status --short` ausfuehren.
3. Betroffene README-/Doku-/Konfigurationsdateien lesen.

Bei Aenderungen:

1. Bestehende FastAPI-, Pydantic-, Typer- und Config-Strukturen nutzen.
2. Backends, Policies und Modell-Aliase als Konfiguration behandeln.
3. Fehlerverhalten mit Tests absichern, besonders Fallback, Cooldown,
   Streaming und OpenAI-kompatible Antwortformate.
4. Doku nur aktualisieren, wenn sie fuer Verhalten, Betrieb oder Sicherheit
   relevant ist.

Nach Aenderungen:

1. `pytest -q` oder gezielte Tests ausfuehren.
2. Bei Konfigurationsaenderungen `llm-router check-config --config ...`
   verwenden, wenn eine passende Testkonfiguration existiert.
3. `git diff --check` und `git status --short` ausfuehren.

## Schnittstellen

- CaiLama spricht den Router ueber `/v1` OpenAI-kompatibel an.
- Health- und Modell-Endpunkte duerfen leichtgewichtig bleiben.
- Router-Fehler muessen fuer Clients verwertbar bleiben; keine stillen
  Fallbacks, die falsche erfolgreiche Antworten vortaeuschen.
- Streaming ist ein Vertrag fuer Kimi CLI und aehnliche Clients.

## Dokumentation

- Ecosystem-Referenz: `https://cailama.org/reference.php`
- LLM-Einstieg: `https://cailama.org/llms.txt`
- Maschinenlesbare Referenz: `https://cailama.org/data/ecosystem.json`
