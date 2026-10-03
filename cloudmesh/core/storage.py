"""CloudMesh Storage Manager - SQLite backend for v3.2.0

This module extends the existing SQLite queue storage to support all data types:
servers, nodes, groups, settings, alerts, ACL, aliases, templates, schedules.
"""

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class StorageManager:
    """SQLite-based storage manager extending queue storage."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent
        
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / "cloudmesh.db"
        self.key_path = self.base_dir / ".secret.key"
        self.backups_dir = self.base_dir / "backups"
        self.backups_dir.mkdir(exist_ok=True)
        
        self._fernet = None
        self._local_lock = threading.Lock()
        
        # Initialize additional tables
        self._init_extended_tables()
    
    @property
    def fernet(self) -> Fernet:
        """Get Fernet encryption instance."""
        if self._fernet is None:
            if self.key_path.exists():
                key = self.key_path.read_bytes()
                self._fernet = Fernet(key)
        return self._fernet
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_extended_tables(self):
        """Initialize extended tables for full data storage."""
        with self._get_connection() as conn:
            # Servers table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    host TEXT NOT NULL,
                    user TEXT NOT NULL,
                    port INTEGER DEFAULT 22,
                    key_path TEXT,
                    password TEXT,
                    status TEXT DEFAULT 'unknown',
                    os_type TEXT DEFAULT 'linux',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Nodes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    host TEXT NOT NULL,
                    port INTEGER DEFAULT 9999,
                    auth_key TEXT NOT NULL,
                    status TEXT DEFAULT 'unknown',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Groups table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Group members table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    device_name TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
                    UNIQUE(group_id, device_name, device_type)
                )
            """)
            
            # Settings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Alerts rules table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    metric TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    operator TEXT DEFAULT 'gt',
                    server TEXT,
                    severity TEXT DEFAULT 'warning',
                    cooldown INTEGER DEFAULT 300,
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Alerts history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT NOT NULL,
                    server TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL,
                    threshold REAL NOT NULL,
                    operator TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Alert cooldown tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_cooldowns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_name TEXT NOT NULL,
                    server TEXT NOT NULL,
                    last_notified TIMESTAMP NOT NULL,
                    UNIQUE(rule_name, server)
                )
            """)
            
            # ACL users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS acl_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until TIMESTAMP
                )
            """)
            
            # ACL roles table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS acl_roles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    permissions TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Aliases table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    command TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Templates table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    command TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Schedule table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    command TEXT NOT NULL,
                    interval_seconds INTEGER NOT NULL,
                    enabled BOOLEAN DEFAULT 1,
                    last_run TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert default settings if not exists
            conn.execute("""
                INSERT OR IGNORE INTO settings (key, value) 
                VALUES ('monitor_interval', '5'), ('max_backups', '10')
            """)
            
            # Insert default ACL roles if not exists
            conn.execute("""
                INSERT OR IGNORE INTO acl_roles (name, permissions) 
                VALUES ('admin', '*'), ('viewer', '["monitor", "ping", "list", "info"]')
            """)
            
            conn.commit()
    
    # Server operations
    def add_server(self, name: str, host: str, user: str, port: int = 22,
                   key_path: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Add a server."""
        with self._get_connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO servers (name, host, user, port, key_path, password)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, host, user, port, key_path, password))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                logger.error("Server '%s' already exists", name)
                return False
    
    def remove_server(self, name: str) -> bool:
        """Remove a server."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM servers WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_server(self, name: str) -> Optional[Dict]:
        """Get server info."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM servers WHERE name = ?", (name,)).fetchone()
            if row:
                return dict(row)
            return None
    
    def list_servers(self) -> List[Dict]:
        """List all servers."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM servers").fetchall()
            return [dict(row) for row in rows]
    
    def update_server_status(self, name: str, status: str) -> bool:
        """Update server status."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE servers SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE name = ?
            """, (status, name))
            conn.commit()
            return cursor.rowcount > 0
    
    # Node operations
    def add_node(self, name: str, host: str, port: int = 9999, auth_key: str = "") -> bool:
        """Add a node."""
        with self._get_connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO nodes (name, host, port, auth_key)
                    VALUES (?, ?, ?, ?)
                """, (name, host, port, auth_key))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                logger.error("Node '%s' already exists", name)
                return False
    
    def remove_node(self, name: str) -> bool:
        """Remove a node."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM nodes WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_node(self, name: str) -> Optional[Dict]:
        """Get node info."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE name = ?", (name,)).fetchone()
            if row:
                return dict(row)
            return None
    
    def list_nodes(self) -> List[Dict]:
        """List all nodes."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM nodes").fetchall()
            return [dict(row) for row in rows]
    
    def update_node_auth_key(self, name: str, auth_key: str) -> bool:
        """Update node auth key."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE nodes SET auth_key = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE name = ?
            """, (auth_key, name))
            conn.commit()
            return cursor.rowcount > 0
    
    # Settings operations
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except json.JSONDecodeError:
                    return row["value"]
            return default
    
    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value."""
        with self._get_connection() as conn:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            conn.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
            """, (key, str(value), str(value)))
            conn.commit()
    
    # Alert operations
    def add_alert_rule(self, name: str, metric: str, threshold: float, operator: str = "gt",
                      server: Optional[str] = None, severity: str = "warning",
                      cooldown: int = 300) -> bool:
        """Add an alert rule."""
        with self._get_connection() as conn:
            try:
                conn.execute("""
                    INSERT INTO alert_rules (name, metric, threshold, operator, server, severity, cooldown)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (name, metric, threshold, operator, server, severity, cooldown))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                logger.error("Alert rule '%s' already exists", name)
                return False
    
    def remove_alert_rule(self, name: str) -> bool:
        """Remove an alert rule."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM alert_rules WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
    
    def list_alert_rules(self) -> List[Dict]:
        """List all alert rules."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM alert_rules").fetchall()
            return [dict(row) for row in rows]
    
    def add_alert_history(self, rule_name: str, server: str, metric: str, value: float,
                         threshold: float, operator: str, severity: str) -> None:
        """Add alert to history."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO alert_history (rule_name, server, metric, value, threshold, operator, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rule_name, server, metric, value, threshold, operator, severity))
            conn.commit()
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get alert history."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM alert_history 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def clear_alert_history(self) -> None:
        """Clear alert history."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM alert_history")
            conn.commit()
    
    def get_alert_cooldown(self, rule_name: str, server: str) -> Optional[float]:
        """Get last notification time for cooldown check."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT last_notified FROM alert_cooldowns 
                WHERE rule_name = ? AND server = ?
            """, (rule_name, server)).fetchone()
            if row:
                return row["last_notified"]
            return None
    
    def set_alert_cooldown(self, rule_name: str, server: str, timestamp: float) -> None:
        """Set last notification time."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO alert_cooldowns (rule_name, server, last_notified)
                VALUES (?, ?, ?)
                ON CONFLICT(rule_name, server) DO UPDATE SET last_notified = ?
            """, (rule_name, server, timestamp, timestamp))
            conn.commit()
    
    # Group operations
    def create_group(self, name: str) -> bool:
        """Create a group."""
        with self._get_connection() as conn:
            try:
                conn.execute("INSERT INTO groups (name) VALUES (?)", (name,))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                logger.error("Group '%s' already exists", name)
                return False
    
    def delete_group(self, name: str) -> bool:
        """Delete a group."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM groups WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
    
    def add_to_group(self, group_name: str, device_name: str, device_type: str = "server") -> bool:
        """Add device to group."""
        with self._get_connection() as conn:
            # Get group id
            group = conn.execute("SELECT id FROM groups WHERE name = ?", (group_name,)).fetchone()
            if not group:
                return False
            
            try:
                conn.execute("""
                    INSERT INTO group_members (group_id, device_name, device_type)
                    VALUES (?, ?, ?)
                """, (group["id"], device_name, device_type))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                logger.warning("Device '%s' already in group '%s'", device_name, group_name)
                return False
    
    def remove_from_group(self, group_name: str, device_name: str) -> bool:
        """Remove device from group."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM group_members 
                WHERE group_id = (SELECT id FROM groups WHERE name = ?) 
                AND device_name = ?
            """, (group_name, device_name))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_group_devices(self, group_name: str) -> List[str]:
        """Get devices in a group."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT device_name FROM group_members 
                WHERE group_id = (SELECT id FROM groups WHERE name = ?)
            """, (group_name,)).fetchall()
            return [row["device_name"] for row in rows]
    
    def list_groups(self) -> Dict[str, List[str]]:
        """List all groups with their devices."""
        with self._get_connection() as conn:
            groups = conn.execute("SELECT name, id FROM groups").fetchall()
            result = {}
            for group in groups:
                devices = conn.execute("""
                    SELECT device_name FROM group_members WHERE group_id = ?
                """, (group["id"],)).fetchall()
                result[group["name"]] = [d["device_name"] for d in devices]
            return result
    
    # Backup operations
    def backup_database(self) -> str:
        """Create a backup of the database."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = self.backups_dir / f"cloudmesh_backup_{timestamp}.db"
        
        # Copy database file
        import shutil
        shutil.copy2(self.db_path, backup_path)
        
        # Cleanup old backups
        max_backups = self.get_setting("max_backups", 10)
        backups = sorted(self.backups_dir.glob("cloudmesh_backup_*.db"))
        while len(backups) > max_backups:
            oldest = backups.pop(0)
            oldest.unlink()
        
        return str(backup_path)
    
    def restore_backup(self, backup_path: str) -> bool:
        """Restore database from backup."""
        backup_file = Path(backup_path)
        if not backup_file.is_absolute():
            backup_file = self.backups_dir / backup_path
        
        if not backup_file.exists():
            logger.error("Backup not found: %s", backup_path)
            return False
        
        # Create backup of current state
        self.backup_database()
        
        # Restore
        import shutil
        shutil.copy2(backup_file, self.db_path)
        return True
    
    def list_backups(self) -> List[str]:
        """List available backups."""
        return sorted([str(p) for p in self.backups_dir.glob("cloudmesh_backup_*.db")], reverse=True)
