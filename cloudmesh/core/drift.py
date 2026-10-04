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


class DriftManager:
    def __init__(self, server_mgr=None, storage=None, base_dir=None):
        """Use the supplied storage or initialize SQLite storage at base_dir.

        With neither storage nor base_dir, use StorageManager's default
        directory. Initialization may create storage files and its errors
        propagate. server_mgr, when supplied, is the source of server entries.
        """
        self.server_mgr = server_mgr
        if storage is None:
            base = Path(base_dir) if base_dir is not None else None
            storage = StorageManager(base) if base is not None else StorageManager()
        self.storage = storage

    # -- collection ----------------------------------------------------
    def collect(self) -> Dict[str, Any]:
        """Return tracked collections keyed by name with selected state fields.

        Server credentials and node auth keys are excluded; command strings
        and descriptions are retained verbatim. Schedule intervals are in
        seconds. Failed collections become empty mappings, and servers whose
        info lookup fails are omitted, which can appear as removals in a diff.
        """
        state: Dict[str, Any] = {}
        try:
            if self.server_mgr is not None:
                servers = {}
                for name in self.server_mgr.list_servers():
                    try:
                        info = self.server_mgr.get_server_info(name)
                    except Exception:
                        continue
                    servers[name] = {
                        "host": info.get("host"),
                        "user": info.get("user"),
                        "port": info.get("port", 22),
                    }
                state["servers"] = servers
            else:
                state["servers"] = {
                    s["name"]: {"host": s.get("host"), "user": s.get("user"),
                                "port": s.get("port", 22)}
                    for s in self.storage.list_servers()
                }
        except Exception as e:
            logger.warning("Drift collect servers failed: %s", e)
            state["servers"] = {}
        try:
            state["nodes"] = {
                n["name"]: {"host": n.get("host"), "port": n.get("port", 9999),
                            "tls": bool(n.get("tls", False))}
                for n in self.storage.list_nodes()
            }
        except Exception as e:
            logger.warning("Drift collect nodes failed: %s", e)
            state["nodes"] = {}
        try:
            state["groups"] = dict(self.storage.list_groups())
        except Exception:
            state["groups"] = {}
        try:
            state["schedules"] = {
                s["name"]: {"command": s.get("command"),
                            "interval": s.get("interval_seconds", 3600),
                            "enabled": bool(s.get("enabled", True)),
                            "server": s.get("server")}
                for s in self.storage.list_schedules()
            }
        except Exception:
            state["schedules"] = {}
        try:
            state["templates"] = {
                t["name"]: {"command": t.get("command", ""),
                            "description": t.get("description", "")}
                for t in self.storage.list_templates()
            }
        except Exception:
            state["templates"] = {}
        try:
            state["aliases"] = dict(self.storage.list_aliases())
        except Exception:
            state["aliases"] = {}
        try:
            state["alert_rules"] = {
                r["name"]: {"metric": r.get("metric"), "threshold": r.get("threshold"),
                            "operator": r.get("operator", "gt"),
                            "server": r.get("server"),
                            "severity": r.get("severity", "warning")}
                for r in self.storage.list_alert_rules()
            }
        except Exception:
            state["alert_rules"] = {}
        return state

    # -- baseline ------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """Replace the stored drift baseline and return the collected state.

        Collection failures can produce a partial baseline. Errors saving it,
        including SQLite and JSON serialization errors, propagate to callers.
        """
        state = self.collect()
        try:
            self.storage.set_setting(BASELINE_KEY, state)
        except Exception as e:
            logger.error("Drift snapshot failed: %s", e)
            raise
        return state

    def get_baseline(self) -> Optional[Dict[str, Any]]:
        """Return the baseline, or None if absent, unreadable, or not a dict."""
        try:
            base = self.storage.get_setting(BASELINE_KEY, None)
        except Exception:
            return None
        return base if isinstance(base, dict) else None

    def clear(self) -> None:
        """Remove the recorded baseline, suppressing storage errors.

        Return None whether deletion succeeds, fails, or no baseline exists.
        """
        try:
            with self.storage._get_connection() as conn:
                conn.execute("DELETE FROM settings WHERE key = ?", (BASELINE_KEY,))
                conn.commit()
        except Exception as e:
            logger.warning("Drift clear failed: %s", e)

    # -- diff ----------------------------------------------------------
    @staticmethod
    def diff_states(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """Return added, removed, and modified entries for each tracked collection.

        Snapshots map collection names to mappings of item names to values.
        Missing or false-valued collections are treated as empty; untracked
        collections are ignored. Added and removed names are sorted lists.
        Modified names map to before/after values that compare unequal.
        """
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

        Returns {"has_baseline": bool, "drifted": bool, "diff": {...}}.
        An absent, unreadable, or non-dict baseline returns both flags False
        and an empty diff without collecting live state. Collection failures
        can appear as removals; malformed baseline collections can raise
        errors during comparison.
        """
        baseline = self.get_baseline()
        if baseline is None:
            return {"has_baseline": False, "drifted": False, "diff": {}}
        current = self.collect()
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
