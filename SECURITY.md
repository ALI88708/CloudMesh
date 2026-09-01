# CloudMesh Security Policy

### Made By MRSX PRO

---

## Disclaimer

**CloudMesh is community software. It has NOT been professionally audited or penetration-tested.** The security features described below are implemented with security best practices in mind, but they are NOT guarantees. Use CloudMesh at your own risk. For production environments handling sensitive data, consult a professional security auditor.

This document describes what security measures exist in the codebase — not what has been independently verified.

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.1.x   | Yes |
| 2.0.x   | Yes |
| < 2.0   | No |

Always run the latest version for the most recent security patches:

```bash
cm update
```

---

## Reporting a Vulnerability

If you discover a security vulnerability in CloudMesh, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Use GitHub's private vulnerability reporting or contact the maintainer directly
3. Include: description, steps to reproduce, potential impact, suggested fix
4. You will receive a response within 48 hours

**Do not** exploit vulnerabilities on systems you do not own.

---

## Security Architecture Overview

CloudMesh uses a **zero-trust model** by default. Every connection is authenticated, every config is encrypted, and every command is logged.

```
+-------------------+     HMAC Auth      +------------------+
|    Controller     | <-----------------> |     Node Agent   |
|  (Your Laptop)    |     TLS (opt.)     |  (Cloud Server)  |
|                   |                     |                  |
|  - Encrypted cfg  |                     |  - SPA (opt.)    |
|  - Key rotation   |                     |  - DDoS guard    |
|  - Hash chain log |                     |  - iptables      |
+-------------------+                     +------------------+
```

---

## What Security Features Exist

### 1. Configuration Encryption (Fernet)

All server configs, node keys, and sensitive data are encrypted at rest using Fernet symmetric encryption.

**How it works:**
- A 256-bit key is auto-generated and stored in `.secret.key`
- Config is serialized to JSON, then encrypted with Fernet
- Decryption only happens in memory
- File permissions set to 600 (owner-only) on Linux

**File:** `cloudmesh/core/security.py` — `SecurityManager` class

```python
# Encryption flow:
plaintext = json.dumps(config).encode()
encrypted = fernet.encrypt(plaintext)   # AES-128-CBC + HMAC-SHA256
config_path.write_bytes(encrypted)
```

**Key file:** `.secret.key`
**Config file:** `config.json` (encrypted)
**Backups:** Automatic backups in `backups/` before every save

**Limitation:** If someone gets access to your `.secret.key` file, they can decrypt everything. Keep it safe.

---

### 2. Node Authentication (HMAC)

Every node has a unique 64-character hex auth key. All TCP communication is authenticated.

**How it works:**
- Controller sends: `{"action": "ping", "auth": "KEY"}`
- Node compares using: `hmac.compare_digest(received_key, stored_key)`
- Timing-safe comparison prevents timing attacks
- Wrong key → connection rejected immediately

**File:** `cloudmesh/node/cloudmesh_node.py` — `_handle()` method

**Key storage:**
- Controller: `.node_keys.json`
- Node: `.node_key`

**Key rotation:**
```bash
cm panic              # Rotate all keys (local + remote)
cm panic rotate       # Rotate remote node keys only
cm panic retry-pending  # Retry failed rotations
```

**Limitation:** If the auth key file is compromised, the attacker can impersonate the controller. Keys are stored in plaintext on disk.

---

### 3. SSH Host Key Verification

CloudMesh uses `RejectPolicy` by default — unknown hosts are rejected, not silently accepted.

**How it works:**
- SSH connections use `StrictHostKeyChecking=yes` (default)
- If host key is not in `~/.ssh/known_hosts`, connection is **REJECTED**
- You must manually add the host: `ssh-keyscan -H HOST >> ~/.ssh/known_hosts`
- If you disable strict checking, a MITM warning is emitted

**File:** `cloudmesh/core/ssh_util.py`

```python
# Default (secure):
ssh_cmd = ["ssh", "-o", "StrictHostKeyChecking=yes", ...]

# If disabled:
warn_host_key_disabled(host)
# WARNING: StrictHostKeyChecking disabled for 192.168.1.100.
# This connection is vulnerable to MITM attacks.
```

---

### 4. DDoS Protection (REST API)

The built-in REST API has multi-layer DDoS protection.

**File:** `cloudmesh/core/ddos.py`

| Layer | Protection | Config |
|-------|-----------|--------|
| Rate Limiting | 30 requests/min per IP | Sliding window |
| Connection Limits | 5 per IP, 100 total | Per-IP + global |
| IP Auto-Ban | 5 failures = 5 min ban | Persistent (survives restart) |
| Packet Validation | Max 1MB, valid JSON, has `action` field | Stateless |
| Slowloris Guard | 10s header timeout, 50MB max | Per-connection |

**Ban list:** Stored in `data/banned_ips.json`

```python
# Example DDoS protection setup:
DDoSProtection(
    rate_max=30,         # requests per window
    rate_window=60,      # window in seconds
    conn_per_ip=5,       # max connections per IP
    conn_total=100,      # max total connections
    ban_threshold=5,     # failures before ban
    ban_duration=300,    # ban duration in seconds
    read_timeout=10,     # slowloris timeout
)
```

**Limitation:** This protects against basic DDoS. It does NOT protect against sophisticated volumetric attacks or application-layer attacks that mimic normal traffic.

---

### 5. Ghost Ports (SPA — Single Packet Authorization)

Makes TCP ports invisible to port scanners. Only signed UDP knocks can open the port.

**File:** `cloudmesh/node/cloudmesh_node.py` — `SpacListener` class

**How it works:**
1. Node listens on UDP port (default 9998) silently
2. Controller sends a signed HMAC packet (timestamp + nonce + signature)
3. Node validates HMAC with shared auth key
4. If valid, node adds iptables ACCEPT rule: `-s <source_ip>` (source IP binding)
5. TCP port opens for N seconds (default 5)
6. After N seconds, iptables ACCEPT rule is removed
7. TCP port closes

**Security properties:**
- **Source IP binding**: Only the knocker's IP can connect (not anyone on the internet)
- **Fail-closed**: If iptables DROP fails at startup, node refuses to start
- **HMAC signed**: Knock cannot be forged without the auth key
- **Nonce replay protection**: Each nonce is used only once
- **Timestamp validation**: Stale packets (>30s) are rejected

**Starting with SPA:**
```bash
cm node start --spa
cm node start --spa --spa-port 9998    # Custom UDP port
cm node start --spa --spa-window 10    # TCP stays open 10s
```

**Limitation:** SPA requires root/elevated privileges for iptables. Does not work on Windows. UDP packets can theoretically be sniffed on the same network segment.

---

### 6. Tripwire Keys

Decoy keys that trigger alerts when used. Zero false positives.

**File:** `cloudmesh/core/advanced.py` — Tripwire features

**How it works:**
- Plant a fake key on a honeypot server
- If anyone authenticates with that key, you get an alert
- The key is a valid-looking auth key but serves only as a trap

```bash
cm tripwire plant --node honeypot --host 10.0.0.99
cm tripwire check    # Check if any tripwire was triggered
```

**Limitation:** Only detects unauthorized access if the attacker uses the tripwire key specifically. Does not protect against other attack vectors.

---

### 7. Emergency Panic Button

Rotates ALL encryption keys and node auth keys instantly.

**File:** `cloudmesh/core/panic.py` — `PanicManager` class

**What gets rotated:**
- `.secret.key` — Fernet encryption key (backup: `.secret.key.bak`)
- `.node_keys.json` — All node auth keys (backup: `.node_keys.json.bak`)
- Remote nodes — Each node's auth key via `rotate_key` action

**What gets logged:**
- Every panic event is recorded in `.panic_log.json` with timestamp and actions taken

**Offline nodes:**
- Rotation saved to `.panic_pending.json`
- Retry with `cm panic retry-pending`

```bash
cm panic --dry-run    # Preview without changes
cm panic              # Execute immediately
cm panic rotate       # Rotate remote nodes only
cm panic retry-pending  # Retry failed rotations
```

**Limitation:** Panic does NOT wipe data. It only rotates keys. If an attacker already has a copy of the data, key rotation does not help. Old backups with old keys remain readable.

---

### 8. Shamir Panic (2-of-3)

Splits the panic key into 3 shares using Shamir's Secret Sharing. Requires 2 of 3 shares to execute.

**File:** `cloudmesh/core/shamir.py`

**How it works:**
- Uses Shamir's Secret Sharing over GF(p) (Galois Field with prime modulus)
- Splits key into 3 shares, threshold is 2
- Any 2 shares can reconstruct the key
- A single compromised device cannot trigger panic alone

```bash
cm panic setup                # Generate 3 shares
cm panic shares               # View share status
cm panic execute --share 1 --share 2  # Execute with 2-of-3
```

**Important:** Shares are shown ONCE. Write them down and store each on a separate device.

**Limitation:** Shares are displayed in plaintext on screen. If someone is watching or recording your screen, the shares are compromised.

---

### 9. Remote Panic Rotation

Panic rotation works on remote nodes too, not just locally.

**File:** `cloudmesh/core/panic.py` — `execute_panic()` method

**Flow:**
1. Controller generates new auth key for node
2. Sends `rotate_key` action to node via `NodeClient.rotate_key(new_key)`
3. Node updates `.node_key` and `self.auth_key`
4. Old key immediately stops working
5. If node is offline, rotation is saved to `.panic_pending.json`

**Limitation:** If the network between controller and node is compromised, the new key could be intercepted during transmission (unless TLS is enabled).

---

### 10. Immutable Command Ledger (Tamper Detection)

Every command is logged with a SHA-256 hash chain. Any tampering breaks the chain.

**File:** `cloudmesh/core/cmdlog.py`

**How it works:**
```
Entry 1: prev=000...000, hash=SHA256(000...000 + time + cmd)
Entry 2: prev=hash1,     hash=SHA256(hash1 + time + cmd)
Entry 3: prev=hash2,     hash=SHA256(hash2 + time + cmd)
...
```

If anyone modifies entry #2, entry #3's `prev_hash` won't match, and verification fails.

```bash
cm cmdlog --verify
# Chain intact — all 42 entries verified.
# Chain BROKEN at entry #17 — possible tampering detected.
```

**Log file:** `command_log.json` (max 500 entries, auto-pruned)

**Limitation:** The log is stored locally on the controller. If the attacker has access to the controller machine, they can delete the log entirely. This detects tampering, not deletion.

---

### 11. Path Traversal Protection

File operations on nodes prevent directory traversal attacks.

**File:** `cloudmesh/core/sync.py`, `cloudmesh/core/transfer.py`

```python
# All user input is sanitized:
safe_path = shlex.quote(user_input)
# Prevents: ../../../etc/passwd
# Prevents: /etc/passwd; rm -rf /
```

**Limitation:** Only applies to file operations. Does not protect against command injection in other contexts.

---

### 12. Dangerous Command Blocklist (API)

The REST API blocks dangerous commands from being executed:

```python
BLOCKED = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", "chmod 777", "> /dev/sda"]
```

**File:** `cloudmesh/core/advanced.py` — `CloudMeshAPI` class

**Limitation:** This is a simple string-matching blocklist. It can be bypassed with variations (e.g., `rm -rf /` with extra spaces, or using variables). It is NOT a sandbox.

---

### 13. Database Password Safety

Database passwords are never stored in config files. They use temporary files:

**File:** `cloudmesh/core/database.py`

```python
# MySQL: writes temp config, executes query, deletes config
my_cnf = f"[client]\nuser={user}\npassword={password}\n..."
remote_conf = "/tmp/.cm_my.conf"
create = f"printf '%s' '{my_cnf}' > {remote_conf} && chmod 600 {remote_conf}"
run = f"mysql --defaults-extra-file={remote_conf} -e \"{sql}\""
cleanup = f"rm -f {remote_conf}"
# All three combined in one SSH command
```

**Limitation:** Password is visible in the SSH command string. If someone has root access on the remote server, they could see it in process listings (`ps aux`).

---

### 14. TLS Support (Optional)

Node connections can be encrypted with TLS:

```bash
cm node start --tls-cert cert.pem --tls-key key.pem
```

**Without TLS, a warning is shown:**
```
WARNING: TLS disabled — traffic is unencrypted. Use --tls-cert/--tls-key for production.
```

**Limitation:** TLS is optional, not enforced. Without it, node communication is in plaintext.

---

### 15. ACL (Role-Based Access Control)

Multi-user support with role-based permissions.

**File:** `cloudmesh/core/acl.py`

**Default roles:**
- `admin`: Full access (`*`)
- `viewer`: Read-only (`monitor`, `ping`, `list`, `info`)

**Password storage (v2.1.0):**
- **bcrypt** with 12 rounds by default (PBKDF2-SHA256 300k iterations as fallback if bcrypt is unavailable)
- Never stored in plaintext

```python
import bcrypt
salt = bcrypt.gensalt(rounds=12)
pwd_hash = bcrypt.hashpw(password.encode(), salt)
```

**Brute-force lockout (v2.1.0):**
- 5 consecutive failed attempts → account locked for **15 minutes**
- All auth events (success/failure/lockout) are written to `data/acl_audit.log`
- Enabling a user resets the attempt counter and lock

**Limitation:** ACL is local only. It does not apply to the node agent or SSH connections. ACL only controls who can use the CLI on the controller machine.

---

### 15b. Node Agent Command Blocklist (v2.1.0)

Remote execution and job submission through the node agent are filtered against a blocklist of destructive commands.

**File:** `cloudmesh/node/cloudmesh_node.py`

**Blocked patterns include:** `rm -rf /`, `mkfs`, `format c:`, `dd if=`, `shutdown`, `reboot`, `init 0/6`, fork bombs (`:(){`), `chmod -R 777 /`, and similar destructive operations.

Blocked attempts are logged and return a `Command blocked by security policy` error without executing.

**Upload mode validation:** only `w`, `a`, `wb`, `ab` are accepted as file modes; anything else is rejected.

---

### 16. Firewall Validation

Firewall rules are validated before being applied.

**File:** `cloudmesh/core/firewall.py`

```python
ALLOWED_RULES = {
    "allow", "deny", "reject",
    "allow 22/tcp", "allow 80/tcp", "allow 443/tcp",
    "allow from", "deny from",
    "limit", "delete",
    "enable", "disable", "status",
    "reset", "default deny incoming", "default allow outgoing",
}
```

Unknown or dangerous rules are rejected before reaching the server.

**Limitation:** The allowlist is not exhaustive. Some valid rules might be rejected. You can bypass it by running iptables directly via SSH.

---

### 17. Telegram Chat ID Validation

Webhook configurations validate input format before saving.

**File:** `cloudmesh/core/webhooks.py`

```python
# Chat ID must be numeric:
if not chat_id.isdigit():
    return "Invalid chat_id format"
```

---

### 18. Plugin Safety

Plugins execute arbitrary commands. CloudMesh warns about this:

**File:** `cloudmesh/core/plugins.py`

```
SECURITY WARNING: plugins.json executes arbitrary commands.
NEVER import plugins.json from untrusted sources or sync it
from remote/unknown origins. Only add plugins you personally wrote.
```

- Local plugins emit a runtime `UserWarning`
- Shell execution uses `shell=True` (full shell syntax, including pipes/redirects)
- 60-second timeout on all plugin executions

**Limitation:** Plugins are NOT sandboxed. A malicious plugin can do anything the user running CloudMesh can do.

---

## What CloudMesh Does NOT Protect Against

Be aware of these limitations:

| Scenario | Why |
|----------|-----|
| Physical access to controller | If attacker has your laptop, they have your keys and config |
| Compromised SSH private key | If private key is stolen, server is accessible without CloudMesh |
| Zero-day in dependencies | paramiko, psutil, cryptography could have undiscovered vulnerabilities |
| Social engineering | If someone tricks you into sharing keys, security features are bypassed |
| Insider threat | A malicious admin with access to the controller can do anything |
| Deleted logs | The command ledger detects tampering, but not deletion |
| Encrypted data at rest | Old backups with old keys remain readable |
| Network-level attacks | Without TLS, node communication is in plaintext |
| Application-layer DDoS | DDoS protection is basic, not designed for sophisticated attacks |

---

## Security Best Practices

### For Controllers (Your Laptop)

1. **Keep `.secret.key` safe** — if lost, encrypted config is unrecoverable
2. **Use SSH keys, not passwords** — keys are more secure and convenient
3. **Enable SPA** — makes your node ports invisible to scanners
4. **Enable TLS** — encrypts node communication
5. **Run `cm doctor` regularly** — catches misconfigurations early
6. **Use `cm panic --dry-run` first** — preview before rotating keys
7. **Back up `.secret.key`** — encrypted config is useless without it

### For Nodes (Cloud Servers)

1. **Run as non-root when possible** — reduces blast radius
2. **Enable TLS** — encrypts node communication
3. **Enable SPA** — hides TCP port from scanners
4. **Keep node agent updated** — `cm node install` reinstalls latest
5. **Use strong auth keys** — 64-char hex (auto-generated)

### For API Usage

1. **Bind to localhost only** — `127.0.0.1` (default, never expose publicly)
2. **Use SSH tunnel for remote access** — not direct port exposure
3. **Never expose API to the internet**

```bash
# Safe: local only
cm api --port 8080

# Safe: via SSH tunnel
ssh -L 8080:127.0.0.1:8080 user@server
# Then access at http://localhost:8080

# DANGEROUS: never do this
cm api --port 8080 --bind 0.0.0.0  # Exposes to internet!
```

---

## File Permissions

On Linux, sensitive files are created with restricted permissions:

| File | Permission | Purpose |
|------|-----------|---------|
| `.secret.key` | 600 (owner-only) | Encryption key |
| `.node_key` | 600 (owner-only) | Node auth key |
| `config.json` | 600 (owner-only) | Encrypted config |
| `.node_keys.json` | 600 (owner-only) | Node key registry |
| `acl.json` | 600 (owner-only) | User credentials |

**Limitation:** File permissions are best-effort. They do not protect against root-level access or other users with elevated privileges.

---

## Cryptographic Details

| Algorithm | Usage | Notes |
|-----------|-------|-------|
| AES-128-CBC | Fernet config encryption | Standard, well-reviewed |
| HMAC-SHA256 | Node auth, SPA packet signing | Timing-safe comparison used |
| SHA-256 | Command ledger hash chain | Standard hashing |
| Shamir's Secret Sharing over GF(p) | Panic key splitting | Mathematical, not custom crypto |
| SHA-256 + salt | ACL password hashing | Not bcrypt/argon2 — weaker against brute force |

**Note:** ACL uses SHA-256 for password hashing, which is weaker than bcrypt or argon2 against offline brute-force attacks. If you need stronger password protection, consider using the API with strong keys instead of password-based ACL.

---

## Known Security Issues

| Issue | Status | Impact |
|-------|--------|--------|
| ACL uses SHA-256 instead of bcrypt | Known | Weaker offline brute-force resistance |
| Plugin execution is not sandboxed | Known | Malicious plugins can do anything |
| Command ledger can be deleted (not just tampered) | Known | Log deletion not detected |
| Database passwords visible in SSH command | Known | Process listing exposure on remote server |
| DDoS protection is basic | Known | Not designed for sophisticated attacks |

---

## Security Updates

Security patches are applied as version updates:

- **v2.0.0 patches**: SPA source IP binding, fail-closed SPA, remote panic rotation, SSH tunnel unification
- **v1.4.0**: Centralized SSH, TLS/SPA warnings, firewall validation, DB temp files

Check for updates:
```bash
cm update
cm doctor    # Run health checks
```

---

<div align="center">

**Created and Developed by MRSX PRO**

**GitHub:** [ALI88708](https://github.com/ALI88708)

**Repository:** [CloudMesh](https://github.com/ALI88708/CloudMesh)

All rights reserved. This project is maintained by **MRSX PRO**.

</div>
