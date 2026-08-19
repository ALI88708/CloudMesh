import json, os, subprocess, time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def _webhooks_file():
    return os.path.join(DATA_DIR, "webhooks.json")

def _load_webhooks():
    p = _webhooks_file()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"webhooks": [], "log": []}

def _save_webhooks(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_webhooks_file(), "w") as f:
        json.dump(data, f, indent=2)

def list_webhooks():
    data = _load_webhooks()
    return data.get("webhooks", [])

def add_webhook(name, url, webhook_type="custom", events=None, chat_id=None):
    data = _load_webhooks()
    webhook = {
        "name": name,
        "url": url,
        "type": webhook_type,
        "events": events or ["alert", "error"],
        "chat_id": chat_id,
        "enabled": True,
        "created": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    data["webhooks"].append(webhook)
    _save_webhooks(data)
    return f"Webhook '{name}' added"

def remove_webhook(name):
    data = _load_webhooks()
    data["webhooks"] = [w for w in data["webhooks"] if w.get("name") != name]
    _save_webhooks(data)
    return f"Webhook '{name}' removed"

def send_webhook(message, event_type="alert"):
    data = _load_webhooks()
    sent = []
    for wh in data.get("webhooks", []):
        if not wh.get("enabled", True):
            continue
        if event_type not in wh.get("events", []):
            continue

        url = wh["url"]
        wh_type = wh.get("type", "custom")

        try:
            if wh_type == "discord":
                payload = json.dumps({"content": f"**CloudMesh** [{event_type}]\n{message}"})
                cmd = ["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload, url]
            elif wh_type == "slack":
                payload = json.dumps({"text": f"*CloudMesh* [{event_type}]\n{message}"})
                cmd = ["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload, url]
            elif wh_type == "telegram":
                chat_id = wh.get("chat_id") or ""
                if not chat_id:
                    sent.append({"webhook": wh["name"], "status": "failed: chat_id required for Telegram"})
                    continue
                cmd = ["curl", "-s", "-X", "POST", f"{url}/sendMessage", "-d", f"chat_id={chat_id}&text=CloudMesh [{event_type}]: {message}"]
            else:
                payload = json.dumps({"event": event_type, "message": message, "source": "cloudmesh", "time": time.strftime("%Y-%m-%d %H:%M:%S")})
                cmd = ["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload, url]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            sent.append({"webhook": wh["name"], "status": "sent"})

            data["log"].append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "webhook": wh["name"],
                "event": event_type,
                "message": message[:100]
            })
        except Exception as e:
            sent.append({"webhook": wh["name"], "status": f"failed: {e}"})

    data["log"] = data["log"][-100:]
    _save_webhooks(data)
    return sent

def test_webhook(name):
    return send_webhook("Test notification from CloudMesh", "test")

def webhook_log(limit=20):
    data = _load_webhooks()
    return data.get("log", [])[-limit:]

def enable_webhook(name):
    data = _load_webhooks()
    for wh in data["webhooks"]:
        if wh["name"] == name:
            wh["enabled"] = True
            _save_webhooks(data)
            return f"Webhook '{name}' enabled"
    return f"Webhook '{name}' not found"

def disable_webhook(name):
    data = _load_webhooks()
    for wh in data["webhooks"]:
        if wh["name"] == name:
            wh["enabled"] = False
            _save_webhooks(data)
            return f"Webhook '{name}' disabled"
    return f"Webhook '{name}' not found"
