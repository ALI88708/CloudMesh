"""CloudMesh Migration Script - v3.2.0 Full SQLite Backend

This script migrates existing JSON-based data to the extended SQLite backend.
Run this once after upgrading to v3.2.0.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any

from cryptography.fernet import Fernet

from .storage import StorageManager

logger = logging.getLogger(__name__)


class MigrationManager:
    """Handle migration from JSON to extended SQLite storage."""

    def __init__(self, base_dir: Path = None, init_storage: bool = True):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent

        self.base_dir = Path(base_dir)
        self.config_path = self.base_dir / "config.json"
        self.key_path = self.base_dir / ".secret.key"
        self._storage = None
        self._init_storage = init_storage

        self.migrated = False
        self.errors = []

    @property
    def storage(self) -> StorageManager:
        if self._storage is None:
            self._storage = StorageManager(self.base_dir)
        return self._storage
    
    def _get_fernet(self) -> Fernet:
        """Get Fernet instance for decryption."""
        if self.key_path.exists():
            key = self.key_path.read_bytes()
            return Fernet(key)
        return None
    
    def _load_encrypted_config(self) -> Dict:
        """Load and decrypt old config.json."""
        if not self.config_path.exists():
            logger.info("No existing config.json found - fresh installation")
            return {}

        fernet = self._get_fernet()
        if not fernet:
            msg = "Cannot decrypt config - missing encryption key"
            logger.error(msg)
            self.errors.append(msg)
            return {}

        try:
            encrypted = self.config_path.read_bytes()
            decrypted = fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            msg = f"Failed to decrypt config: {e}"
            logger.error(msg)
            self.errors.append(msg)
            return {}
    
    def migrate_servers(self, config: Dict) -> int:
        """Migrate servers from config."""
        servers = config.get("servers", {})
        count = 0

        for name, info in servers.items():
            try:
                ok = self.storage.add_server(
                    name=name,
                    host=info.get("host"),
                    user=info.get("user"),
                    port=info.get("port", 22),
                    key_path=info.get("key_path"),
                    password=info.get("password")
                )
                if not ok:
                    raise RuntimeError("storage rejected server (duplicate or constraint)")

                # Update status if available
                if info.get("status"):
                    self.storage.update_server_status(name, info["status"])

                count += 1
                logger.info("Migrated server: %s", name)
            except Exception as e:
                self.errors.append(f"Failed to migrate server {name}: {e}")
                logger.error("Failed to migrate server %s: %s", name, e)

        return count
    
    def migrate_nodes(self) -> int:
        """Migrate nodes from .node_keys.json."""
        node_keys_file = self.base_dir / ".node_keys.json"
        if not node_keys_file.exists():
            logger.info("No .node_keys.json found")
            return 0

        try:
            data = json.loads(node_keys_file.read_text())
            count = 0

            for name, info in data.items():
                try:
                    if isinstance(info, dict):
                        host = info.get("host")
                        port = info.get("port", 9999)
                        auth_key = info.get("key", "")
                        tls = bool(info.get("tls", False))
                        ca_file = info.get("ca_file")
                    else:
                        host = str(info)
                        port = 9999
                        auth_key = ""
                        tls = False
                        ca_file = None
                    ok = self.storage.add_node(
                        name=name,
                        host=host,
                        port=port,
                        auth_key=auth_key,
                        tls=tls,
                        ca_file=ca_file,
                    )
                    if not ok:
                        raise RuntimeError("storage rejected node (duplicate or constraint)")
                    count += 1
                    logger.info("Migrated node: %s", name)
                except Exception as e:
                    self.errors.append(f"Failed to migrate node {name}: {e}")
                    logger.error("Failed to migrate node %s: %s", name, e)

            return count
        except Exception as e:
            self.errors.append(f"Failed to load .node_keys.json: {e}")
            logger.error("Failed to load .node_keys.json: %s", e)
            return 0
    
    def migrate_groups(self, config: Dict) -> int:
        """Migrate groups from config."""
        groups = config.get("groups", {})
        count = 0

        for group_name, devices in groups.items():
            try:
                if not isinstance(devices, list):
                    raise ValueError(f"group {group_name} is not a list")
                ok = self.storage.create_group(group_name)
                if not ok:
                    # Group may already exist from a previous partial run; continue adding members.
                    logger.warning("Group '%s' already exists, merging members", group_name)

                for device in devices:
                    # Try to determine if it's a server or node
                    device_type = "server"  # Default
                    try:
                        if self.storage.get_node(device):
                            device_type = "node"
                    except Exception:
                        pass

                    self.storage.add_to_group(group_name, device, device_type)

                count += 1
                logger.info("Migrated group: %s with %d devices", group_name, len(devices))
            except Exception as e:
                self.errors.append(f"Failed to migrate group {group_name}: {e}")
                logger.error("Failed to migrate group %s: %s", group_name, e)

        return count
    
    def migrate_settings(self, config: Dict) -> int:
        """Migrate settings from config."""
        settings = config.get("settings", {})
        count = 0
        
        for key, value in settings.items():
            try:
                self.storage.set_setting(key, value)
                count += 1
            except Exception as e:
                self.errors.append(f"Failed to migrate setting {key}: {e}")
                logger.error("Failed to migrate setting %s: %s", key, e)
        
        return count
    
    def migrate_alerts(self) -> int:
        """Migrate alerts from alerts.json."""
        alerts_file = self.base_dir / "alerts.json"
        if not alerts_file.exists():
            logger.info("No alerts.json found")
            return 0

        try:
            data = json.loads(alerts_file.read_text())
            count = 0

            # Migrate rules
            for rule in data.get("rules", []):
                try:
                    ok = self.storage.add_alert_rule(
                        name=rule.get("name"),
                        metric=rule.get("metric"),
                        threshold=rule.get("threshold"),
                        operator=rule.get("operator", "gt"),
                        server=rule.get("server"),
                        severity=rule.get("severity", "warning"),
                        cooldown=rule.get("cooldown", 300)
                    )
                    if not ok:
                        raise RuntimeError("storage rejected alert rule (duplicate or constraint)")
                    count += 1
                    logger.info("Migrated alert rule: %s", rule.get("name"))
                except Exception as e:
                    self.errors.append(f"Failed to migrate alert rule {rule.get('name')}: {e}")
                    logger.error("Failed to migrate alert rule %s: %s", rule.get("name"), e)

            # Migrate history
            for alert in data.get("history", []):
                try:
                    self.storage.add_alert_history(
                        rule_name=alert.get("rule"),
                        server=alert.get("server"),
                        metric=alert.get("metric"),
                        value=alert.get("value"),
                        threshold=alert.get("threshold"),
                        operator=alert.get("operator"),
                        severity=alert.get("severity")
                    )
                except Exception as e:
                    msg = f"Failed to migrate alert history entry: {e}"
                    self.errors.append(msg)
                    logger.warning(msg)

            # Migrate cooldowns
            for key, timestamp in data.get("last_notified", {}).items():
                try:
                    rule_name, server = key.split("|")
                    self.storage.set_alert_cooldown(rule_name, server, timestamp)
                except Exception as e:
                    msg = f"Failed to migrate alert cooldown {key}: {e}"
                    self.errors.append(msg)
                    logger.warning(msg)

            return count
        except Exception as e:
            self.errors.append(f"Failed to load alerts.json: {e}")
            logger.error("Failed to load alerts.json: %s", e)
            return 0
    
    def migrate_acl(self) -> int:
        """Migrate ACL from data/acl.json."""
        data_dir = self.base_dir / "data"
        acl_file = data_dir / "acl.json"
        
        if not acl_file.exists():
            logger.info("No acl.json found")
            return 0
        
        try:
            data = json.loads(acl_file.read_text())
            count = 0
            
            # Migrate users
            for username, info in data.get("users", {}).items():
                try:
                    # Use direct SQL to bypass password hashing
                    with self.storage._get_connection() as conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO acl_users 
                            (username, password_hash, salt, role, enabled, created_at, failed_attempts, locked_until)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            username,
                            info.get("password_hash"),
                            info.get("salt"),
                            info.get("role", "viewer"),
                            info.get("enabled", True),
                            info.get("created"),
                            info.get("failed_attempts", 0),
                            info.get("locked_until")
                        ))
                        conn.commit()
                    count += 1
                    logger.info("Migrated ACL user: %s", username)
                except Exception as e:
                    self.errors.append(f"Failed to migrate ACL user {username}: {e}")
                    logger.error("Failed to migrate ACL user %s: %s", username, e)
            
            # Migrate roles (skip defaults)
            for role_name, permissions in data.get("roles", {}).items():
                if role_name in ["admin", "viewer"]:
                    continue  # Skip default roles
                try:
                    with self.storage._get_connection() as conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO acl_roles (name, permissions)
                            VALUES (?, ?)
                        """, (role_name, json.dumps(permissions) if isinstance(permissions, list) else permissions))
                        conn.commit()
                    logger.info("Migrated ACL role: %s", role_name)
                except Exception as e:
                    self.errors.append(f"Failed to migrate ACL role {role_name}: {e}")
                    logger.error("Failed to migrate ACL role %s: %s", role_name, e)
            
            return count
        except Exception as e:
            self.errors.append(f"Failed to load acl.json: {e}")
            logger.error("Failed to load acl.json: %s", e)
            return 0
    
    def migrate_aliases(self) -> int:
        """Migrate aliases from .aliases.json."""
        aliases_file = self.base_dir / ".aliases.json"
        if not aliases_file.exists():
            logger.info("No .aliases.json found")
            return 0

        try:
            data = json.loads(aliases_file.read_text())
            count = 0

            for name, command in data.items():
                try:
                    if isinstance(command, dict):
                        command = command.get("command", "")
                    command = str(command)
                    with self.storage._get_connection() as conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO aliases (name, command)
                            VALUES (?, ?)
                        """, (name, command))
                        conn.commit()
                    count += 1
                    logger.info("Migrated alias: %s", name)
                except Exception as e:
                    self.errors.append(f"Failed to migrate alias {name}: {e}")
                    logger.error("Failed to migrate alias %s: %s", name, e)

            return count
        except Exception as e:
            self.errors.append(f"Failed to load .aliases.json: {e}")
            logger.error("Failed to load .aliases.json: %s", e)
            return 0
    
    def migrate_templates(self) -> int:
        """Migrate templates from .templates.json."""
        templates_file = self.base_dir / ".templates.json"
        if not templates_file.exists():
            logger.info("No .templates.json found")
            return 0
        
        try:
            data = json.loads(templates_file.read_text())
            count = 0
            
            for name, template_data in data.items():
                try:
                    # TemplateManager stores templates as dict with 'command', 'description', 'created'
                    if isinstance(template_data, dict):
                        command = template_data.get("command", "")
                        description = template_data.get("description", "")
                        created = template_data.get("created")
                    else:
                        command = str(template_data)
                        description = ""
                        created = None

                    with self.storage._get_connection() as conn:
                        conn.execute("""
                            INSERT INTO templates (name, command, description, created)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(name) DO UPDATE SET
                                command = excluded.command,
                                description = excluded.description,
                                created = COALESCE(excluded.created, templates.created)
                        """, (name, command, description, created))
                        conn.commit()
                    count += 1
                    logger.info("Migrated template: %s", name)
                except Exception as e:
                    self.errors.append(f"Failed to migrate template {name}: {e}")
                    logger.error("Failed to migrate template %s: %s", name, e)
            
            return count
        except Exception as e:
            self.errors.append(f"Failed to load .templates.json: {e}")
            logger.error("Failed to load .templates.json: %s", e)
            return 0
    
    def migrate_schedule(self) -> int:
        """Migrate schedule from .schedule.json."""
        schedule_file = self.base_dir / ".schedule.json"
        if not schedule_file.exists():
            logger.info("No .schedule.json found")
            return 0
        
        try:
            data = json.loads(schedule_file.read_text())
            count = 0
            
            for name, info in data.items():
                try:
                    with self.storage._get_connection() as conn:
                        conn.execute("""
                            INSERT INTO schedules
                                (name, command, interval_seconds, enabled, last_run,
                                 server, created, run_count)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(name) DO UPDATE SET
                                command = excluded.command,
                                interval_seconds = excluded.interval_seconds,
                                enabled = excluded.enabled,
                                last_run = excluded.last_run,
                                server = excluded.server,
                                created = COALESCE(excluded.created, schedules.created),
                                run_count = excluded.run_count
                        """, (
                            name,
                            info.get("command"),
                            info.get("interval", 3600),
                            info.get("enabled", True),
                            info.get("last_run"),
                            info.get("server"),
                            info.get("created"),
                            info.get("run_count", 0),
                        ))
                        conn.commit()
                    count += 1
                    logger.info("Migrated schedule: %s", name)
                except Exception as e:
                    self.errors.append(f"Failed to migrate schedule {name}: {e}")
                    logger.error("Failed to migrate schedule %s: %s", name, e)
            
            return count
        except Exception as e:
            self.errors.append(f"Failed to load .schedule.json: {e}")
            logger.error("Failed to load .schedule.json: %s", e)
            return 0
    
    def _preview_counts(self, config: Dict) -> Dict[str, int]:
        """Count migratable items without touching SQLite (dry-run)."""
        counts = {"servers": 0, "nodes": 0, "groups": 0, "settings": 0,
                  "alerts": 0, "acl_users": 0, "aliases": 0, "templates": 0,
                  "schedules": 0}
        try:
            servers = config.get("servers", {})
            counts["servers"] = len(servers) if isinstance(servers, dict) else 0
            groups = config.get("groups", {})
            counts["groups"] = len(groups) if isinstance(groups, dict) else 0
            settings = config.get("settings", {})
            counts["settings"] = len(settings) if isinstance(settings, dict) else 0
        except Exception:
            pass
        for filename, key in [(".node_keys.json", "nodes"), ("alerts.json", "alerts"),
                              (".aliases.json", "aliases"), (".templates.json", "templates"),
                              (".schedule.json", "schedules")]:
            try:
                p = self.base_dir / filename
                if not p.exists():
                    continue
                data = json.loads(p.read_text())
                if key == "alerts":
                    rules = data.get("rules", []) if isinstance(data, dict) else []
                    counts[key] = len(rules)
                elif isinstance(data, dict):
                    counts[key] = len(data)
            except Exception as e:
                self.errors.append(f"Failed to preview {filename}: {e}")
        acl_file = self.base_dir / "data" / "acl.json"
        try:
            if acl_file.exists():
                data = json.loads(acl_file.read_text())
                users = data.get("users", {}) if isinstance(data, dict) else {}
                counts["acl_users"] = len(users) if isinstance(users, dict) else 0
        except Exception as e:
            self.errors.append(f"Failed to preview acl.json: {e}")
        return counts

    def verify(self) -> Dict:
        """Compare JSON sources with SQLite content without writing.

        Returns {"ok": bool, "checks": [{type, json, sqlite, match, detail}]}.
        """
        config = self._load_encrypted_config()
        expected = self._preview_counts(config)
        checks = []

        def _names(rows, key="name"):
            try:
                return {r[key] for r in rows}
            except Exception:
                return set()

        # servers / nodes / groups: compare name sets (strong check).
        try:
            db_servers = _names(self.storage.list_servers())
        except Exception as e:
            db_servers = set()
            self.errors.append(f"verify: cannot list servers: {e}")
        json_servers = set((config.get("servers", {}) or {}).keys())
        checks.append({"type": "servers", "json": sorted(json_servers),
                       "sqlite": sorted(db_servers),
                       "match": json_servers == db_servers})

        try:
            node_file = self.base_dir / ".node_keys.json"
            json_nodes = set(json.loads(node_file.read_text()).keys()) if node_file.exists() else set()
        except Exception:
            json_nodes = set()
        try:
            db_nodes = _names(self.storage.list_nodes())
        except Exception as e:
            db_nodes = set()
            self.errors.append(f"verify: cannot list nodes: {e}")
        checks.append({"type": "nodes", "json": sorted(json_nodes),
                       "sqlite": sorted(db_nodes), "match": json_nodes == db_nodes})

        json_groups = set((config.get("groups", {}) or {}).keys())
        try:
            db_groups = set(self.storage.list_groups().keys())
        except Exception as e:
            db_groups = set()
            self.errors.append(f"verify: cannot list groups: {e}")
        checks.append({"type": "groups", "json": sorted(json_groups),
                       "sqlite": sorted(db_groups), "match": json_groups == db_groups})

        # Other types: compare counts (settings may include SQLite defaults).
        comparators = {
            "alerts": (expected.get("alerts", 0),
                       lambda: len(self.storage.list_alert_rules())),
            "acl_users": (expected.get("acl_users", 0),
                          lambda: self._count_table("acl_users")),
            "aliases": (expected.get("aliases", 0),
                        lambda: len(self.storage.list_aliases())),
            "templates": (expected.get("templates", 0),
                          lambda: len(self.storage.list_templates())),
            "schedules": (expected.get("schedules", 0),
                          lambda: len(self.storage.list_schedules())),
        }
        for kind, (json_count, counter) in comparators.items():
            try:
                db_count = counter()
            except Exception as e:
                db_count = -1
                self.errors.append(f"verify: cannot count {kind}: {e}")
            checks.append({"type": kind, "json": json_count, "sqlite": db_count,
                           "match": json_count == db_count})

        for c in checks:
            c["detail"] = "match" if c["match"] else "MISMATCH"
        ok = all(c["match"] for c in checks) and not self.errors
        return {"ok": ok, "checks": checks, "errors": list(self.errors)}

    def _count_table(self, table: str) -> int:
        with self.storage._get_connection() as conn:
            row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            return int(row["n"])

    def migrate_all(self, dry_run: bool = False) -> Dict[str, int]:
        """Run full migration. dry_run=True writes nothing (no DB, no dirs)."""
        logger.info("Starting migration from JSON to extended SQLite storage...")

        if dry_run:
            logger.info("DRY RUN MODE - No data will be written")
            config = self._load_encrypted_config()
            # _load_encrypted_config may append errors for missing key; in dry-run
            # a missing config simply means nothing to migrate, not a failure.
            if not self.config_path.exists():
                self.errors.clear()
            results = self._preview_counts(config)
            self.migrated = False
            if self.errors:
                logger.warning("Dry-run completed with %d errors", len(self.errors))
            else:
                logger.info("Dry-run completed successfully!")
            return results

        config = self._load_encrypted_config()

        # Track per-kind success: a kind is marked imported only when its
        # section added no new errors, so later manager inits retry (rather
        # than skip) incomplete kinds and never treat partial data as final.
        tracked = (
            ("servers", lambda: self.migrate_servers(config)),
            ("nodes", self.migrate_nodes),
            ("groups", lambda: self.migrate_groups(config)),
            ("settings", lambda: self.migrate_settings(config)),
            ("alerts", self.migrate_alerts),
            ("acl_users", self.migrate_acl),
            ("aliases", self.migrate_aliases),
            ("templates", self.migrate_templates),
            ("schedules", self.migrate_schedule),
        )
        results = {}
        clean_kinds = []
        for kind, fn in tracked:
            before = len(self.errors)
            try:
                results[kind] = fn()
            except Exception as e:
                self.errors.append(f"Migration section {kind} crashed: {e}")
                results[kind] = 0
            if len(self.errors) == before:
                clean_kinds.append(kind)

        self.migrated = True

        # The bulk migration is the canonical importer: record the markers
        # for clean kinds so later manager inits treat SQLite as authoritative
        # instead of re-importing (an empty table is a valid state, e.g. after
        # a restore, and must not trigger a legacy re-import).
        for kind in clean_kinds:
            if kind in ("servers", "groups", "nodes", "alerts", "schedules",
                        "templates", "aliases"):
                try:
                    self.storage.mark_legacy_imported(kind)
                except Exception as e:
                    self.errors.append(f"Failed to record migration marker for {kind}: {e}")

        if self.errors:
            logger.warning("Migration completed with %d errors", len(self.errors))
            for error in self.errors:
                logger.error("  - %s", error)
        else:
            logger.info("Migration completed successfully!")

        return results
    
    def backup_old_files(self) -> str:
        """Backup old JSON files before migration."""
        timestamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_dir = self.base_dir / "backups" / f"json_backup_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        files_to_backup = [
            "config.json",
            ".node_keys.json",
            "alerts.json",
            ".aliases.json",
            ".templates.json",
            ".schedule.json",
        ]
        
        import shutil
        for filename in files_to_backup:
            src = self.base_dir / filename
            if src.exists():
                shutil.copy2(src, backup_dir / filename)
                logger.info("Backed up: %s", filename)
        
        # Backup ACL
        acl_src = self.base_dir / "data" / "acl.json"
        if acl_src.exists():
            (backup_dir / "data").mkdir(exist_ok=True)
            shutil.copy2(acl_src, backup_dir / "data" / "acl.json")
            logger.info("Backed up: data/acl.json")
        
        return str(backup_dir)


def run_migration(base_dir: Path = None, dry_run: bool = False) -> Dict:
    """Run migration and return results. success=False whenever errors exist."""
    manager = MigrationManager(base_dir, init_storage=not dry_run)

    if not dry_run:
        # Backup old files first
        backup_path = manager.backup_old_files()
        logger.info("Old JSON files backed up to: %s", backup_path)
    else:
        backup_path = None

    results = manager.migrate_all(dry_run=dry_run)
    success = (len(manager.errors) == 0) and (manager.migrated if not dry_run else True)

    return {
        "success": success,
        "dry_run": dry_run,
        "results": results,
        "errors": manager.errors,
        "backup_path": backup_path
    }


if __name__ == "__main__":
    import argparse
    import sys
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Migrate CloudMesh JSON data to SQLite")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--base-dir", default=None, help="Base directory holding JSON data")
    args = parser.parse_args()

    base = Path(args.base_dir) if args.base_dir else None
    results = run_migration(base_dir=base, dry_run=args.dry_run)

    print("\n=== Migration Results ===")
    print(f"Success: {results['success']}")
    if results.get("dry_run"):
        print("(dry-run: no data was written)")
    print("\nMigrated items:")
    for item, count in results['results'].items():
        print(f"  {item}: {count}")

    if results['errors']:
        print(f"\nErrors: {len(results['errors'])}")
        for error in results['errors'][:10]:  # Show first 10 errors
            print(f"  - {error}")

    if results['backup_path']:
        print(f"\nBackup location: {results['backup_path']}")

    sys.exit(0 if results["success"] else 1)
