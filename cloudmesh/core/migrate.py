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

from storage import StorageManager

logger = logging.getLogger(__name__)


class MigrationManager:
    """Handle migration from JSON to extended SQLite storage."""
    
    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        
        self.base_dir = Path(base_dir)
        self.config_path = self.base_dir / "config.json"
        self.key_path = self.base_dir / ".secret.key"
        self.storage = StorageManager(base_dir)
        
        self.migrated = False
        self.errors = []
    
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
            logger.error("Cannot decrypt config - missing encryption key")
            return {}
        
        try:
            encrypted = self.config_path.read_bytes()
            decrypted = fernet.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error("Failed to decrypt config: %s", e)
            return {}
    
    def migrate_servers(self, config: Dict) -> int:
        """Migrate servers from config."""
        servers = config.get("servers", {})
        count = 0
        
        for name, info in servers.items():
            try:
                self.storage.add_server(
                    name=name,
                    host=info.get("host"),
                    user=info.get("user"),
                    port=info.get("port", 22),
                    key_path=info.get("key_path"),
                    password=info.get("password")
                )
                
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
                    self.storage.add_node(
                        name=name,
                        host=info.get("host"),
                        port=info.get("port", 9999),
                        auth_key=info.get("key", "")
                    )
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
                self.storage.create_group(group_name)
                
                for device in devices:
                    # Try to determine if it's a server or node
                    device_type = "server"  # Default
                    if self.storage.get_node(device):
                        device_type = "node"
                    
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
                    self.storage.add_alert_rule(
                        name=rule.get("name"),
                        metric=rule.get("metric"),
                        threshold=rule.get("threshold"),
                        operator=rule.get("operator", "gt"),
                        server=rule.get("server"),
                        severity=rule.get("severity", "warning"),
                        cooldown=rule.get("cooldown", 300)
                    )
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
                    logger.warning("Failed to migrate alert history entry: %s", e)
            
            # Migrate cooldowns
            for key, timestamp in data.get("last_notified", {}).items():
                try:
                    rule_name, server = key.split("|")
                    self.storage.set_alert_cooldown(rule_name, server, timestamp)
                except Exception as e:
                    logger.warning("Failed to migrate alert cooldown: %s", e)
            
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
            
            for name, command in data.items():
                try:
                    with self.storage._get_connection() as conn:
                        conn.execute("""
                            INSERT OR REPLACE INTO templates (name, command)
                            VALUES (?, ?)
                        """, (name, command))
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
                            INSERT OR REPLACE INTO schedules (name, command, interval_seconds, enabled, last_run)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            name,
                            info.get("command"),
                            info.get("interval"),
                            info.get("enabled", True),
                            info.get("last_run")
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
    
    def migrate_all(self) -> Dict[str, int]:
        """Run full migration."""
        logger.info("Starting migration from JSON to extended SQLite storage...")
        
        config = self._load_encrypted_config()
        
        results = {
            "servers": self.migrate_servers(config),
            "nodes": self.migrate_nodes(),
            "groups": self.migrate_groups(config),
            "settings": self.migrate_settings(config),
            "alerts": self.migrate_alerts(),
            "acl_users": self.migrate_acl(),
            "aliases": self.migrate_aliases(),
            "templates": self.migrate_templates(),
            "schedules": self.migrate_schedule(),
        }
        
        self.migrated = True
        
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
    """Run migration and return results."""
    manager = MigrationManager(base_dir)
    
    if not dry_run:
        # Backup old files first
        backup_path = manager.backup_old_files()
        logger.info("Old JSON files backed up to: %s", backup_path)
    
    results = manager.migrate_all()
    
    return {
        "success": manager.migrated,
        "results": results,
        "errors": manager.errors,
        "backup_path": backup_path if not dry_run else None
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    dry_run = "--dry-run" in sys.argv
    results = run_migration(dry_run=dry_run)
    
    print("\n=== Migration Results ===")
    print(f"Success: {results['success']}")
    print("\nMigrated items:")
    for item, count in results['results'].items():
        print(f"  {item}: {count}")
    
    if results['errors']:
        print(f"\nErrors: {len(results['errors'])}")
        for error in results['errors'][:10]:  # Show first 10 errors
            print(f"  - {error}")
    
    if results['backup_path']:
        print(f"\nBackup location: {results['backup_path']}")
