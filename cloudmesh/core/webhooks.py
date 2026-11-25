import json, os, subprocess, time
import urllib.parse

from cloudmesh.core.paths import data_dir

_INITIAL_DATA_DIR = str(data_dir())
DATA_DIR = _INITIAL_DATA_DIR


def _data_dir():
    return DATA_DIR if DATA_DIR != _INITIAL_DATA_DIR else str(data_dir())


def _webhooks_file():
    return os.path.join(_data_dir(), "webhooks.json")

def _load_webhooks():
    p = _webhooks_file()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"webhooks": [], "log": []}

def _save_webhooks(data):
    os.makedirs(_data_dir(), exist_ok=True)
    with open(_webhooks_file(), "w") as f:
        json.dump(data, f, indent=2)

def _valid_webhook_url(url):
    if not isinstance(url, str) or url.startswith("-") or any(ch in url for ch in ("\n", "\r", "\x00")):
        return False
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)

def list_webhooks():
    data = _load_webhooks()
    return data.get("webhooks", [])

def add_webhook(name, url, webhook_type="custom", events=None, chat_id=None):
    if not _valid_webhook_url(url):
        return f"Invalid webhook URL (must be http:// or https://): {url}"
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

def _deliver_webhook(wh, message, event_type, data):
    url = wh.get("url", "")
    if not _valid_webhook_url(url):
        return {"webhook": wh.get("name", "?"), "status": "failed: invalid URL"}
    wh_type = wh.get("type", "custom")
    try:
        if wh_type == "discord":
            payload = json.dumps({"content": f"**CloudMesh** [{event_type}]\n{message}"})
            cmd = ["curl", "-s", "-f", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload, "--", url]
        elif wh_type == "slack":
            payload = json.dumps({"text": f"*CloudMesh* [{event_type}]\n{message}"})
            cmd = ["curl", "-s", "-f", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload, "--", url]
        elif wh_type == "telegram":
            chat_id = wh.get("chat_id") or ""
            if not chat_id:
                return {"webhook": wh["name"], "status": "failed: chat_id required for Telegram"}
            cmd = ["curl", "-s", "-f", "-X", "POST", "-d", f"chat_id={chat_id}&text=CloudMesh [{event_type}]: {message}", "--", f"{url}/sendMessage"]
        else:
            payload = json.dumps({"event": event_type, "message": message, "source": "cloudmesh", "time": time.strftime("%Y-%m-%d %H:%M:%S")})
            cmd = ["curl", "-s", "-f", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload, "--", url]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if getattr(result, "returncode", 0) != 0:
            err = (getattr(result, "stderr", "") or f"exit {result.returncode}").strip()
            return {"webhook": wh["name"], "status": f"failed: {err}"}

        data["log"].append({
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "webhook": wh["name"],
            "event": event_type,
            "message": message[:100]
        })
        return {"webhook": wh["name"], "status": "sent"}
    except Exception as e:
        return {"webhook": wh["name"], "status": f"failed: {e}"}

def send_webhook(message, event_type="alert"):
    data = _load_webhooks()
    sent = []
    for wh in data.get("webhooks", []):
        if not wh.get("enabled", True):
            continue
        if event_type not in wh.get("events", []):
            continue
        sent.append(_deliver_webhook(wh, message, event_type, data))

    data["log"] = data["log"][-100:]
    _save_webhooks(data)
    return sent

def test_webhook(name):
    data = _load_webhooks()
    matches = [wh for wh in data.get("webhooks", []) if wh.get("name") == name]
    if not matches:
        return [{"webhook": name, "status": "not found"}]
    sent = [_deliver_webhook(wh, "Test notification from CloudMesh", "test", data) for wh in matches]
    data["log"] = data["log"][-100:]
    _save_webhooks(data)
    return sent

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
