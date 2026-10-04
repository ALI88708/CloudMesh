"""CloudMesh Storage Manager - SQLite backend for v3.2.0

This module extends the existing SQLite queue storage to support all data types:
servers, nodes, groups, settings, alerts, ACL, aliases, templates, schedules.
"""

import json
import logging
import os
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

FERNET_PREFIX = "gAAAAA"


def _is_posix() -> bool:
    return os.name != "nt"


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if _is_posix():
        try:
            os.chmod(path, 0o700)
        except OSError as e:
            logger.warning("Failed to set directory permissions on %s: %s", path, e)


def _ensure_private_file(path: Path) -> None:
    if _is_posix():
        try:
            os.chmod(path, 0o600)
        except OSError as e:
            logger.warning("Failed to set file permissions on %s: %s", path, e)


class StorageManager:
    """SQLite-based storage manager extending queue storage."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path(__file__).parent.parent

        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / "cloudmesh.db"
        self.key_path = self.base_dir / ".secret.key"
        self.backups_dir = self.base_dir / "backups"
        _ensure_private_dir(self.backups_dir)

        self._fernet = None
        self._local_lock = threading.Lock()

        self._ensure_db_file()
        # The backend owns its Fernet key: create eagerly so secrets can
        # never be written without encryption and `.secret.key` always
        # exists with private permissions right after init.
        self._get_or_create_key()
        # Initialize additional tables
        self._init_extended_tables()
        _ensure_private_file(self.db_path)
        _ensure_private_file(self.key_path)

    def _ensure_db_file(self) -> None:
        """Create the DB file with private permissions if missing."""
        try:
            fd = os.open(str(self.db_path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        except OSError as e:
            logger.warning("Failed to pre-create database file: %s", e)
        _ensure_private_file(self.db_path)

    def _get_or_create_key(self) -> bytes:
        """Load or atomically create the Fernet key with 0600 perms."""
        if self.key_path.exists():
            try:
                key = self.key_path.read_bytes().strip()
                Fernet(key)  # validate
                _ensure_private_file(self.key_path)
                return key
            except Exception as e:
                logger.error("Existing secret key is invalid: %s", e)
                raise
        key = Fernet.generate_key()
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=str(self.key_path.parent),
                prefix=f".{self.key_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                temp_path = Path(tmp.name)
                tmp.write(key)
                if _is_posix():
                    os.chmod(temp_path, 0o600)
            try:
                if _is_posix():
                    os.link(temp_path, self.key_path)
                else:
                    if not self.key_path.exists():
                        os.replace(temp_path, self.key_path)
                    else:
                        return self.key_path.read_bytes().strip()
            except FileExistsError:
                return self.key_path.read_bytes().strip()
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass
        _ensure_private_file(self.key_path)
        return key

    @property
    def fernet(self) -> Fernet:
        """Get Fernet encryption instance (always available)."""
        if self._fernet is None:
            self._fernet = Fernet(self._get_or_create_key())
        return self._fernet

    def _encrypt_secret(self, value: Optional[str]) -> Optional[str]:
        """Encrypt a secret; None/empty stays NULL/empty without loss."""
        if value is None:
            return None
        if value == "":
            return ""
        return self.fernet.encrypt(value.encode()).decode()

    def _decrypt_secret(self, value: Optional[str], context: str = "") -> Optional[str]:
        """Decrypt a stored secret.

        Returns plaintext. Legacy plaintext rows (from pre-encryption DBs)
        are returned as-is with a warning so migration does not lose data.
        Undecryptable Fernet tokens return None (never the ciphertext).
        """
        if value is None or value == "":
            return value
        try:
            return self.fernet.decrypt(value.encode()).decode()
        except InvalidToken as e:
            if not value.startswith(FERNET_PREFIX):
                logger.warning(
                    "Legacy plaintext secret for %s; re-encrypt on next write", context
                )
                return value
            logger.warning("Failed to decrypt secret for %s: %s", context, e)
            return None
        except Exception as e:
            logger.warning("Failed to decrypt secret for %s: %s", context, e)
            return None
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 30000")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error as e:
            logger.warning("Failed to set PRAGMAs: %s", e)
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

            # Schema evolution for pre-existing databases.
            self._ensure_column(conn, "nodes", "tls", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "nodes", "ca_file", "TEXT")
            self._ensure_column(conn, "schedules", "server", "TEXT")
            self._ensure_column(conn, "schedules", "created", "TEXT")
            self._ensure_column(conn, "schedules", "run_count", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "templates", "description", "TEXT DEFAULT ''")
            self._ensure_column(conn, "templates", "created", "TEXT")

            conn.commit()
    
    # Server operations
    def add_server(self, name: str, host: str, user: str, port: int = 22,
                   key_path: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Add a server. Secrets are always encrypted, never plaintext."""
        with self._get_connection() as conn:
            try:
                encrypted_password = self._encrypt_secret(password)

                conn.execute("""
                    INSERT INTO servers (name, host, user, port, key_path, password)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, host, user, port, key_path, encrypted_password))
                conn.commit()
                return True
            except sqlite3.IntegrityError as e:
                if "UNIQUE" in str(e).upper():
                    logger.error("Server '%s' already exists", name)
                else:
                    logger.error("Failed to add server '%s': %s", name, e)
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
                server = dict(row)
                # Decrypt password (never return ciphertext as plaintext)
                if server.get("password"):
                    server["password"] = self._decrypt_secret(
                        server["password"], context=f"server {name}"
                    )
                return server
            return None

    def list_servers(self) -> List[Dict]:
        """List all servers."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM servers").fetchall()
            servers = []
            for row in rows:
                server = dict(row)
                # Decrypt password
                if server.get("password"):
                    server["password"] = self._decrypt_secret(
                        server["password"], context=f"server {server.get('name')}"
                    )
                servers.append(server)
            return servers
    
    def update_server_status(self, name: str, status: str) -> bool:
        """Update server status."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE servers SET status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE name = ?
            """, (status, name))
            conn.commit()
            return cursor.rowcount > 0

    def update_server_os_type(self, name: str, os_type: str) -> bool:
        """Update server OS type."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                UPDATE servers SET os_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE name = ?
            """, (os_type, name))
            conn.commit()
            return cursor.rowcount > 0
    
    # Node operations
    def add_node(self, name: str, host: str, port: int = 9999, auth_key: str = "",
                 tls: bool = False, ca_file: Optional[str] = None) -> bool:
        """Add a node, encrypting nonempty auth keys; None is stored as empty.

        tls and ca_file store connection preferences without validating the
        certificate path. Return True after insertion or False on a constraint
        violation, including duplicate names. Other database errors and key
        loading or encryption errors propagate.
        """
        with self._get_connection() as conn:
            try:
                encrypted_key = self._encrypt_secret(auth_key)
                if encrypted_key is None:
                    encrypted_key = ""

                conn.execute("""
                    INSERT INTO nodes (name, host, port, auth_key, tls, ca_file)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (name, host, port, encrypted_key, int(bool(tls)), ca_file))
                conn.commit()
                return True
            except sqlite3.IntegrityError as e:
                if "UNIQUE" in str(e).upper():
                    logger.error("Node '%s' already exists", name)
                else:
                    logger.error("Failed to add node '%s': %s", name, e)
                return False
    
    def upsert_node(self, name: str, host: str, port: int = 9999, auth_key: str = "",
                    tls: bool = False, ca_file: Optional[str] = None) -> bool:
        """Insert or update a node atomically.

        Unlike remove+re-add, a failed upsert leaves the existing row
        (and its encrypted auth key) intact.
        """
        with self._get_connection() as conn:
            try:
                encrypted_key = self._encrypt_secret(auth_key)
                if encrypted_key is None:
                    encrypted_key = ""
                conn.execute("""
                    INSERT INTO nodes (name, host, port, auth_key, tls, ca_file)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                        host = excluded.host,
                        port = excluded.port,
                        auth_key = excluded.auth_key,
                        tls = excluded.tls,
                        ca_file = excluded.ca_file,
                        updated_at = CURRENT_TIMESTAMP
                """, (name, host, port, encrypted_key, int(bool(tls)), ca_file))
                conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error("Failed to upsert node '%s': %s", name, e)
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
                node = dict(row)
                # Decrypt auth_key
                if node.get("auth_key"):
                    node["auth_key"] = self._decrypt_secret(
                        node["auth_key"], context=f"node {name}"
                    )
                return node
            return None

    def list_nodes(self) -> List[Dict]:
        """List all nodes."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM nodes").fetchall()
            nodes = []
            for row in rows:
                node = dict(row)
                # Decrypt auth_key
                if node.get("auth_key"):
                    node["auth_key"] = self._decrypt_secret(
                        node["auth_key"], context=f"node {node.get('name')}"
                    )
                nodes.append(node)
            return nodes

    def update_node_auth_key(self, name: str, auth_key: str) -> bool:
        """Update node auth key."""
        with self._get_connection() as conn:
            encrypted_key = self._encrypt_secret(auth_key)
            if encrypted_key is None:
                encrypted_key = ""

            cursor = conn.execute("""
                UPDATE nodes SET auth_key = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE name = ?
            """, (encrypted_key, name))
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
                          threshold: float, operator: str, severity: str,
                          timestamp=None) -> None:
        """Add alert to history. An explicit timestamp preserves original event times on import."""
        with self._get_connection() as conn:
            if timestamp is None:
                conn.execute("""
                    INSERT INTO alert_history (rule_name, server, metric, value, threshold, operator, severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (rule_name, server, metric, value, threshold, operator, severity))
            else:
                conn.execute("""
                    INSERT INTO alert_history (rule_name, server, metric, value, threshold, operator, severity, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (rule_name, server, metric, value, threshold, operator, severity, timestamp))
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

    def list_alert_cooldowns(self) -> Dict[str, float]:
        """Return {rule|server: timestamp}, with times in seconds since the epoch.

        Database errors propagate.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT rule_name, server, last_notified FROM alert_cooldowns"
            ).fetchall()
            return {f"{r['rule_name']}|{r['server']}": r["last_notified"] for r in rows}
    
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
    
    # Schedule operations
    def upsert_schedule(self, name: str, command: str, interval_seconds: int,
                        enabled: bool = True, last_run=None, server=None,
                        created=None, run_count: int = 0) -> None:
        """Insert or update a scheduled task by name.

        Preserve an existing created value when created is None; other supplied
        fields are overwritten. interval_seconds is stored without range validation.
        Database errors propagate.
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO schedules
                    (name, command, interval_seconds, enabled, last_run, server, created, run_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    command = excluded.command,
                    interval_seconds = excluded.interval_seconds,
                    enabled = excluded.enabled,
                    last_run = excluded.last_run,
                    server = excluded.server,
                    created = COALESCE(excluded.created, schedules.created),
                    run_count = excluded.run_count
            """, (name, command, interval_seconds, int(bool(enabled)), last_run,
                  server, created, run_count or 0))
            conn.commit()

    def remove_schedule(self, name: str) -> bool:
        """Delete a scheduled task and return whether a row existed.

        Database errors propagate.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM schedules WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    def list_schedules(self) -> List[Dict]:
        """List all scheduled tasks."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM schedules").fetchall()
            return [dict(row) for row in rows]

    # Template operations
    def upsert_template(self, name: str, command: str, description: str = "",
                        created=None) -> None:
        """Insert or update a command template by name.

        Preserve an existing created value when created is None, and store an
        empty description for a false value. Database errors propagate.
        """
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO templates (name, command, description, created)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    command = excluded.command,
                    description = excluded.description,
                    created = COALESCE(excluded.created, templates.created)
            """, (name, command, description or "", created))
            conn.commit()

    def remove_template(self, name: str) -> bool:
        """Delete a command template and return whether a row existed.

        Database errors propagate.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM templates WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    def list_templates(self) -> List[Dict]:
        """List all command templates."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM templates").fetchall()
            return [dict(row) for row in rows]

    # Alias operations
    def upsert_alias(self, name: str, command: str) -> None:
        """Insert or replace a command alias."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO aliases (name, command)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET command = excluded.command
            """, (name, command))
            conn.commit()

    def remove_alias(self, name: str) -> bool:
        """Delete a command alias and return whether a row existed.

        Database errors propagate.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM aliases WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    def list_aliases(self) -> Dict[str, str]:
        """Return {name: command} alias map."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT name, command FROM aliases").fetchall()
            return {row["name"]: row["command"] for row in rows}

    # Backup operations
    def _ensure_column(self, conn, table: str, column: str, ddl: str) -> None:
        """Attempt to add a missing column, suppressing SQLite errors.

        table, column, and ddl must be trusted SQL fragments. The caller owns
        the connection and commits the schema change.
        """
        try:
            existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        except sqlite3.Error:
            return
        if column not in existing:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            except sqlite3.Error as e:
                logger.warning("Failed to add column %s.%s: %s", table, column, e)

    def legacy_imported(self, kind: str) -> bool:
        """Return whether the legacy JSON import marker for kind is set.

        Return False if the marker cannot be read. A set marker records an
        import attempt, not that every item was imported successfully.

        NOTE: get_setting JSON-decodes, so a stored "1" reads back as int 1;
        normalize before comparing.
        """
        try:
            return str(self.get_setting(f"legacy_{kind}_imported", None)) == "1"
        except Exception:
            return False

    def mark_legacy_imported(self, kind: str) -> None:
        """Attempt to record the legacy import marker for kind, suppressing errors."""
        try:
            self.set_setting(f"legacy_{kind}_imported", "1")
        except Exception as e:
            logger.warning("Failed to record legacy import marker for %s: %s", kind, e)

    def _validated_max_backups(self, default: int = 10) -> int:
        try:
            raw = self.get_setting("max_backups", default)
            value = int(raw)
            if value < 1:
                return default
            return min(value, 100)
        except (TypeError, ValueError):
            return default

    def backup_database(self, exclude: Optional[str] = None) -> str:
        """Create a backup of the database using SQLite backup API.

        `exclude` is a backup filename that cleanup must never delete
        (used by restore to protect its source file).
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _ensure_private_dir(self.backups_dir)
        suffix = 0
        while True:
            suffix_part = f"_{suffix}" if suffix else ""
            backup_path = self.backups_dir / f"cloudmesh_backup_{timestamp}{suffix_part}.db"
            try:
                fd = os.open(str(backup_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(fd)
                break
            except FileExistsError:
                suffix += 1
                continue

        # Use SQLite backup API for proper WAL handling (consistent even with open readers)
        with self._get_connection() as source:
            dest = sqlite3.connect(str(backup_path))
            try:
                source.backup(dest)
                dest.commit()
            finally:
                dest.close()

        _ensure_private_file(backup_path)

        # Cleanup old backups (never delete the excluded restore source).
        max_backups = self._validated_max_backups(10)
        excluded = Path(exclude).name if exclude else None
        backups = sorted(self.backups_dir.glob("cloudmesh_backup_*.db"))
        while len(backups) > max_backups:
            oldest = backups.pop(0)
            if excluded is not None and oldest.name == excluded:
                logger.warning(
                    "Retention limit reached but keeping restore source %s", oldest.name
                )
                break
            try:
                oldest.unlink()
            except OSError as e:
                logger.warning("Failed to remove old backup %s: %s", oldest, e)
                break

        return str(backup_path)

    def _resolve_backup_path(self, backup_path: str) -> Path:
        backup_file = Path(backup_path)
        if not backup_file.is_absolute():
            backup_file = self.backups_dir / backup_path
        backups_dir = self.backups_dir.resolve()
        try:
            resolved = backup_file.resolve()
        except OSError as e:
            logger.error("Invalid backup path: %s", e)
            raise ValueError("Invalid backup path")
        if backups_dir not in resolved.parents and resolved != backups_dir:
            logger.error("Path traversal blocked: %s", backup_path)
            raise ValueError("Restore path must be inside the backups directory")
        return resolved

    @staticmethod
    def _is_sqlite_db(path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                return f.read(16) == b"SQLite format 3\x00"
        except OSError:
            return False

    @staticmethod
    def _source_table_names_ro(path: Path) -> Optional[List[str]]:
        """List tables in a backup opened strictly read-only.

        Returns None if the file cannot be opened as a database. Opening
        with mode=ro guarantees a missing file can never be silently
        recreated as an empty database.
        """
        try:
            uri = path.as_uri() + "?mode=ro"
        except (OSError, ValueError) as e:
            logger.error("Cannot build read-only URI for backup: %s", e)
            return None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=30)
        except sqlite3.Error as e:
            logger.error("Cannot open backup read-only: %s", e)
            return None
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            return [r[0] for r in rows]
        except sqlite3.Error as e:
            logger.error("Cannot read backup schema: %s", e)
            return None
        finally:
            conn.close()

    def restore_backup(self, backup_path: str) -> bool:
        """Restore database from backup using the SQLite backup API."""
        try:
            backup_file = self._resolve_backup_path(backup_path)
        except ValueError:
            return False

        def _valid_source() -> Optional[List[str]]:
            if not backup_file.exists():
                logger.error("Backup not found: %s", backup_path)
                return None
            if not self._is_sqlite_db(backup_file):
                logger.error("Backup is not a valid SQLite database: %s", backup_path)
                return None
            tables = self._source_table_names_ro(backup_file)
            if not tables or "servers" not in tables:
                logger.error(
                    "Backup %s has no CloudMesh schema; refusing to overwrite live database",
                    backup_path,
                )
                return None
            return tables

        if _valid_source() is None:
            return False

        # Create safety backup of current state before overwriting, protecting
        # the restore source from retention cleanup (max_backups=1 would
        # otherwise delete it, then sqlite would recreate an empty DB).
        try:
            self.backup_database(exclude=backup_file.name)
        except Exception as e:
            logger.error("Failed to create safety backup before restore: %s", e)
            return False

        # Re-verify: the source must still exist after cleanup ran.
        if _valid_source() is None:
            return False

        # Restore via backup API so WAL/-shm state stays consistent even
        # if another connection briefly exists; checkpoint first.
        try:
            with self._get_connection() as conn:
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except sqlite3.Error:
                    pass
            source = sqlite3.connect(backup_file.as_uri() + "?mode=ro", uri=True, timeout=30)
            try:
                dest = sqlite3.connect(str(self.db_path), timeout=30)
                try:
                    source.backup(dest)
                    dest.commit()
                finally:
                    dest.close()
            finally:
                source.close()
        except Exception as e:
            logger.error("Restore failed: %s", e)
            return False
        _ensure_private_file(self.db_path)
        return True
    
    def list_backups(self) -> List[str]:
        """List available backups."""
        return sorted([str(p) for p in self.backups_dir.glob("cloudmesh_backup_*.db")], reverse=True)
