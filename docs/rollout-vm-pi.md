# Beispiel-Rollout: Router-VM + Pi-Ollama

Diese Notiz dokumentiert einen uebertragbaren Rollout ohne Credentials. IPs, Usernamen und Modellnamen sind Platzhalter oder Beispiele und muessen an die eigene Umgebung angepasst werden.

## Zielbild

```text
Clients -> http://ROUTER_VM_IP:18080/v1
              |
              +-> vm backend: http://127.0.0.1:11434/v1
              +-> pi backend: http://OLLAMA_PI_IP:11434/v1
```

Die Router-VM hat Vorrang. Wenn das lokale Ollama auf der VM nicht erreichbar ist oder ein fallbackfaehiger Fehler auftritt, nutzt der Router das Pi-Backend.

Wenn `routing_strategy: "round_robin"` gesetzt ist, werden die Requests ueber VM und Pi verteilt. Faellt ein Host aus, wird auf einen anderen Host ausgewichen. Nach zwei fehlgeschlagenen Versuchen wird der betroffene Host fuer 300 Sekunden uebersprungen und danach automatisch wieder versucht.

## Vorbereitung

Auf der Router-VM:

```bash
git clone git@github.com:TotoBa/LLM-Router.git
cd LLM-Router
python3 -m venv .venv
.venv/bin/pip install -e .
cp configs/router.vm-pi.example.yaml configs/router.local.yaml
cp .env.example .env
```

In `configs/router.local.yaml`:

- `OLLAMA_PI_IP` ersetzen
- `provider_model`-Werte an `ollama list` anpassen
- `server.host: "0.0.0.0"` setzen, wenn Clients aus dem LAN zugreifen
- `routing_strategy: "round_robin"` aktiv lassen, wenn ueber alle Backends verteilt werden soll
- `runtime.request_timeout_seconds: null` aktiv lassen, damit lange LLM-Antworten nicht vom Router abgebrochen werden
- Modelle, die nur auf der VM laufen sollen, mit `backends: ["vm"]` eintragen

## Autostart auf der VM

Wenn Ollama-Modelle unter dem Benutzeraccount der VM verfuegbar sind, Ollama und Router als User-Services einrichten:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/ollama-user.service.example ~/.config/systemd/user/ollama.service
cp systemd/llm-router-user.service.example ~/.config/systemd/user/llm-router.service
```

In den Service-Dateien `DEIN_USER` und Pfade ersetzen. Danach:

```bash
systemctl --user daemon-reload
systemctl --user enable --now ollama.service
systemctl --user enable --now llm-router.service
```

Ollama sollte pro Host nur ein Modell gleichzeitig laden und nur einen Lauf gleichzeitig ausfuehren. Die Beispiel-Services setzen deshalb:

```ini
Environment=OLLAMA_MAX_LOADED_MODELS=1
Environment=OLLAMA_NUM_PARALLEL=1
Environment=OLLAMA_MAX_QUEUE=2
```

Damit duerfen maximal zwei weitere Requests in Ollama warten; bei mehr Last antwortet Ollama mit Ueberlastung und der Router kann fallbacken oder den letzten Backend-Fehler zurueckgeben.

Ein Admin aktiviert Linger, damit die Dienste nach einem Reboot ohne Login starten:

```bash
sudo loginctl enable-linger DEIN_USER
```

Falls `sudo` nicht verfuegbar ist:

```bash
su -c 'loginctl enable-linger DEIN_USER'
```

## Autostart auf dem Pi

Ollama soll auf dem Pi dauerhaft im LAN erreichbar sein:

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
```

## Modelle bereitstellen

Alle Provider-Modelle aus der Router-Config muessen auf allen referenzierten Backends verfuegbar sein:

```bash
for model in \
  kimi-k2.6:cloud \
  deepseek-v4-pro:cloud \
  deepseek-v4-flash:cloud \
  gemma4:31b-cloud \
  qwen3.5:397b-cloud \
  glm-5.1:cloud \
  minimax-m2.7:cloud \
  nemotron-3-super:cloud \
  gpt-oss:20b-cloud \
  qwen3-vl:4b
do
  ollama pull "$model"
done
```

Nur auf der VM:

```bash
for model in \
  gpt-oss-safeguard:20b \
  gemma4:e2b
do
  ollama pull "$model"
done
```

Zusaetzliche Modelle koennen installiert bleiben. Der Router routet nur auf die Aliase aus `configs/router.local.yaml`.

## Verifikation

Health und Modellliste:

```bash
curl http://ROUTER_VM_IP:18080/health
curl http://ROUTER_VM_IP:18080/v1/models
```

Normale Antwort:

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

Erwartete Header:

```text
x-llm-router-backend: vm oder pi
x-llm-router-fallback-used: false
```

Fallback provozieren:

```bash
systemctl --user stop ollama.service
```

Anfrage erneut senden. Erwartete Header:

```text
x-llm-router-backend: pi
x-llm-router-fallback-used: true
```

Primaeres Backend wieder starten:

```bash
systemctl --user start ollama.service
```

Bei `backend_cooldown_seconds: 300` bleibt das zuvor fehlerhafte Backend danach noch bis zum Ablauf des Cooldowns aus der Auswahl. Nach Ablauf der 300 Sekunden wird es automatisch wieder versucht.

## Betriebsbefehle

Router-VM:

```bash
systemctl --user status ollama.service llm-router.service
journalctl --user -u llm-router.service -f
curl http://ROUTER_VM_IP:18080/health
```

Pi:

```bash
systemctl status ollama.service
journalctl -u ollama.service -f
curl http://OLLAMA_PI_IP:11434/api/tags
```
