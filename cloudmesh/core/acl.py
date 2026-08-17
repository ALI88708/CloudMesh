import json, os, hashlib, secrets

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

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
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    acl["users"][username] = {
        "password_hash": pwd_hash,
        "salt": salt,
        "role": role,
        "enabled": True,
        "created": __import__("time").strftime("%Y-%m-%d %H:%M:%S")
    }
    _save_acl(acl)
    return f"User '{username}' created with role '{role}'"

def remove_user(username):
    acl = _load_acl()
    if username not in acl["users"]:
        return f"User '{username}' not found"
    del acl["users"][username]
    _save_acl(acl)
    return f"User '{username}' removed"

def authenticate(username, password):
    acl = _load_acl()
    user = acl.get("users", {}).get(username)
    if not user:
        return False
    if not user.get("enabled", True):
        return False
    pwd_hash = hashlib.sha256((user["salt"] + password).encode()).hexdigest()
    return pwd_hash == user.get("password_hash", "")

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
    return f"Role updated to '{role}'"

def enable_user(username):
    acl = _load_acl()
    if username not in acl["users"]:
        return f"User '{username}' not found"
    acl["users"][username]["enabled"] = True
    _save_acl(acl)
    return f"User '{username}' enabled"

def disable_user(username):
    acl = _load_acl()
    if username not in acl["users"]:
        return f"User '{username}' not found"
    acl["users"][username]["enabled"] = False
    _save_acl(acl)
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
