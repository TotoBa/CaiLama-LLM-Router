# Deployment mit systemd

Diese Anleitung beschreibt den dauerhaften Betrieb des Routers und der Ollama-Backends nach einem Neustart. Zugangsdaten gehoeren nicht in die Doku; Hostnamen, IPs und User werden in Beispielen als Platzhalter geschrieben.

## Varianten

| Variante | Einsatz |
|---|---|
| User-Service | Empfohlen, wenn Ollama-Cloud-Modelle unter einem bestehenden Benutzeraccount registriert sind. |
| System-Service | Geeignet, wenn der Router als eigener Systemdienst ohne Benutzer-Accountbindung laufen soll. |

Bei Ollama-Cloud-Modellen ist die User-Service-Variante oft praktischer, weil `ollama serve` dann denselben Account-Context nutzt wie `ollama pull`.

## VM + Pi Beispiel

Beispieltopologie:

| Rolle | Platzhalter | Dienst |
|---|---|---|
| Router-VM | `ROUTER_VM_IP` | Router + lokales Ollama |
| Pi-Backend | `OLLAMA_PI_IP` | Netzwerk-Ollama |

Router-Endpunkt fuer Clients:

```text
http://ROUTER_VM_IP:18080/v1
```

Backend-Endpunkte in der Router-Config:

```yaml
backends:
  vm:
    base_url: "http://127.0.0.1:11434/v1"
    priority: 10
    enabled: true

  pi:
    base_url: "http://OLLAMA_PI_IP:11434/v1"
    priority: 20
    enabled: true
```

Eine vollstaendige Vorlage liegt in `configs/router.vm-pi.example.yaml`.

Die Vorlage nutzt `routing_strategy: "round_robin"` und verteilt Requests auf alle verfuegbaren Backends. Fehlerhafte Backends werden nach zwei fehlgeschlagenen Versuchen fuer 300 Sekunden uebersprungen und danach automatisch wieder versucht.

## Installation auf der Router-VM

```bash
git clone git@github.com:TotoBa/LLM-Router.git
cd LLM-Router
python3 -m venv .venv
.venv/bin/pip install -e .
cp configs/router.vm-pi.example.yaml configs/router.local.yaml
cp .env.example .env
```

Danach `configs/router.local.yaml` anpassen:

- `OLLAMA_PI_IP` durch die Pi-IP ersetzen
- Modelle auf das setzen, was auf beiden Ollama-Hosts verfuegbar ist
- `server.host` auf `0.0.0.0`, wenn andere Rechner den Router erreichen sollen

Config pruefen:

```bash
.venv/bin/llm-router check-config --config configs/router.local.yaml
```

## Router als User-Service

```bash
mkdir -p ~/.config/systemd/user
cp systemd/ollama-user.service.example ~/.config/systemd/user/ollama.service
cp systemd/llm-router-user.service.example ~/.config/systemd/user/llm-router.service
```

In beiden Dateien `DEIN_USER` und Pfade anpassen. Danach:

```bash
systemctl --user daemon-reload
systemctl --user enable --now ollama.service
systemctl --user enable --now llm-router.service
```

Damit die User-Services auch ohne Login nach dem Boot laufen, muss ein Admin einmal Linger aktivieren:

```bash
sudo loginctl enable-linger DEIN_USER
```

Auf Systemen ohne `sudo` entsprechend als Root:

```bash
su -c 'loginctl enable-linger DEIN_USER'
```

Status und Logs:

```bash
systemctl --user status ollama.service llm-router.service
journalctl --user -u llm-router.service -f
```

## Router als System-Service

Wenn keine Accountbindung an Ollama noetig ist:

```bash
sudo cp systemd/llm-router.service.example /etc/systemd/system/llm-router.service
sudo nano /etc/systemd/system/llm-router.service
sudo systemctl daemon-reload
sudo systemctl enable --now llm-router.service
```

Status und Logs:

```bash
systemctl status llm-router.service
journalctl -u llm-router.service -f
```

## Pi-Ollama im Netzwerk

Auf dem Pi muss Ollama dauerhaft auf dem LAN-Interface lauschen:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo cp systemd/ollama-network-override.example.conf /etc/systemd/system/ollama.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl enable --now ollama.service
sudo systemctl restart ollama.service
```

Pruefen:

```bash
systemctl is-enabled ollama.service
systemctl is-active ollama.service
ss -ltnp | grep ':11434'
curl http://OLLAMA_PI_IP:11434/api/tags
curl http://OLLAMA_PI_IP:11434/v1/models
```

Der Socket sollte auf `*:11434` oder auf der LAN-IP lauschen. Kein Port-Forwarding ins Internet einrichten.

## Modelle synchronisieren

Auf jedem Ollama-Host dieselben Provider-Modelle bereitstellen, die in `models.*.provider_model` genutzt werden:

```bash
for model in \
  kimi-k2.6:cloud \
  deepseek-v4-pro:cloud \
  deepseek-v4-flash:cloud \
  gemma4:31b-cloud
do
  ollama pull "$model"
done

ollama list
```

Zusaetzliche Modelle duerfen installiert bleiben. Der Router nutzt nur die Modelle, die in der Config referenziert sind.

## Smoke-Tests

Router erreichbar:

```bash
curl http://ROUTER_VM_IP:18080/health
curl http://ROUTER_VM_IP:18080/v1/models
```

Antwort ueber primaeres Backend:

```bash
curl -D - http://ROUTER_VM_IP:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma4:31b-cloud",
    "messages": [{"role": "user", "content": "Gib nur ROUTER_OK aus."}],
    "max_tokens": 32,
    "stream": false
  }'
```

Wichtige Header:

```text
x-llm-router-backend: vm oder pi
x-llm-router-fallback-used: false
```

Fallback testen, indem das primaere Ollama kurz gestoppt wird:

```bash
systemctl --user stop ollama.service
```

Dann dieselbe Anfrage erneut senden. Erwartung:

```text
x-llm-router-backend: pi
x-llm-router-fallback-used: true
```

Primaeres Ollama danach wieder starten:

```bash
systemctl --user start ollama.service
```

Wenn `backend_cooldown_seconds: 300` gesetzt ist, wird das fehlerhafte Backend erst nach Ablauf des Cooldowns automatisch wieder in die Auswahl genommen.

## Reboot-Checkliste

Nach einem Neustart:

```bash
systemctl --user is-enabled ollama.service
systemctl --user is-active ollama.service
systemctl --user is-enabled llm-router.service
systemctl --user is-active llm-router.service
curl http://ROUTER_VM_IP:18080/health
```

Auf dem Pi:

```bash
systemctl is-enabled ollama.service
systemctl is-active ollama.service
curl http://OLLAMA_PI_IP:11434/api/tags
```
