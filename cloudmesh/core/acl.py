import json, os, secrets, time

_HAS_BCRYPT = False
try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:
    import hashlib

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_LOG_FILE = os.path.join(DATA_DIR, "acl_audit.log")


def _log_auth_event(event):
    os.makedirs(DATA_DIR, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(_LOG_FILE, "a") as f:
        f.write(f"[{ts}] {event}\n")


def _acl_file():
    return os.path.join(DATA_DIR, "acl.json")


def _load_acl():
    p = _acl_file()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"users": {}, "roles": {"admin": ["*"], "viewer": ["monitor", "ping", "list", "info"]}}


def _save_acl(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_acl_file(), "w") as f:
        json.dump(data, f, indent=2)


def _hash_password(password, salt=None):
    if _HAS_BCRYPT:
        if salt is None:
            salt = bcrypt.gensalt(rounds=12)
        elif isinstance(salt, str):
            salt = salt.encode()
        pwd_hash = bcrypt.hashpw(password.encode(), salt)
        return pwd_hash.decode(), salt.decode() if isinstance(salt, bytes) else salt
    else:
        if salt is None:
            salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 300000).hex()
        return pwd_hash, salt


def _verify_password(password, stored_hash, salt):
    if _HAS_BCRYPT:
        try:
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
        except Exception:
            return False
    else:
        pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 300000).hex()
        return pwd_hash == stored_hash


def list_users():
    acl = _load_acl()
    users = []
    for name, info in acl.get("users", {}).items():
        users.append({
            "username": name,
            "role": info.get("role", "viewer"),
            "enabled": info.get("enabled", True),
            "created": info.get("created", "")
        })
    return users


def add_user(username, password, role="viewer"):
    acl = _load_acl()
    if username in acl["users"]:
        return f"User '{username}' already exists"
    pwd_hash, salt = _hash_password(password)
    acl["users"][username] = {
        "password_hash": pwd_hash,
        "salt": salt,
        "role": role,
        "enabled": True,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "failed_attempts": 0,
        "locked_until": None,
    }
    _save_acl(acl)
    _log_auth_event(f"USER_CREATED: {username} role={role}")
    return f"User '{username}' created with role '{role}'"


def remove_user(username):
    acl = _load_acl()
    if username not in acl["users"]:
        return f"User '{username}' not found"
    del acl["users"][username]
    _save_acl(acl)
    _log_auth_event(f"USER_REMOVED: {username}")
    return f"User '{username}' removed"


def authenticate(username, password):
    acl = _load_acl()
    user = acl.get("users", {}).get(username)
    if not user:
        _log_auth_event(f"AUTH_FAIL: user '{username}' not found")
        return False
    if not user.get("enabled", True):
        _log_auth_event(f"AUTH_FAIL: user '{username}' disabled")
        return False
    locked_until = user.get("locked_until")
    if locked_until:
        if time.time() < locked_until:
            _log_auth_event(f"AUTH_FAIL: user '{username}' locked out")
            return False
        else:
            user["locked_until"] = None
            user["failed_attempts"] = 0
            _save_acl(acl)
    if _verify_password(password, user["password_hash"], user.get("salt", "")):
        user["failed_attempts"] = 0
        _save_acl(acl)
        _log_auth_event(f"AUTH_OK: user '{username}'")
        return True
    else:
        user["failed_attempts"] = user.get("failed_attempts", 0) + 1
        if user["failed_attempts"] >= 5:
            user["locked_until"] = time.time() + 900
            _log_auth_event(f"AUTH_LOCKED: user '{username}' locked for 15 minutes after 5 failed attempts")
        _save_acl(acl)
        _log_auth_event(f"AUTH_FAIL: user '{username}' wrong password (attempt {user['failed_attempts']}/5)")
        return False


def check_permission(username, command):
    acl = _load_acl()
    user = acl.get("users", {}).get(username)
    if not user:
        return False
    role = user.get("role", "viewer")
    perms = acl.get("roles", {}).get(role, [])
    if "*" in perms:
        return True
    for p in perms:
        if command.startswith(p):
            return True
    return False


def set_role(username, role):
    acl = _load_acl()
    if username not in acl["users"]:
        return f"User '{username}' not found"
    acl["users"][username]["role"] = role
    _save_acl(acl)
    _log_auth_event(f"ROLE_CHANGE: user '{username}' -> role '{role}'")
    return f"Role updated to '{role}'"


def enable_user(username):
    acl = _load_acl()
    if username not in acl["users"]:
        return f"User '{username}' not found"
    acl["users"][username]["enabled"] = True
    acl["users"][username]["failed_attempts"] = 0
    acl["users"][username]["locked_until"] = None
    _save_acl(acl)
    _log_auth_event(f"USER_ENABLED: {username}")
    return f"User '{username}' enabled"


def disable_user(username):
    acl = _load_acl()
    if username not in acl["users"]:
        return f"User '{username}' not found"
    acl["users"][username]["enabled"] = False
    _save_acl(acl)
    _log_auth_event(f"USER_DISABLED: {username}")
    return f"User '{username}' disabled"


def list_roles():
    acl = _load_acl()
    return acl.get("roles", {})


def add_role(role_name, permissions):
    acl = _load_acl()
    acl["roles"][role_name] = permissions
    _save_acl(acl)
    return f"Role '{role_name}' created"


def remove_role(role_name):
    acl = _load_acl()
    if role_name in acl.get("roles", {}):
        del acl["roles"][role_name]
        _save_acl(acl)
        return f"Role '{role_name}' removed"
    return f"Role '{role_name}' not found"
