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
    """Alert rules and history with SQLite as the source of truth.

    The legacy ``alerts.json`` file is kept as a compatible mirror, and any
    legacy data is imported once (persistent marker: an empty rule set is a
    valid state and must not trigger a re-import).
    """

    def __init__(self, resource_monitor, base_dir=None, notifier=None, storage=None):
        """Attach a metric monitor and optional notifier, then import legacy data.

        base_dir locates alerts.json and, when storage is omitted, the new
        StorageManager. Storage initialization errors propagate.
        """
        self.monitor = resource_monitor
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        self.base_dir = Path(base_dir)
        self.alerts_file = self.base_dir / "alerts.json"
        self.notifier = notifier
        if storage is None:
            try:
                from cloudmesh.core.storage import StorageManager
            except ImportError:
                from core.storage import StorageManager
            storage = StorageManager(self.base_dir)
        self.storage = storage
        self._ensure_imported()

    def _ensure_imported(self):
        """Import legacy rules, history, and cooldowns unless already marked.

        Read or entry import failures leave the marker unset and mirror
        untouched. Successful history imports preserve supplied timestamps.
        Malformed rule/history collections or cooldown mappings can raise
        TypeError or AttributeError.
        """
        try:
            if self.storage.legacy_imported("alerts"):
                self._push_mirror()
                return
        except Exception:
            return
        if self.alerts_file.exists():
            try:
                data = json.loads(self.alerts_file.read_text())
                if not isinstance(data, dict):
                    raise ValueError("alerts.json is not an object")
            except Exception as e:
                logger.error("Failed to load alerts: %s", e)
                return  # leave marker unset; do not touch the mirror
            ok = True
            for rule in data.get("rules", []):
                try:
                    if not self.storage.add_alert_rule(
                        name=rule.get("name"),
                        metric=rule.get("metric"),
                        threshold=rule.get("threshold"),
                        operator=rule.get("operator", "gt"),
                        server=rule.get("server"),
                        severity=rule.get("severity", "warning"),
                        cooldown=rule.get("cooldown", DEFAULT_COOLDOWN),
                    ):
                        raise RuntimeError("storage rejected alert rule")
                except Exception:
                    ok = False
                    continue
            for alert in data.get("history", []):
                try:
                    self.storage.add_alert_history(
                        rule_name=alert.get("rule"),
                        server=alert.get("server"),
                        metric=alert.get("metric"),
                        value=alert.get("value"),
                        threshold=alert.get("threshold"),
                        operator=alert.get("operator"),
                        severity=alert.get("severity"),
                        timestamp=alert.get("timestamp"),
                    )
                except Exception:
                    ok = False
                    continue
            for key, timestamp in data.get("last_notified", {}).items():
                try:
                    rule_name, server = key.split("|")
                    self.storage.set_alert_cooldown(rule_name, server, timestamp)
                except Exception:
                    ok = False
                    continue
            if not ok:
                logger.warning("Alerts import incomplete; marker left unset")
                return
        try:
            self.storage.mark_legacy_imported("alerts")
        except Exception:
            pass
        self._push_mirror()

    def _push_mirror(self):
        """Write rules, up to 500 recent alerts, and cooldowns to JSON.

        Suppress storage, serialization, and file write errors.
        """
        try:
            rules = self.storage.list_alert_rules()
            history = [
                {
                    "rule": h.get("rule_name"),
                    "server": h.get("server"),
                    "metric": h.get("metric"),
                    "value": h.get("value"),
                    "threshold": h.get("threshold"),
                    "operator": h.get("operator"),
                    "severity": h.get("severity"),
                    "timestamp": h.get("timestamp"),
                }
                for h in self.storage.get_alert_history(limit=500)
            ]
            data = {
                "rules": rules,
                "history": history,
                "last_notified": self.storage.list_alert_cooldowns(),
            }
            self.alerts_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning("Failed to write alerts mirror: %s", e)

    def add_rule(self, name, metric, threshold, operator="gt", server=None,
                 severity="warning", cooldown=DEFAULT_COOLDOWN):
        """Attempt to store an enabled rule and return its requested values.

        Recognized metrics are cpu, ram, disk, load, and gpu; threshold uses
        the monitor's units. Operators are gt, lt, gte, lte, and eq. A missing
        server applies the rule to any server being checked. Unknown severity
        becomes warning; cooldown is converted to integer seconds and clamped
        to zero. Conversion errors propagate. Duplicate rules and persistence
        failures do not prevent returning the rule dictionary.
        """
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
        try:
            self.storage.add_alert_rule(
                name=name, metric=metric, threshold=threshold, operator=operator,
                server=server, severity=rule["severity"], cooldown=rule["cooldown"],
            )
        except Exception as e:
            logger.warning("Failed to persist alert rule %s: %s", name, e)
        self._push_mirror()
        return rule

    def remove_rule(self, name):
        """Attempt to delete the named rule and refresh JSON, suppressing errors."""
        try:
            self.storage.remove_alert_rule(name)
        except Exception as e:
            logger.warning("Failed to remove alert rule %s: %s", name, e)
        self._push_mirror()

    def list_rules(self):
        """Return stored rule dictionaries, or an empty list on storage failure."""
        try:
            return self.storage.list_alert_rules()
        except Exception as e:
            logger.warning("Failed to list alert rules: %s", e)
            return []

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
        """Return whether the rule's cooldown in seconds has elapsed.

        key is formatted as rule_name|server. Missing or unreadable timestamps
        allow notification. Invalid cooldown conversion or timestamp arithmetic
        errors propagate when a nonzero timestamp is available.
        """
        try:
            rule_name, server = key.split("|")
            last = self.storage.get_alert_cooldown(rule_name, server)
        except Exception:
            return True
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
        """Return triggered alert dictionaries and attempt to record each one.

        If server_names is None, check only servers explicitly named in rules.
        Cooldowns gate notifications, not returned alerts or history; elapsed
        cooldowns are updated even when send_notifications is False. Failures
        within a server's check are suppressed and remaining servers continue.
        Refresh the JSON mirror after checking.
        """
        rules = self.list_rules()
        if server_names is None:
            server_names = list(dict.fromkeys(r.get("server") for r in rules if r.get("server")))
            if not server_names:
                return []

        triggered = []
        for name in server_names:
            try:
                metrics = self.monitor.get_all_metrics(name)
                if metrics is None:
                    continue

                for rule in rules:
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
                        try:
                            self.storage.add_alert_history(
                                rule_name=rule["name"], server=name, metric=metric_name,
                                value=value, threshold=rule["threshold"],
                                operator=rule["operator"],
                                severity=severity,
                            )
                        except Exception as e:
                            logger.warning("Failed to record alert history: %s", e)

                        key = self._cooldown_key(rule["name"], name)
                        if self._cooldown_passed(key, rule):
                            try:
                                self.storage.set_alert_cooldown(rule["name"], name, time.time())
                            except Exception:
                                pass
                            if send_notifications:
                                self._send_notification(alert)
            except Exception as e:
                logger.warning("Alert check failed for %s: %s", name, e)

        self._push_mirror()
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
        """Return recent alert dictionaries in descending timestamp order.

        limit is the SQLite row limit: zero returns none and a negative value
        removes the limit. Storage or conversion failures return an empty list.
        """
        try:
            return [
                {
                    "rule": h.get("rule_name"),
                    "server": h.get("server"),
                    "metric": h.get("metric"),
                    "value": h.get("value"),
                    "threshold": h.get("threshold"),
                    "operator": h.get("operator"),
                    "severity": h.get("severity"),
                    "timestamp": h.get("timestamp"),
                }
                for h in self.storage.get_alert_history(limit=limit)
            ]
        except Exception as e:
            logger.warning("Failed to read alert history: %s", e)
            return []

    def clear_history(self):
        """Attempt to clear stored history and refresh JSON, preserving cooldowns.

        Storage and mirror write errors are suppressed.
        """
        try:
            self.storage.clear_alert_history()
        except Exception as e:
            logger.warning("Failed to clear alert history: %s", e)
        self._push_mirror()