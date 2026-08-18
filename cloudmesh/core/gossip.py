import json
import time
from pathlib import Path
from datetime import datetime


class GossipManager:
    def __init__(self, data_file=None):
        self.data_file = Path(data_file or Path(__file__).parent.parent / ".gossip_trust.json")
        self._data = self._load()

    def _load(self):
        if self.data_file.exists():
            try:
                return json.loads(self.data_file.read_text())
            except Exception:
                pass
        return {"nodes": {}, "last_scan": None}

    def _save(self):
        self.data_file.write_text(json.dumps(self._data, indent=2))

    def record_controller_ping(self, node_name, reachable, latency_ms=None):
        if node_name not in self._data["nodes"]:
            self._data["nodes"][node_name] = {
                "controller_observed": [],
                "self_reports": [],
                "trust_score": 100,
                "status": "unknown",
            }

        node = self._data["nodes"][node_name]
        observation = {
            "time": datetime.now().isoformat(),
            "reachable": reachable,
            "latency_ms": latency_ms,
        }
        node["controller_observed"].append(observation)
        node["controller_observed"] = node["controller_observed"][-60:]

        self._evaluate_trust(node)

    def record_self_report(self, node_name, healthy, reported_metrics=None):
        if node_name not in self._data["nodes"]:
            self._data["nodes"][node_name] = {
                "controller_observed": [],
                "self_reports": [],
                "trust_score": 100,
                "status": "unknown",
            }

        node = self._data["nodes"][node_name]
        report = {
            "time": datetime.now().isoformat(),
            "healthy": healthy,
            "metrics": reported_metrics,
        }
        node["self_reports"].append(report)
        node["self_reports"] = node["self_reports"][-60:]

        self._evaluate_trust(node)

    def _evaluate_trust(self, node):
        controller_obs = node.get("controller_observed", [])
        self_reports = node.get("self_reports", [])

        recent_obs = controller_obs[-10:]
        recent_reports = self_reports[-10:]

        if not recent_obs and not recent_reports:
            node["status"] = "unknown"
            node["trust_score"] = 100
            return

        controller_reachable_count = sum(1 for o in recent_obs if o.get("reachable"))
        controller_total = len(recent_obs)

        self_healthy_count = sum(1 for r in recent_reports if r.get("healthy"))
        self_total = len(recent_reports)

        if controller_total > 0:
            controller_rate = controller_reachable_count / controller_total
        else:
            controller_rate = None

        if self_total > 0:
            self_rate = self_healthy_count / self_total
        else:
            self_rate = None

        if controller_rate is not None and self_rate is not None:
            if self_rate > 0.8 and controller_rate < 0.3:
                node["trust_score"] = 10
                node["status"] = "suspicious"
                node["reason"] = f"Node reports healthy ({self_rate:.0%}) but controller unreachable ({controller_rate:.0%})"
            elif controller_rate > 0.8:
                node["trust_score"] = 100
                node["status"] = "trusted"
                node["reason"] = None
            elif controller_rate > 0.5:
                node["trust_score"] = 60
                node["status"] = "degraded"
                node["reason"] = f"Controller reachability at {controller_rate:.0%}"
            else:
                node["trust_score"] = 20
                node["status"] = "unreachable"
                node["reason"] = f"Controller can only reach node {controller_rate:.0%} of the time"
        elif controller_rate is not None:
            if controller_rate > 0.8:
                node["trust_score"] = 90
                node["status"] = "trusted"
                node["reason"] = None
            elif controller_rate > 0.3:
                node["trust_score"] = 50
                node["status"] = "degraded"
                node["reason"] = f"Controller reachability at {controller_rate:.0%}"
            else:
                node["trust_score"] = 10
                node["status"] = "unreachable"
                node["reason"] = f"Controller rarely reaches node ({controller_rate:.0%})"
        elif self_rate is not None:
            node["trust_score"] = 50
            node["status"] = "unverified"
            node["reason"] = "Only self-reports available — controller cannot reach node"

    def get_trust_status(self, node_name=None):
        if node_name:
            return self._data["nodes"].get(node_name)
        return self._data["nodes"]

    def get_suspicious_nodes(self):
        suspicious = []
        for name, node in self._data["nodes"].items():
            if node.get("status") in ("suspicious", "unreachable"):
                suspicious.append({"name": name, **node})
        return suspicious

    def scan_all(self, server_mgr, node_keys=None):
        from core.node_client import NodeClient

        self._data["last_scan"] = datetime.now().isoformat()

        if node_keys:
            for name, info in node_keys.items():
                try:
                    start = time.time()
                    client = NodeClient(info["host"], info["port"], info["key"])
                    reachable = client.ping()
                    latency = round((time.time() - start) * 1000, 1) if reachable else None

                    self.record_controller_ping(name, reachable, latency)

                    if reachable:
                        metrics = client.get_metrics()
                        self.record_self_report(name, True, metrics)
                    else:
                        self.record_self_report(name, False)
                except Exception:
                    self.record_controller_ping(name, False)
                    self.record_self_report(name, False)

        if server_mgr:
            for name in server_mgr.list_servers():
                try:
                    start = time.time()
                    ok, msg = server_mgr.test_connection(name)
                    latency = round((time.time() - start) * 1000, 1) if ok else None
                    self.record_controller_ping(name, ok, latency)
                except Exception:
                    self.record_controller_ping(name, False)

        self._save()
        return self.get_trust_status()

    def clear(self, node_name=None):
        if node_name:
            self._data["nodes"].pop(node_name, None)
        else:
            self._data = {"nodes": {}, "last_scan": None}
        self._save()
