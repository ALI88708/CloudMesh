"""Drift detection for CloudMesh-managed state.

A baseline snapshot of every SQLite-backed collection (servers, nodes,
schedules, templates, aliases, alert rules) is stored in the ``settings``
table. ``check()`` diffs live state against the baseline and reports
added/removed/modified entries per collection. Secrets are never stored:
node auth keys are excluded from node entries.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from cloudmesh.core.storage import StorageManager
except ImportError:  # `cd cloudmesh && pytest tests` without installed package
    from core.storage import StorageManager

logger = logging.getLogger(__name__)

BASELINE_KEY = "drift_baseline"
TRACKED = ("servers", "nodes", "groups", "schedules", "templates", "aliases", "alert_rules")


class DriftError(RuntimeError):
    """Raised when live state cannot be fully collected."""


class DriftManager:
    def __init__(self, server_mgr=None, storage=None, base_dir=None):
        self.server_mgr = server_mgr
        if storage is None:
            base = Path(base_dir) if base_dir is not None else None
            storage = StorageManager(base) if base is not None else StorageManager()
        self.storage = storage

    # -- collection ----------------------------------------------------
    def collect(self) -> Dict[str, Any]:
        """Capture current managed state (no secrets)."""
        state: Dict[str, Any] = {}
        errors: Dict[str, str] = {}
        collectors = (
            ("servers", self._collect_servers),
            ("nodes", self._collect_nodes),
            ("groups", self._collect_groups),
            ("schedules", self._collect_schedules),
            ("templates", self._collect_templates),
            ("aliases", self._collect_aliases),
            ("alert_rules", self._collect_alert_rules),
        )
        for kind, fn in collectors:
            try:
                state[kind] = fn()
            except Exception as e:
                errors[kind] = str(e)
                state[kind] = {}
        if errors:
            raise DriftError(f"collection failed for: {sorted(errors)}")
        return state

    def _collect_servers(self) -> Dict[str, Any]:
        if self.server_mgr is not None:
            servers = {}
            for name in self.server_mgr.list_servers():
                info = self.server_mgr.get_server_info(name)
                servers[name] = {
                    "host": info.get("host"),
                    "user": info.get("user"),
                    "port": info.get("port", 22),
                }
            return servers
        return {
            s["name"]: {"host": s.get("host"), "user": s.get("user"),
                        "port": s.get("port", 22)}
            for s in self.storage.list_servers()
        }

    def _collect_nodes(self) -> Dict[str, Any]:
        return {
            n["name"]: {"host": n.get("host"), "port": n.get("port", 9999),
                        "tls": bool(n.get("tls", False))}
            for n in self.storage.list_nodes()
        }

    def _collect_groups(self) -> Dict[str, Any]:
        return dict(self.storage.list_groups())

    def _collect_schedules(self) -> Dict[str, Any]:
        return {
            s["name"]: {"command": s.get("command"),
                        "interval": s.get("interval_seconds", 3600),
                        "enabled": bool(s.get("enabled", True)),
                        "server": s.get("server")}
            for s in self.storage.list_schedules()
        }

    def _collect_templates(self) -> Dict[str, Any]:
        return {
            t["name"]: {"command": t.get("command", ""),
                        "description": t.get("description", "")}
            for t in self.storage.list_templates()
        }

    def _collect_aliases(self) -> Dict[str, Any]:
        return dict(self.storage.list_aliases())

    def _collect_alert_rules(self) -> Dict[str, Any]:
        return {
            r["name"]: {"metric": r.get("metric"), "threshold": r.get("threshold"),
                        "operator": r.get("operator", "gt"),
                        "server": r.get("server"),
                        "severity": r.get("severity", "warning")}
            for r in self.storage.list_alert_rules()
        }

    # -- baseline ------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """Record the current state as the drift baseline."""
        state = self.collect()
        try:
            self.storage.set_setting(BASELINE_KEY, state)
        except Exception as e:
            logger.error("Drift snapshot failed: %s", e)
            raise
        return state

    def get_baseline(self) -> Optional[Dict[str, Any]]:
        """Return the recorded baseline, or None when absent."""
        try:
            base = self.storage.get_setting(BASELINE_KEY, None)
        except Exception:
            return None
        return base if isinstance(base, dict) else None

    def clear(self) -> None:
        """Remove the recorded baseline."""
        try:
            with self.storage._get_connection() as conn:
                conn.execute("DELETE FROM settings WHERE key = ?", (BASELINE_KEY,))
                conn.commit()
        except Exception as e:
            logger.warning("Drift clear failed: %s", e)

    # -- diff ----------------------------------------------------------
    @staticmethod
    def diff_states(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """Diff two state snapshots per collection."""
        result: Dict[str, Any] = {}
        for kind in TRACKED:
            old = before.get(kind, {}) or {}
            new = after.get(kind, {}) or {}
            old_keys, new_keys = set(old), set(new)
            modified = {}
            for key in old_keys & new_keys:
                if old[key] != new[key]:
                    modified[key] = {"before": old[key], "after": new[key]}
            result[kind] = {
                "added": sorted(new_keys - old_keys),
                "removed": sorted(old_keys - new_keys),
                "modified": modified,
            }
        return result

    def check(self) -> Dict[str, Any]:
        """Diff live state against the baseline.

        Returns {"has_baseline": bool, "drifted": bool, "diff": {...}}
        plus "error" when live state cannot be fully collected (never
        reported as removals).
        """
        baseline = self.get_baseline()
        if baseline is None:
            return {"has_baseline": False, "drifted": False, "diff": {}}
        try:
            current = self.collect()
        except DriftError as e:
            logger.error("Drift check refused on partial state: %s", e)
            return {"has_baseline": True, "drifted": False, "diff": {},
                    "error": str(e)}
        diff = self.diff_states(baseline, current)
        drifted = any(
            d["added"] or d["removed"] or d["modified"] for d in diff.values()
        )
        return {"has_baseline": True, "drifted": drifted, "diff": diff}

    @staticmethod
    def summarize(diff: Dict[str, Any]) -> List[str]:
        """One-line human summaries per drifted collection."""
        lines = []
        for kind in TRACKED:
            d = diff.get(kind, {})
            parts = []
            if d.get("added"):
                parts.append(f"+{len(d['added'])} added ({', '.join(d['added'][:3])})")
            if d.get("removed"):
                parts.append(f"-{len(d['removed'])} removed ({', '.join(d['removed'][:3])})")
            if d.get("modified"):
                parts.append(f"~{len(d['modified'])} modified ({', '.join(list(d['modified'])[:3])})")
            if parts:
                lines.append(f"{kind}: " + "; ".join(parts))
        return lines
