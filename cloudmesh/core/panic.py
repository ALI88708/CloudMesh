import base64
import hashlib
import json
import os
import secrets
import shutil
from pathlib import Path
from datetime import datetime

from cryptography.fernet import Fernet

from core.shamir import ShamirSecretSharing


class PanicManager:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path(__file__).parent.parent)
        self.secret_key_file = self.base_dir / ".secret.key"
        self.node_keys_file = self.base_dir / ".node_keys.json"
        self.panic_log_file = self.base_dir / ".panic_log.json"
        self.pending_file = self.base_dir / ".panic_pending.json"

    def _log_panic(self, actions):
        entries = []
        if self.panic_log_file.exists():
            try:
                entries = json.loads(self.panic_log_file.read_text())
            except Exception:
                entries = []
        entry = {
            "timestamp": datetime.now().isoformat(),
            "actions": actions,
        }
        entries.append(entry)
        entries = entries[-100:]
        self.panic_log_file.write_text(json.dumps(entries, indent=2))

    def _load_pending(self):
        if self.pending_file.exists():
            try:
                return json.loads(self.pending_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_pending(self, pending):
        self.pending_file.write_text(json.dumps(pending, indent=2))

    def dry_run(self):
        actions = []
        if self.secret_key_file.exists():
            actions.append(("rotate_secret_key", "Will generate new Fernet encryption key"))
        else:
            actions.append(("rotate_secret_key", "No key file found — will create new one"))

        if self.node_keys_file.exists():
            try:
                nodes = json.loads(self.node_keys_file.read_text())
                for name in nodes:
                    actions.append(("rotate_node_key", f"Will rotate auth key for node '{name}' (local + remote)"))
                actions.append(("backup_node_keys", "Will backup .node_keys.json"))
            except Exception:
                actions.append(("rotate_node_keys", "Will regenerate .node_keys.json"))
        else:
            actions.append(("rotate_node_keys", "No .node_keys.json found — nothing to rotate"))

        actions.append(("log_panic", "Will record panic event in .panic_log.json"))
        return actions

    def execute_panic(self):
        actions = []

        if self.secret_key_file.exists():
            shutil.copy2(self.secret_key_file, self.secret_key_file.with_suffix(".key.bak"))
            new_key = Fernet.generate_key()
            self.secret_key_file.write_bytes(new_key)
            actions.append("Rotated .secret.key (backup saved as .secret.key.bak)")
        else:
            new_key = Fernet.generate_key()
            self.secret_key_file.write_bytes(new_key)
            actions.append("Created new .secret.key (none existed before)")

        if self.node_keys_file.exists():
            try:
                from core.node_client import NodeClient
                nodes = json.loads(self.node_keys_file.read_text())
                shutil.copy2(self.node_keys_file, self.node_keys_file.with_suffix(".json.bak"))
                pending = self._load_pending()
                for name, info in nodes.items():
                    new_auth = secrets.token_hex(32)
                    client = NodeClient(info["host"], info["port"], info["key"])
                    try:
                        result = client.rotate_key(new_auth, timeout=5)
                        if result.get("success"):
                            nodes[name]["key"] = new_auth
                            actions.append(f"Rotated '{name}' — confirmed remotely")
                        else:
                            pending[name] = {"host": info["host"], "port": info["port"],
                                             "old_key": info["key"], "new_key": new_auth}
                            actions.append(f"Rotated '{name}' locally, remote confirm FAILED — retry needed")
                    except Exception as e:
                        pending[name] = {"host": info["host"], "port": info["port"],
                                         "old_key": info["key"], "new_key": new_auth}
                        actions.append(f"Node '{name}' unreachable ({e}) — rotation PENDING")
                self.node_keys_file.write_text(json.dumps(nodes, indent=2))
                if pending:
                    self._save_pending(pending)
                    actions.append(f"{len(pending)} node(s) pending — use 'cm panic retry-pending' later")
                actions.append(f"Rotated auth keys for {len(nodes)} node(s) (backup saved as .node_keys.json.bak)")
            except Exception as e:
                actions.append(f"Error rotating node keys: {e}")
        else:
            actions.append("No .node_keys.json found — skipped node key rotation")

        self._log_panic(actions)
        actions.append(f"Panic event logged at {datetime.now().isoformat()}")

        return actions

    def retry_pending(self):
        pending = self._load_pending()
        if not pending:
            return ["No pending rotations"]

        from core.node_client import NodeClient
        actions = []
        remaining = {}

        for name, info in pending.items():
            client = NodeClient(info["host"], info["port"], info["old_key"])
            try:
                result = client.rotate_key(info["new_key"], timeout=5)
                if result.get("success"):
                    if self.node_keys_file.exists():
                        nodes = json.loads(self.node_keys_file.read_text())
                        if name in nodes:
                            nodes[name]["key"] = info["new_key"]
                            self.node_keys_file.write_text(json.dumps(nodes, indent=2))
                    actions.append(f"Retry SUCCESS: '{name}' rotated remotely")
                else:
                    remaining[name] = info
                    actions.append(f"Retry FAILED: '{name}' — still pending")
            except Exception as e:
                remaining[name] = info
                actions.append(f"Retry FAILED: '{name}' ({e}) — still pending")

        if remaining:
            self._save_pending(remaining)
            actions.append(f"{len(remaining)} node(s) still pending")
        else:
            self.pending_file.unlink(missing_ok=True)
            actions.append("All pending rotations completed — pending file removed")

        self._log_panic(actions)
        return actions


class TripwireManager:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path(__file__).parent.parent)
        self.node_keys_file = self.base_dir / ".node_keys.json"
        self.tripwire_log = self.base_dir / ".tripwire_log.json"

    def _load_keys(self):
        if self.node_keys_file.exists():
            try:
                return json.loads(self.node_keys_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_keys(self, keys):
        self.node_keys_file.write_text(json.dumps(keys, indent=2))
        try:
            if os.name != "nt":
                os.chmod(self.node_keys_file, 0o600)
        except Exception:
            pass

    def plant(self, node_name, host, port=9999):
        keys = self._load_keys()
        if node_name in keys:
            existing = keys[node_name]
            if existing.get("tripwire"):
                return f"Tripwire '{node_name}' already planted"
            return f"Node '{node_name}' already exists (not a tripwire — use a different name)"

        tripwire_key = secrets.token_hex(32)
        keys[node_name] = {
            "host": host,
            "port": port,
            "key": tripwire_key,
            "tripwire": True,
            "planted_at": datetime.now().isoformat(),
        }
        self._save_keys(keys)

        entry = {
            "event": "planted",
            "node_name": node_name,
            "host": host,
            "timestamp": datetime.now().isoformat(),
            "key_hash": hashlib.sha256(tripwire_key.encode()).hexdigest()[:16],
        }
        self._log_tripwire_event(entry)

        return tripwire_key

    def check(self, key_used):
        keys = self._load_keys()
        for name, info in keys.items():
            if info.get("tripwire") and info.get("key") == key_used:
                return True, name
        return False, None

    def list_tripwires(self):
        keys = self._load_keys()
        tripwires = {}
        for name, info in keys.items():
            if info.get("tripwire"):
                masked_key = info["key"][:8] + "..." + info["key"][-4:]
                tripwires[name] = {
                    "host": info.get("host"),
                    "port": info.get("port"),
                    "planted_at": info.get("planted_at"),
                    "key_masked": masked_key,
                }
        return tripwires

    def remove(self, node_name):
        keys = self._load_keys()
        if node_name not in keys:
            return f"Node '{node_name}' not found"
        if not keys[node_name].get("tripwire"):
            return f"Node '{node_name}' is not a tripwire"
        del keys[node_name]
        self._save_keys(keys)

        entry = {
            "event": "removed",
            "node_name": node_name,
            "timestamp": datetime.now().isoformat(),
        }
        self._log_tripwire_event(entry)
        return f"Tripwire '{node_name}' removed"

    def get_triggered(self):
        if self.tripwire_log.exists():
            try:
                entries = json.loads(self.tripwire_log.read_text())
                return [e for e in entries if e.get("event") == "triggered"]
            except Exception:
                return []
        return []

    def _log_tripwire_event(self, entry):
        entries = []
        if self.tripwire_log.exists():
            try:
                entries = json.loads(self.tripwire_log.read_text())
            except Exception:
                entries = []
        entries.append(entry)
        entries = entries[-200:]
        self.tripwire_log.write_text(json.dumps(entries, indent=2))


class ShamirPanicManager:
    def __init__(self, base_dir=None):
        self.base_dir = Path(base_dir or Path(__file__).parent.parent)
        self.shares_file = self.base_dir / ".panic_shares.json"
        self.panic_manager = PanicManager(base_dir)

    def setup_shares(self, n_shares=3, threshold=2, labels=None):
        panic_key = secrets.token_bytes(32)
        shares = ShamirSecretSharing.split(panic_key, n_shares, threshold)

        if labels is None:
            labels = [f"device-{i}" for i in range(1, n_shares + 1)]

        shares_data = []
        for (share_id, share_b64), label in zip(shares, labels):
            shares_data.append({
                "id": share_id,
                "share": share_b64,
                "label": label,
                "created_at": datetime.now().isoformat(),
            })

        key_hash = hashlib.sha256(panic_key).hexdigest()

        config = {
            "threshold": threshold,
            "n_shares": n_shares,
            "key_hash": key_hash,
            "shares": shares_data,
            "created_at": datetime.now().isoformat(),
        }
        self.shares_file.write_text(json.dumps(config, indent=2))
        try:
            if os.name != "nt":
                os.chmod(self.shares_file, 0o600)
        except Exception:
            pass

        return shares_data

    def execute_with_shares(self, share_ids):
        config = self._load_config()
        if not config:
            return None, "No shares configured. Run: cm panic setup"

        threshold = config["threshold"]
        key_hash_expected = config["key_hash"]

        if len(share_ids) < threshold:
            return None, f"Need {threshold} shares to execute panic (got {len(share_ids)})"

        share_map = {}
        for s in config["shares"]:
            share_map[s["id"]] = s["share"]

        provided = []
        for sid in share_ids:
            if sid not in share_map:
                return None, f"Share ID {sid} not found"
            provided.append((sid, share_map[sid]))

        reconstructed = ShamirSecretSharing.combine(provided)
        key_hash_actual = hashlib.sha256(reconstructed).hexdigest()

        if key_hash_actual != key_hash_expected:
            return None, "Invalid shares — reconstructed key does not match"

        actions = self.panic_manager.execute_panic()
        self._log_share_panic(share_ids)
        return actions, None

    def get_shares_info(self):
        config = self._load_config()
        if not config:
            return None
        info = {
            "threshold": config["threshold"],
            "n_shares": config["n_shares"],
            "created_at": config["created_at"],
            "shares": [],
        }
        for s in config["shares"]:
            info["shares"].append({
                "id": s["id"],
                "label": s["label"],
                "created_at": s["created_at"],
            })
        return info

    def _load_config(self):
        if self.shares_file.exists():
            try:
                return json.loads(self.shares_file.read_text())
            except Exception:
                return None
        return None

    def _log_share_panic(self, share_ids):
        log_file = self.base_dir / ".panic_log.json"
        entries = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text())
            except Exception:
                entries = []
        entry = {
            "timestamp": datetime.now().isoformat(),
            "method": "shamir_2of3",
            "share_ids_used": share_ids,
            "actions": ["Panic executed via Shamir Secret Sharing"],
        }
        entries.append(entry)
        entries = entries[-100:]
        log_file.write_text(json.dumps(entries, indent=2))
