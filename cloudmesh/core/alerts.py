import json
from datetime import datetime
from pathlib import Path


class AlertManager:
    def __init__(self, resource_monitor, base_dir=None):
        self.monitor = resource_monitor
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        self.base_dir = Path(base_dir)
        self.alerts_file = self.base_dir / "alerts.json"
        self._rules = []
        self._history = []
        self._load()

    def _load(self):
        if self.alerts_file.exists():
            try:
                data = json.loads(self.alerts_file.read_text())
                self._rules = data.get("rules", [])
                self._history = data.get("history", [])
            except Exception:
                self._rules = []
                self._history = []

    def _save(self):
        data = {"rules": self._rules, "history": self._history[-100:]}
        self.alerts_file.write_text(json.dumps(data, indent=2))

    def add_rule(self, name, metric, threshold, operator="gt", server=None):
        rule = {
            "name": name,
            "metric": metric,
            "threshold": threshold,
            "operator": operator,
            "server": server,
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

    def check_alerts(self, server_names=None):
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

                    if self._check_condition(value, rule["threshold"], rule["operator"]):
                        alert = {
                            "rule": rule["name"],
                            "server": name,
                            "metric": metric_name,
                            "value": value,
                            "threshold": rule["threshold"],
                            "operator": rule["operator"],
                            "timestamp": datetime.now().isoformat(),
                        }
                        triggered.append(alert)
                        self._history.append(alert)
            except Exception:
                continue

        self._save()
        return triggered

    def get_history(self, limit=50):
        return self._history[-limit:]

    def clear_history(self):
        self._history = []
        self._save()
