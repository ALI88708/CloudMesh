"""Smart diagnostics for CloudMesh.

The engine inspects resource metrics, SSL expiries, process-watcher alerts,
backup freshness, and managed-state drift, then returns structured findings::

    {"id": ..., "severity": "info|warning|critical", "area": ...,
     "target": ..., "title": ..., "detail": ..., "suggestion": ...}

Every check degrades gracefully: a missing component simply yields no
findings instead of raising.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SEVERITIES = ("info", "warning", "critical")

DISK_CRIT = 90.0
DISK_WARN = 75.0
RAM_CRIT = 90.0
RAM_WARN = 75.0
CPU_CRIT = 95.0
CPU_WARN = 80.0
SSL_CRIT_DAYS = 7
SSL_WARN_DAYS = 30
BACKUP_STALE_DAYS = 7


def _finding(fid, severity, area, target, title, detail="", suggestion=""):
    """Build a finding with an ID, severity, target, and optional fix guidance."""
    return {
        "id": fid, "severity": severity, "area": area, "target": target,
        "title": title, "detail": detail, "suggestion": suggestion,
    }


class DiagnoseEngine:
    def __init__(self, monitor=None, server_mgr=None, storage=None,
                 base_dir=None, drift=None):
        """Configure metric sources, backup storage, and an optional drift checker.

        If storage is omitted and base_dir is given, initialize SQLite storage
        there, creating its files as needed. Storage initialization failures
        disable backup checks; import errors and invalid base_dir values can
        still propagate. Omitting drift defers its creation until diagnosis.
        """
        self.monitor = monitor
        self.server_mgr = server_mgr
        if storage is None and base_dir is not None:
            try:
                from cloudmesh.core.storage import StorageManager
            except ImportError:
                from core.storage import StorageManager
            try:
                storage = StorageManager(Path(base_dir))
            except Exception as e:
                logger.warning("Diagnose storage unavailable: %s", e)
                storage = None
        self.storage = storage
        self.base_dir = Path(base_dir) if base_dir is not None else None
        self._drift = drift

    # -- entry point ---------------------------------------------------
    def diagnose(self, names=None, include_local: bool = True) -> List[Dict[str, Any]]:
        """Return findings in check order, with a healthy finding if none arise.

        names selects servers for resource checks; None selects all known
        servers and an empty iterable selects none. include_local adds local
        metrics. SSL, watcher, backup, and drift checks remain fleet-wide.
        Findings contain id, severity, area, target, title, detail, and
        suggestion fields and are not sorted by severity.

        Metric retrieval failures yield connectivity warnings. Other checks
        skip unavailable data, so a healthy result can include skipped checks.
        Errors processing malformed check results can still propagate.
        """
        findings: List[Dict[str, Any]] = []
        targets = self._targets(names, include_local)
        for target, metrics in targets:
            if metrics is None:
                findings.append(_finding(
                    "unreachable", "warning", "connectivity", target,
                    f"{target}: metrics unavailable",
                    detail="Could not collect resource metrics.",
                    suggestion="Check the server is reachable: cm test -n NAME / cm ping.",
                ))
                continue
            findings.extend(self._check_resources(target, metrics))
        findings.extend(self._check_ssl())
        findings.extend(self._check_watchers())
        findings.extend(self._check_backups())
        findings.extend(self._check_drift())
        if not findings:
            findings.append(_finding(
                "healthy", "info", "overview", "all",
                "No issues detected",
                detail="All enabled checks passed.",
                suggestion="",
            ))
        return findings

    def _targets(self, names, include_local):
        """Return (target, metrics) pairs, using None for failed metric reads.

        Include local metrics when requested; names=None discovers servers
        through server_mgr. Failed discovery omits remote targets, and a
        missing monitor returns no targets.
        """
        out = []
        if self.monitor is None:
            return out
        if include_local:
            try:
                out.append(("local", self.monitor.get_local_metrics()))
            except Exception as e:
                logger.warning("Local metrics failed: %s", e)
                out.append(("local", None))
        if names is None and self.server_mgr is not None:
            try:
                names = self.server_mgr.list_servers()
            except Exception:
                names = []
        for name in names or []:
            try:
                out.append((name, self.monitor.get_all_metrics(name)))
            except Exception as e:
                logger.warning("Metrics failed for %s: %s", name, e)
                out.append((name, None))
        return out

    # -- checks ----------------------------------------------------------
    def _check_resources(self, target, metrics):
        """Return findings for CPU, RAM, and disk utilization percentages.

        CPU warns at 80% and is critical at 95%; RAM and disk warn at 75%
        and are critical at 90%, including each threshold. Missing values
        and values whose float conversion raises TypeError or ValueError are
        ignored. metrics and nonempty ram/disk entries must support get();
        AttributeError from malformed entries propagates.
        """
        out = []
        cpu = metrics.get("cpu_percent")
        ram = metrics.get("ram") or {}
        disk = metrics.get("disk") or {}
        try:
            cpu_v = float(cpu) if cpu is not None else None
        except (TypeError, ValueError):
            cpu_v = None
        try:
            ram_v = float(ram.get("percent")) if ram.get("percent") is not None else None
        except (TypeError, ValueError):
            ram_v = None
        try:
            disk_v = float(disk.get("percent")) if disk.get("percent") is not None else None
        except (TypeError, ValueError):
            disk_v = None

        if disk_v is not None:
            if disk_v >= DISK_CRIT:
                out.append(_finding(
                    "disk-critical", "critical", "resources", target,
                    f"{target}: disk {disk_v:.0f}% full",
                    detail=f"Used {disk.get('used_gb', '?')}/{disk.get('total_gb', '?')} GB.",
                    suggestion="Free space now: cm cleanup; inspect usage: cm disk -n NAME.",
                ))
            elif disk_v >= DISK_WARN:
                out.append(_finding(
                    "disk-warning", "warning", "resources", target,
                    f"{target}: disk {disk_v:.0f}% full",
                    detail="Above the 75% warning threshold.",
                    suggestion="Plan cleanup soon: cm cleanup; watch trend: cm reshistory show NAME.",
                ))
        if ram_v is not None:
            if ram_v >= RAM_CRIT:
                out.append(_finding(
                    "ram-critical", "critical", "resources", target,
                    f"{target}: RAM {ram_v:.0f}% used",
                    detail=f"Used {ram.get('used_gb', '?')}/{ram.get('total_gb', '?')} GB.",
                    suggestion="Find hungry processes: cm top -n NAME; consider moving load: cm run --best.",
                ))
            elif ram_v >= RAM_WARN:
                out.append(_finding(
                    "ram-warning", "warning", "resources", target,
                    f"{target}: RAM {ram_v:.0f}% used",
                    detail="Above the 75% warning threshold.",
                    suggestion="Check top processes: cm top -n NAME.",
                ))
        if cpu_v is not None and cpu_v >= CPU_CRIT:
            out.append(_finding(
                "cpu-critical", "critical", "resources", target,
                f"{target}: CPU {cpu_v:.0f}%",
                detail="CPU saturated at snapshot time.",
                suggestion="Check top processes: cm top -n NAME; spread load: cm slice.",
            ))
        elif cpu_v is not None and cpu_v >= CPU_WARN:
            out.append(_finding(
                "cpu-warning", "warning", "resources", target,
                f"{target}: CPU {cpu_v:.0f}%",
                detail="CPU above the 80% warning threshold.",
                suggestion="Check top processes: cm top -n NAME.",
            ))
        return out

    def _check_ssl(self):
        """Check tracked domains over TLS and return certificate findings.

        Non-valid statuses produce warnings. For valid results, integer
        days_left values at or below 7 are critical (including expired
        certificates); values from 8 through 30 warn. Loading failures yield
        no findings, while raised certificate-check errors, non-dict results,
        and missing day counts are skipped. TypeError and ValueError converting
        day counts are ignored; other conversion errors propagate.
        """
        out = []
        try:
            try:
                from cloudmesh.core import sslcheck
            except ImportError:
                from core import sslcheck
            domains = sslcheck.load_domains()
        except Exception as e:
            logger.warning("SSL check skipped: %s", e)
            return out
        for entry in domains or []:
            if isinstance(entry, dict):
                domain, port = entry.get("domain", ""), entry.get("port", 443)
            else:
                domain, port = entry, 443
            if not domain:
                continue
            try:
                result = sslcheck.check_cert(domain, port)
            except Exception:
                continue
            if not isinstance(result, dict):
                continue
            if result.get("status") not in ("valid",):
                out.append(_finding(
                    "ssl-error", "warning", "ssl", domain,
                    f"SSL check failed for {domain}: {result.get('status')}",
                    detail=str(result.get("error", ""))[:200],
                    suggestion="Verify manually: cm ssl check DOMAIN.",
                ))
                continue
            days = result.get("days_left")
            try:
                days_v = int(days) if days is not None else None
            except (TypeError, ValueError):
                days_v = None
            if days_v is None:
                continue
            if days_v < 0:
                out.append(_finding(
                    "ssl-expired", "critical", "ssl", domain,
                    f"SSL expired for {domain}",
                    detail=f"Expired {-days_v} day(s) ago.",
                    suggestion="Renew the certificate now: cm ssl renew-check.",
                ))
            elif days_v <= SSL_CRIT_DAYS:
                out.append(_finding(
                    "ssl-critical", "critical", "ssl", domain,
                    f"SSL expires in {days_v} day(s): {domain}",
                    detail=f"Issuer: {result.get('issuer', '?')}.",
                    suggestion="Renew soon: cm ssl renew-check.",
                ))
            elif days_v <= SSL_WARN_DAYS:
                out.append(_finding(
                    "ssl-warning", "warning", "ssl", domain,
                    f"SSL expires in {days_v} day(s): {domain}",
                    detail=f"Issuer: {result.get('issuer', '?')}.",
                    suggestion="Schedule renewal: cm ssl renew-check.",
                ))
        return out

    def _check_watchers(self):
        """Return warnings for up to ten recent stored watcher alerts.

        No fresh process check is run. Loading failures return no findings;
        malformed alert entries can raise AttributeError.
        """
        out = []
        try:
            try:
                from cloudmesh.core.watcher import watcher_alerts
            except ImportError:
                from core.watcher import watcher_alerts
            alerts = watcher_alerts()
        except Exception as e:
            logger.warning("Watcher check skipped: %s", e)
            return out
        for alert in (alerts or [])[-10:]:
            out.append(_finding(
                "watcher", "warning", "processes",
                str(alert.get("server", "?")),
                f"Watcher alert: {alert.get('alert', alert.get('watcher', '?'))}",
                detail=str(alert.get("time", "")),
                suggestion="Inspect status: cm watcher check.",
            ))
        return out

    def _check_backups(self):
        """Report missing SQLite backups or a newest backup over seven days old.

        Age uses the latest modification time among cloudmesh_backup_*.db
        files in storage.backups_dir. Missing backups produce an info finding;
        stale backups produce a warning. Missing storage, listing failures,
        and OSError while reading modification times yield no findings.
        """
        out = []
        if self.storage is None:
            return out
        try:
            backups = sorted(Path(self.storage.backups_dir).glob("cloudmesh_backup_*.db"))
        except Exception as e:
            logger.warning("Backup check skipped: %s", e)
            return out
        if not backups:
            out.append(_finding(
                "backup-missing", "info", "backups", "storage",
                "No SQLite backups yet",
                detail="Retention protects restores only once backups exist.",
                suggestion="Create one: cm storage backup.",
            ))
            return out
        try:
            latest = max(backups, key=lambda p: p.stat().st_mtime)
            age_days = (datetime.now(timezone.utc).timestamp() - latest.stat().st_mtime) / 86400
        except OSError:
            return out
        if age_days > BACKUP_STALE_DAYS:
            out.append(_finding(
                "backup-stale", "warning", "backups", "storage",
                f"Latest backup is {age_days:.0f} days old",
                detail=f"Newest: {latest.name}.",
                suggestion="Refresh it: cm storage backup.",
            ))
        return out

    def _check_drift(self):
        """Return one warning per collection that differs from the baseline.

        Create a default DriftManager if none was supplied, which may
        initialize storage files. Initialization and check failures, an absent
        baseline, or no drift yield no findings. Errors importing the summary
        helper or processing malformed results propagate.
        """
        out = []
        try:
            drift = self._drift
            if drift is None:
                try:
                    from cloudmesh.core.drift import DriftManager
                except ImportError:
                    from core.drift import DriftManager
                drift = DriftManager(server_mgr=self.server_mgr, storage=self.storage)
            result = drift.check()
        except Exception as e:
            logger.warning("Drift check skipped: %s", e)
            return out
        if not result.get("has_baseline"):
            return out
        if not result.get("drifted"):
            return out
        try:
            from cloudmesh.core.drift import DriftManager as _DM
        except ImportError:
            from core.drift import DriftManager as _DM
        for line in _DM.summarize(result["diff"]):
            out.append(_finding(
                "drift", "warning", "drift", "fleet",
                f"Configuration drift: {line}",
                detail="Managed state differs from the recorded baseline.",
                suggestion="Review: cm drift check; re-baseline when intended: cm drift snapshot.",
            ))
        return out
