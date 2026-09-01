import json
import logging
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = {"info": 0, "warning": 1, "critical": 2}
DEFAULT_COOLDOWN = 300


def _effective_severity(severity, value, threshold, operator):
    base = SEVERITY_LEVELS.get(severity, 1)
    try:
        over = value > threshold if operator in ("gt", "gte") else False
    except TypeError:
        return severity
    if over and threshold and value >= threshold * 1.2 and base < SEVERITY_LEVELS["critical"]:
        base += 1
    return list(SEVERITY_LEVELS.keys())[base]


class AlertManager:
    def __init__(self, resource_monitor, base_dir=None, notifier=None):
        self.monitor = resource_monitor
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        self.base_dir = Path(base_dir)
        self.alerts_file = self.base_dir / "alerts.json"
        self._rules = []
        self._history = []
        self._last_notified = {}
        self.notifier = notifier
        self._load()

    def _load(self):
        if self.alerts_file.exists():
            try:
                data = json.loads(self.alerts_file.read_text())
                self._rules = data.get("rules", [])
                self._history = data.get("history", [])
                self._last_notified = data.get("last_notified", {})
            except Exception as e:
                logger.error("Failed to load alerts: %s", e)
                self._rules = []
                self._history = []
                self._last_notified = {}

    def _save(self):
        data = {
            "rules": self._rules,
            "history": self._history[-500:],
            "last_notified": self._last_notified,
        }
        self.alerts_file.write_text(json.dumps(data, indent=2))

    def add_rule(self, name, metric, threshold, operator="gt", server=None,
                 severity="warning", cooldown=DEFAULT_COOLDOWN):
        if severity not in SEVERITY_LEVELS:
            severity = "warning"
        rule = {
            "name": name,
            "metric": metric,
            "threshold": threshold,
            "operator": operator,
            "server": server,
            "severity": severity,
            "cooldown": max(int(cooldown), 0),
            "enabled": True,
        }
        self._rules.append(rule)
        self._save()
        return rule

    def remove_rule(self, name):
        self._rules = [r for r in self._rules if r["name"] != name]
        self._save()

    def list_rules(self):
        return self._rules

    def _check_condition(self, value, threshold, operator):
        if value is None:
            return False
        if operator == "gt":
            return value > threshold
        elif operator == "lt":
            return value < threshold
        elif operator == "gte":
            return value >= threshold
        elif operator == "lte":
            return value <= threshold
        elif operator == "eq":
            return value == threshold
        return False

    def _cooldown_key(self, rule_name, server):
        return f"{rule_name}|{server}"

    def _cooldown_passed(self, key, rule):
        last = self._last_notified.get(key)
        if not last:
            return True
        cooldown = max(int(rule.get("cooldown", DEFAULT_COOLDOWN)), 0)
        return (time.time() - last) >= cooldown

    def _format_notification(self, alert):
        sev = alert["severity"].upper()
        line = f"[{sev}] CloudMesh Alert - {alert['rule']} on {alert['server']}"
        line += f" - {alert['metric']}={alert['value']}% (threshold {alert['threshold']}%)"
        return line

    def check_alerts(self, server_names=None, send_notifications=True):
        if server_names is None:
            server_names = list(dict.fromkeys(r.get("server") for r in self._rules if r.get("server")))
            if not server_names:
                return []

        triggered = []
        for name in server_names:
            try:
                metrics = self.monitor.get_all_metrics(name)
                if metrics is None:
                    continue

                for rule in self._rules:
                    if not rule.get("enabled", True):
                        continue
                    if rule.get("server") and rule["server"] != name:
                        continue

                    metric_name = rule["metric"]
                    value = None
                    if metric_name == "cpu":
                        value = metrics.get("cpu_percent")
                    elif metric_name == "ram":
                        ram = metrics.get("ram") or {}
                        value = ram.get("percent")
                    elif metric_name == "disk":
                        disk = metrics.get("disk") or {}
                        value = disk.get("percent")
                    elif metric_name == "load":
                        value = metrics.get("load")
                    elif metric_name == "gpu":
                        gpu = metrics.get("gpu") or {}
                        value = gpu.get("utilization")

                    if self._check_condition(value, rule["threshold"], rule["operator"]):
                        severity = _effective_severity(
                            rule.get("severity", "warning"), value, rule["threshold"], rule["operator"]
                        )
                        alert = {
                            "rule": rule["name"],
                            "server": name,
                            "metric": metric_name,
                            "value": value,
                            "threshold": rule["threshold"],
                            "operator": rule["operator"],
                            "severity": severity,
                            "timestamp": datetime.now().isoformat(),
                        }
                        triggered.append(alert)
                        self._history.append(alert)

                        key = self._cooldown_key(rule["name"], name)
                        if self._cooldown_passed(key, rule):
                            self._last_notified[key] = time.time()
                            if send_notifications:
                                self._send_notification(alert)
            except Exception as e:
                logger.warning("Alert check failed for %s: %s", name, e)

        self._save()
        return triggered

    def _send_notification(self, alert):
        if not self.notifier:
            return
        message = self._format_notification(alert)
        try:
            results = self.notifier.notify(message)
            for channel, ok in results.items():
                if ok:
                    logger.info("Notification sent via %s for %s", channel, alert["rule"])
                else:
                    logger.warning("Notification failed via %s (not configured or error)", channel)
        except Exception as e:
            logger.error("Notification error: %s", e)

    def get_history(self, limit=50):
        return self._history[-limit:]

    def clear_history(self):
        self._history = []
        self._save()