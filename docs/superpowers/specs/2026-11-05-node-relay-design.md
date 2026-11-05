# CloudMesh 4.3.0 — Node Relay (Phase 1)

**Status:** Draft for approval
**Date:** 2026-11-05
**Target release:** CloudMesh 4.3.0
**Branch:** `feature/node-relay`
**Follows:** 4.2.6 (stability release)

---

## 1. Why

CloudMesh can only reach a node that accepts an inbound TCP connection on
port 9999. A node behind NAT, a cloud security group, or a host firewall is
invisible until the operator opens a port and exposes the agent to the
internet. That is the largest practical gap between "I installed the agent"
and "the node is part of my pool."

The next update closes that gap with a relay: a reachable meeting point that
both the node and the controller dial **outbound**. The node never opens an
inbound port, the controller never needs the node's address, and the existing
request/response protocol runs end-to-end inside TLS.

This is Phase 1 of the sequence the user approved: relay first, then node
membership and peer trust (Phase 2, outlined in section 14). Phase 1 does not
let one node command another. It makes every node reachable from the
controller, which is the prerequisite for any peer layer.

## 2. What exists today

Facts verified in the 4.2.6 tree:

- `cloudmesh/node/cloudmesh_node.py` is a standalone stdlib agent (psutil
  optional). It listens on TCP 9999, accepts one connection at a time in
  `serve()`, and handles each in a thread.
- The wire format is a 4-byte big-endian length followed by one JSON object.
  `NodeAgent._recv_msg` caps a request at 50 MB and `_send_msg` writes one
  response.
- The first request carries `auth`, the node's shared key. The agent compares
  it with `hmac.compare_digest`. TLS is optional (`--tls-cert/--tls-key`),
  SPA is optional, and both are off by default.
- The agent knows nothing about other nodes. There is no outbound connection,
  no peer list, and no registration with anything.
- The agent's `upload` action is confined by `_safe_path` / `_safe_open_write`
  to `~/.cloudmesh-node/data`. Paths outside that directory are rejected, and
  `test_security.py` asserts the confinement. The cert and config paths this
  design needs are outside it, so the agent's data channel cannot provision
  relay settings.
- The agent has no reload or restart action. `stop` kills the PID. Linux
  systemd units use `Restart=always`, but the FreeBSD/OpenBSD/NetBSD units in
  `node-install.sh` have no supervisor, and `taskkill /F` on Windows leaves
  nothing to restart the process.
- `cloudmesh/core/node_client.py` opens a new TCP connection per request and
  returns one response. `tls=True` uses `ssl.create_default_context` with an
  optional CA file. `NodeClient.from_config(info)` receives the stored record,
  not the operator's node name.
- Node records live in `NodeKeyring` (SQLite source of truth, JSON mirror),
  with the legacy shape `{name: {host, port, key, tls, ca_file}}`.
- `cloudmesh/node/node-install.sh` writes systemd/rc.d units whose
  `ExecStart` is `python3 cloudmesh_node.py start` with no arguments, so any
  new runtime setting must come from a config file, not from unit flags.
- `cm node add/test/info/exec/install/...` all assume direct reachability.
  `cm node test` and `cm node list` fail with "Connection refused" or a
  timeout when the node is behind NAT.
- Nothing in the tree generates an X.509 certificate today; there is no
  `cryptography`-based cert helper to reuse.

Consequence: "connect the servers to each other and to the user's device" is
not a patch to the agent. It is a new transport layer plus a rendezvous
service, and it needs an explicit bootstrap path that does not depend on the
node being reachable.

## 3. Goals

**G1 — Reach nodes behind NAT.** A node with no inbound port can be added,
tested, monitored, executed against, uploaded to, and used for async jobs
through the relay, using the same commands as a direct node.

**G2 — Outbound only.** The node opens outbound connections to the relay and
never listens on a public port in relay mode. Relay-only mode must be
available for operators who want the inbound listener disabled entirely.

**G3 — End-to-end confidentiality and integrity.** The relay must not be able
to read commands, output, file contents, or the node auth key. Inner TLS runs
between the controller and the node, through the relay, and the controller
pins the node certificate fingerprint. Relay mode without TLS is refused.

**G4 — No new lateral movement.** A node cannot ask the relay to reach
another node, and a compromised node cannot impersonate another node's relay
registration. Per-node relay tokens are enrolled by the controller.

**G5 — Zero regressions.** Direct mode is unchanged and remains the default.
The existing suite stays green. Every new behaviour is written test-first.

**G6 — Operable by one person.** The happy path is four commands:
`cm relay init` on the relay host, `cm relay add` on the controller,
`cm node relay enable` (over SSH, or `--local` on the node), then normal
`cm node ...` commands. A failed relay does not take the node down; it
reconnects with backoff and reports its state.

### Success criteria

- On a node with its inbound port blocked, `cm node test -n NAME` succeeds
  through the relay, and `cm node exec -n NAME "uptime"` returns output.
- `cm node monitor`, `cm node info`, file upload/download, and async jobs
  work through the relay.
- A packet capture of the relay's paired socket contains no plaintext
  command, output, or node auth key (asserted by an integration test).
- The relay process can be killed and restarted; the node reconnects without
  operator action, and direct mode keeps working.
- A node with no SSH and no inbound port can still join: `--local` on the
  node plus one `cm node relay import` on the controller is enough.
- Every existing test passes unchanged, and the 4.3.0 wheel installs and
  passes the command-surface smoke test.

## 4. Non-goals (4.3.0)

- **Node-to-node direct connections.** Phase 2. A node cannot connect to
  another node in this release.
- **Peer discovery, gossip, trust scores, distributed queue routing.** Phase 2.
- **Controller failover / a headless controller on a node.** Phase 3.
- **A hosted public relay service.** The operator runs the relay on a host
  they control.
- **NAT hole punching / UDP traversal.** The relay is the meeting point;
  no attempt is made to upgrade to a direct path.
- **Multiplexing many requests over one TCP connection.** Phase 1 uses a
  small pool of parked connections, one request per pair.
- **Windows relay host.** The relay server is stdlib and portable, but the
  first release is tested on Linux and BSD only. Windows nodes can use relay
  mode as clients.
- **Automatic relay key rotation inside `cm panic`.** Phase 1 documents the
  manual rotation; wiring it into panic is a follow-up.
- **Multi-controller node sharing.** Two controllers cannot both manage the
  same relay node in this release; the sidecar entry belongs to one
  controller's config directory. Phase 2's signed directory changes this.

## 5. Anti-goals

- No plaintext relay fallback, on either leg. If TLS or fingerprint pinning
  fails, the command fails loudly; it never downgrades.
- No relay that parses or logs inner protocol bytes. It pairs sockets and
  forwards bytes; that property is what keeps it from becoming a place where
  commands and keys accumulate.
- No new mandatory dependency in the agent. The relay client uses stdlib
  `ssl`, `socket`, `hmac`, `json`, and `threading`.
- No schema migration of `NodeKeyring`. Relay settings live in sidecar files,
  following the `drain.py` precedent.
- No provisioning over the agent's plaintext data channel. Config and private
  keys travel over SSH or are generated on the node.
- No silent failure. A node that cannot reach its relay says so in
  `cm node info`, `cm doctor`, and its log.
- No shared cluster-wide relay token. Each node gets its own token.

## 6. Constraints

- Python ≥ 3.11 on the controller; the agent keeps its existing floor.
- The agent remains a standalone single file plus an optional relay module;
  it must not import `cloudmesh.core`.
- The relay host may run only the agent, without the full CloudMesh package.
  The relay implementation must therefore be a standalone stdlib file that
  both `cm relay serve` and `cloudmesh_node.py relay` can run.
- The node installer's service units have no arguments; configuration comes
  from files under `~/.cloudmesh-node/`.
- Development and the suite run on Windows; Linux/BSD-specific service
  restart paths are unit-tested with a fake runner and verified on a real
  host only when one is available.
- TDD: failing test first, then the smallest change, then refactor.
- The relay must not require opening an inbound port on the node. The relay
  host itself needs one reachable TCP port; that is the operator's choice.

## 7. Fixed decisions (yours)

- Work in the approved order: relay first, then peer membership.
- The next update is the relay; do not start Phase 2 in this release.
- The user relies on the agent for technical choices; the calls below are
  therefore stated explicitly and remain vetoable.

## 8. Calls I am making (vetoable)

**C1 — Topology.** Controller and node both dial the relay. The relay pairs
one controller connection with one parked node connection and then forwards
raw bytes. It never initiates a connection to a node.

**C2 — Relay is a role, not a new service to host.** The relay server is a
standalone stdlib module, `cloudmesh/node/cloudmesh_relay.py`. It runs via
`cm relay serve` on a full install, or via `cloudmesh_node.py relay` on an
agent-only host. One implementation, two entry points.

**C3 — Both legs use TLS.** The outer leg (controller↔relay, node↔relay)
is TLS with a relay certificate generated by `cm relay init`; both sides pin
its SHA-256 fingerprint unless the operator configures a real CA. The inner
leg (controller↔node) is TLS with a node certificate; the controller pins
its fingerprint. The relay sees ciphertext only on the inner leg and can
never read commands, output, files, or the node auth key.

**C4 — Relay identity is a controller-generated ID.** Each relay enrollment
creates a random 128-bit `relay_id`. It is not the agent's `.node_id` UUID
and not the operator's `-n NAME`. The node config carries the ID; the
controller sidecar maps name → ID. Renaming a node locally does not change
its relay identity, and enrollment does not require reading anything from the
node first.

**C5 — Per-node tokens, one per node.** Each node receives a random 32-byte
token. The controller sends it to the relay once, over the admin channel
inside outer TLS; the relay stores it in a `0600` registry and verifies an
HMAC on every registration. The node never sends the raw token after
enrollment. This prevents one compromised node from registering as another
relay ID.

**C6 — One request per paired connection, with a parking pool.** The node
keeps `pool` parked connections (default 4) registered with the relay. A
request consumes one; the node opens a replacement. The relay queues a
controller connect for up to 5 seconds waiting for a parked connection.
The cap applies to **parked** connections only, so opening a replacement
while a paired request is still running cannot race the cap. This avoids
implementing stream multiplexing in Phase 1.

**C7 — Bootstrap is SSH or local, never the agent data channel.** `cm node
relay enable` provisions over SSH by default (reusing `ServerManager` and
SFTP), which is encrypted and works today. On a node with no SSH and no
inbound port, `cm node relay enable --local` runs on the node, generates the
key material locally, and prints one `cm node relay import` command for the
controller. The node's TLS private key is generated on the node in local
mode and crosses only SSH in SSH mode; it never crosses the relay or the
agent's data channel.

**C8 — Sidecar storage, no keyring migration.** Relay profiles live in
`.relays.json`; per-node relay settings and fingerprints live in
`.node_relay.json`. Both are `0600` where the OS supports it and are written
atomically. `NodeKeyring` is untouched; `NodeClient.from_config` gains an
optional node name so it can find the sidecar entry.

**C9 — DDoS limits follow the real client, not the relay IP.** In relay mode
the relay passes a stable `client_id` (generated per controller process) in
the `paired` message. The node rate-limits and bans per `client_id`, with a
higher default rate than direct mode (120 requests/minute, 8 concurrent) and
a global cap. Direct mode keeps the existing per-IP behavior unchanged. The
relay also applies per-IP limits to registration and connect attempts.

**C10 — Opt-in per node.** `cm node add` stays direct by default. Relay is
enabled with `cm node relay enable` or `cm node add --relay ...`. Existing
nodes and scripts are unaffected.

**C11 — Version 4.3.0.** New feature, no breaking change. Follow the 4.2.6
release checklist: version bump across every surface, changelog, README,
site, installers, SECURITY, LTS, test-count badge, tag, release.

## 9. Architecture

### 9.1 Topology

```
        controller (laptop)                     relay host (public IP)
        +------------------+  outer TLS         +----------------------+
        | cm node exec     |------------------->|  cloudmesh_relay.py  |
        | NodeClient       |                    |  pair(relay_id)      |
        | inner TLS client |<======= ciphertext =|  raw byte pump       |
        +------------------+                    +----------+-----------+
                                                           ^
                                                           | outer TLS
                                                +----------+-----------+
                                                | node agent (NAT)     |
                                                | inner TLS server     |
                                                | parked pool (4)      |
                                                +----------------------+
```

The relay never connects to the node. Both sides connect outbound, so the
node needs no inbound port and no public address. The relay needs one
reachable port (default 9997). The controller's inner TLS session terminates
at the node; the relay forwards ciphertext it cannot read.

### 9.2 Components

| Component | Path | Responsibility |
|---|---|---|
| Relay server | `cloudmesh/node/cloudmesh_relay.py` | Accept registrations and connects, authenticate, park, pair, pump bytes, admin API, status |
| Relay client (node) | `cloudmesh/node/cloudmesh_node.py` (`RelayClient`) | Keep a pool of parked connections, wrap a paired socket in TLS server mode, call `NodeAgent._handle`, reconnect with backoff |
| Relay transport (controller) | `cloudmesh/core/node_relay.py` | Sidecar storage, relay profile, enrollment, `RelayTransport` that pairs and wraps inner TLS client mode |
| Bootstrap | `cloudmesh/core/node_relay.py` + `cloudmesh/main.py` | SSH/local provisioning, cert generation, config upload, service restart |
| Node config | `~/.cloudmesh-node/.node_relay.json` | One object: relay ID, URL, token, fingerprints, cert/key paths, pool |
| Controller node config | `.node_relay.json` under the base dir | Name → relay ID, URL, relay fingerprint, node fingerprint |
| Relay profiles | `.relays.json` | Relay URL → admin key, relay fingerprint, optional CA file |
| CLI | `cloudmesh/main.py` | `cm relay init/add/serve/status/revoke`; `cm node relay enable/import/disable/status`; `cm node add --relay` |
| Doctor | `cloudmesh/main.py` | Relay profile, node config, both fingerprints, cert expiry, reachability |

### 9.3 Handshake

All handshake messages run **inside outer TLS** and use the existing 4-byte
big-endian length + JSON framing, capped at 64 KB. After `paired`, the relay
stops parsing and forwards raw bytes; the inner TLS handshake is just bytes
to it.

**Node registration**

```
node -> relay: {"type":"register","relay_id":"<32 hex>","ts":<unix>,
                "nonce":"<hex>","mac":"<hmac>"}
              mac = HMAC-SHA256(node_token,
                    "register|" + relay_id + "|" + ts + "|" + nonce)
relay -> node: {"type":"parked"}            # connection waits
relay -> node: {"type":"paired","client_id":"<32 hex>"}   # controller arrived
node:          wrap socket as inner TLS server, call NodeAgent._handle(..., client_id)
```

**Controller connect**

```
controller -> relay: {"type":"connect","relay_id":"<id>","client_id":"<32 hex>",
                      "ts":<unix>,"nonce":"<hex>","mac":"<hmac>"}
                    mac = HMAC-SHA256(relay_admin_key,
                          "connect|" + relay_id + "|" + client_id + "|" + ts + "|" + nonce)
relay -> controller: {"type":"paired"}
controller:          wrap socket as inner TLS client, verify pinned node
                     fingerprint, send the normal request
```

The controller generates `client_id` once per process and reuses it, so the
node's rate limiter and bans follow the controller, not the relay's address.

**Admin operations** (enroll, revoke, status, ping) use the same framing and
an HMAC over `"admin|" + action + "|" + relay_id + "|" + ts + "|" + nonce`
with the relay admin key. `enroll` additionally carries the node token and
pool size inside outer TLS. `revoke` deletes the token and closes that node's
parked connections; an already paired request is allowed to finish.

**Replay and clock rules.** Timestamps are accepted within ±30 seconds.
Nonces are remembered for 60 seconds per role and relay ID (bounded LRU,
10,000 entries). A repeated nonce or a stale timestamp is an auth failure.
All comparisons use `hmac.compare_digest`.

**Parked keepalive.** The relay sends `{"type":"ping"}` every 30 seconds to
a parked connection. The node answers `{"type":"pong"}`. A parked connection
that misses two pings is closed; the node replenishes the pool. This keeps
NAT mappings alive and detects half-open connections.

**Pairing.** The relay keeps a per-relay-ID FIFO of parked connections and a
condition variable for waiting controllers. A connect request waits up to
5 seconds for a parked connection. If none arrives, the relay returns
`{"type":"error","message":"node offline"}`. When paired, the relay sends
`paired` to both sides and starts two forwarding threads. On EOF or error,
both directions are shut down and both sockets closed. The node caps the
client ID at the documented format so a malformed value cannot become a
memory key.

### 9.4 TLS and fingerprint pinning

**Outer leg (relay certificate).**

- `cm relay init` generates an ECDSA P-256 self-signed certificate with
  `CN=<relay host>`, 10-year validity, plus an admin key. It writes the
  relay profile (`relay.json`) and prints the fingerprint and the
  `cm relay add` / node enable commands.
- If `cryptography` is unavailable on an agent-only relay host,
  `cm relay init --tls-cert/--tls-key` accepts operator-provided PEMs; the
  relay refuses to start without a certificate.
- The controller and the node create an `SSLContext` with
  `check_hostname=False`, `verify_mode=CERT_NONE`, connect, then compare the
  relay certificate's SHA-256 fingerprint with the pinned value before
  sending any handshake byte. If the profile or node config has a CA file,
  standard verification replaces pinning.
- A mismatch closes the connection and reports `"relay identity mismatch"`.

**Inner leg (node certificate).**

- Relay mode refuses to start on the node without a cert/key pair. The agent
  logs a clear error and does not fall back to plaintext.
- `cm node relay enable` uses `relay-cert.pem` / `relay-key.pem` under
  `~/.cloudmesh-node/` (or `--cert/--key`), generating an ECDSA P-256
  self-signed certificate with `CN=<relay_id>` and a 10-year validity if the
  node has none. In local mode the node generates it itself.
- The controller's `RelayTransport` creates an `SSLContext` with
  `check_hostname=False`, `verify_mode=CERT_NONE`, and
  `server_hostname=<relay_id>`, completes the handshake, then compares the
  peer certificate's SHA-256 fingerprint with the pinned value using
  `hmac.compare_digest`. It sends nothing before the comparison succeeds.
- A mismatch closes the connection and returns
  `"relay node identity mismatch"`. The controller retries up to two parked
  connections, then fails. Retrying is an availability measure, not a
  downgrade: every attempt still verifies the pin.
- Certificates are checked by `cm doctor` for expiry (warn inside 30 days,
  fail if expired).

### 9.5 Node relay client

- `RelayClient` starts only when `.node_relay.json` exists or
  `--relay-config` is supplied. It is a set of daemon threads inside the
  agent process.
- Each pool slot: connect to the relay over outer TLS (verify the pinned
  relay fingerprint), send `register`, wait for `parked`, answer pings, wait
  for `paired`, wrap the socket in inner TLS server mode, call
  `NodeAgent._handle(sock, ("relay", 0), client_id=...)`, then open a
  replacement slot.
- Reconnect uses exponential backoff from 1 s to 60 s with ±20% jitter.
  A relay outage logs once per state change, not once per retry. Registration
  failures caused by a not-yet-imported token are logged once and retried on
  the same backoff.
- `--relay-only` disables the inbound listener. Without it, the agent keeps
  the direct listener and adds the relay pool.
- `info` gains `relay`: `{enabled, url, connected_slots, pool_size,
  last_error, last_connected_at}`. `cm node info` renders it.
- Shutdown closes all parked sockets and stops the threads; it does not wait
  for a parked connection to time out.

### 9.6 Controller transport

`NodeClient` gains a `transport` choice:

- `direct` (default): today's behavior, unchanged.
- `relay`: read the node's controller sidecar entry, pair through the
  relay, wrap inner TLS, then run the existing `_send` payload logic on the
  wrapped socket.

`NodeClient.from_config(info, name=None)` uses relay when `name` is supplied
and the sidecar has an entry with a node fingerprint. Every call site passes
the name; `from_config` without a name stays direct for backward
compatibility. If the sidecar entry is incomplete, it returns a named error
instead of falling back to direct (a node behind NAT would otherwise produce
a misleading "connection refused").

The relay handshake and inner TLS wrap happen once per request, matching the
one-request-per-connection protocol. The response size cap and timeouts are
unchanged.

### 9.7 Storage

**Controller: `.relays.json`** (under `resolve_base_dir()`):

```json
{
  "relay.example.com:9997": {
    "admin_key": "<64 hex chars>",
    "relay_fingerprint": "<64 hex chars>",
    "ca_file": null
  }
}
```

**Controller: `.node_relay.json`** (under `resolve_base_dir()`):

```json
{
  "web-1": {
    "relay_id": "<32 hex chars>",
    "url": "relay.example.com:9997",
    "relay_fingerprint": "<64 hex chars>",
    "node_fingerprint": "<64 hex chars>"
  }
}
```

**Node: `~/.cloudmesh-node/.node_relay.json`** (one node identity per agent,
not keyed by name):

```json
{
  "relay_id": "<32 hex chars>",
  "url": "relay.example.com:9997",
  "node_token": "<64 hex chars>",
  "relay_fingerprint": "<64 hex chars>",
  "tls_cert": "relay-cert.pem",
  "tls_key": "relay-key.pem",
  "pool": 4
}
```

The node file is the only place the node token is stored. The controller
never needs it, and the relay receives it once at enrollment. Certificate
paths are relative to the agent directory unless absolute.

**Relay: `relay.json`** (relay host):

```json
{
  "bind": "0.0.0.0",
  "port": 9997,
  "admin_key": "<64 hex chars>",
  "tls_cert": "relay-cert.pem",
  "tls_key": "relay-key.pem",
  "tokens_file": "tokens.json"
}
```

**Relay: `tokens.json`** (relay host, `0600`):

```json
{
  "<relay_id>": {"token": "<64 hex chars>", "pool": 4, "created_at": "..."}
}
```

All files are written with the existing atomic private-JSON helper, `0600`
on POSIX. A relay file leak yields node tokens, which grant registration
(availability) but not command execution: an impostor cannot pass the inner
TLS handshake, and the controller refuses on fingerprint mismatch.

`cm node remove` and `cm node relay disable` remove the sidecar entry and
revoke the token at the relay (best effort; a relay that is down leaves a
stale token that `cm relay revoke` can remove later).

### 9.8 Bootstrap

**SSH mode (default).**

`cm node relay enable -n NAME --relay HOST:PORT --ssh-user USER
[--ssh-key PATH] [--ssh-port 22] [--pool 4] [--cert PATH --key PATH]`

1. Generate `relay_id`, `node_token`, and (unless supplied) the node's
   cert/key on the controller.
2. Open SSH through the existing `ServerManager`/`ssh_util` path and upload
   `relay-cert.pem`, `relay-key.pem`, and `.node_relay.json` into
   `~/.cloudmesh-node/` with `0600`. This uses SFTP, not the agent's
   `data/`-confined upload action.
3. Enroll `{relay_id, token, pool}` at the relay over outer TLS with the
   admin HMAC.
4. Write the controller sidecar with the node fingerprint and relay
   fingerprint.
5. Restart the agent (`systemctl restart cloudmesh-node`, the BSD rc.d
   stop/start, or `service`), or print the exact manual command when no unit
   is detected. On Windows, print the command; do not attempt a kill.
6. Verify by pairing through the relay and calling `ping`. On failure,
   report the specific error; leave the uploaded config in place so a retry
   does not need SSH again.

If any step before the restart fails, remove the controller sidecar entry and
revoke the token, so the operator can retry cleanly.

**Local mode (no SSH, no inbound port).**

`cm node relay enable --local --relay HOST:PORT [--pool 4]` runs on the
node. It generates the relay ID, token, and certificate locally, writes the
node config, and prints exactly one controller command:

```
cm node relay import -n NAME --relay HOST:PORT --relay-id ID --token TOKEN \
  --node-fingerprint FP --relay-fingerprint FP
```

`cm node relay import` writes the controller sidecar and enrolls the token
at the relay. The agent's registration fails with `unauthorized` until the
import runs, then succeeds on its next backoff attempt. Local mode never
sends the private key anywhere.

**Disable.**

`cm node relay disable -n NAME` revokes the token at the relay, removes the
controller sidecar, and (with the same SSH flags) removes the node config and
restarts the agent. `--local` on the node removes the node config and prints
the controller-side revoke command.

### 9.9 CLI surface

```
cm relay init [--url HOST:PORT] [--config PATH] [--system]
              [--tls-cert PATH --tls-key PATH]
    Generate the admin key and relay TLS certificate, write relay.json, and
    print the `cm relay add` and node enable commands.

cm relay add --url HOST:PORT --key KEY [--fingerprint FP] [--ca-file PATH]
    Store a relay profile on the controller.

cm relay serve [--bind HOST] [--port 9997] [--config PATH]
    Run the relay in the foreground. Also available as
    `cloudmesh_node.py relay ...` on an agent-only host.

cm relay status [--relay HOST:PORT]
    Ask the relay for uptime, enrolled nodes, parked counts, paired counts,
    auth failures, and version.

cm relay revoke -n NAME [--relay HOST:PORT]
    Remove the token and close that node's parked connections.

cm node relay enable -n NAME --relay HOST:PORT
    (--ssh-user USER [--ssh-key PATH] [--ssh-port 22] | --local)
    [--pool 4] [--cert PATH --key PATH]
    Provision relay mode on the node (see 9.8).

cm node relay import -n NAME --relay HOST:PORT --relay-id ID --token TOKEN
    --node-fingerprint FP --relay-fingerprint FP
    Controller-side half of local mode.

cm node relay disable -n NAME [--ssh-user ... | --local]
    Remove the node config, revoke the token, restart the agent.

cm node relay status -n NAME
    Show relay URL, connection state, pool slots, last error, fingerprints.

cm node add -n NAME --relay HOST:PORT --ssh-user ... | --local ...
    Add a relay-backed node in one step (implies `relay enable`). `-H` is not
    required in this form; the keyring stores the relay host and port for
    display compatibility. If enable fails, the keyring entry is removed.
```

`cm node list` gains a `Transport` column (`DIRECT` or `RELAY`) and keeps
the existing `Status` and `State` columns.

### 9.10 Failure behavior

| Failure | Behavior |
|---|---|
| Relay down at node start | Agent starts, direct listener works if enabled, relay client retries with backoff, `info.last_error` is set |
| Relay down while parked | Socket closes, slot reconnects, controller gets `"node offline"` |
| Controller cannot reach relay | Named error: `"relay unreachable: <reason>"`; no direct fallback |
| Relay certificate mismatch | Named error before any handshake byte; no registration or connect |
| Node offline / no parked slot | Relay waits 5 s, then `"node offline"` |
| Inner TLS handshake fails | Named error; no request is sent; no key leaves the controller |
| Node fingerprint mismatch | Named error; retry up to two parked connections; then fail |
| Duplicate node registration | Parked connections up to `pool`; more is rejected with `"too many registrations"`. Paired connections do not count against the cap |
| Stale/duplicate nonce | Auth failure, connection closed, logged with relay ID and IP |
| Relay restart | Nodes reconnect; controller commands during the gap fail with `"node offline"` |
| Node restart | Relay drops parked sockets, node re-registers |
| Token revoked | Node registration fails with `"unauthorized"`; node logs it; `cm node relay status` shows the error |
| Pool exhausted (more concurrent commands than slots) | Relay queues up to 5 s; if still exhausted, the command fails with `"relay pool exhausted"` |
| SSH bootstrap fails | Named error; controller sidecar and token are rolled back |
| No service unit detected | Config is uploaded; the exact restart command is printed; `cm node relay status` reports `not running` until it is run |
| Local mode before import | Node logs `unauthorized` once, retries with backoff; import makes the next attempt succeed |
| Many requests from one controller | Rate-limited per `client_id` (120/minute, 8 concurrent) without affecting other controllers |
| One controller fails auth repeatedly | That `client_id` is banned; other controllers keep working; the relay IP is not banned by the node |

### 9.11 Observability

- Relay log: one line per register, pair, revoke, auth failure, and
  disconnect. No inner bytes, no tokens, no keys.
- `cm relay status` reads counters from the running relay over the admin
  channel; it does not read the relay's files.
- `cm node info` and `cm node relay status` show the relay state from the
  agent's `info` response.
- `cm doctor` adds rows: `Relay profile`, `Node relay config`,
  `Relay certificate`, `Node certificate`, `Relay fingerprint`, `Relay
  reachable` (short timeout, warning only when the relay is configured but
  unreachable).

## 10. Security model

### 10.1 Assets

- Node auth key: grants full command execution on that node.
- Relay admin key: grants enroll/revoke/status and connect on the relay.
- Per-node relay token: grants registration as that relay ID (availability).
- Commands, output, uploaded/downloaded files.
- Node and relay TLS private keys.

### 10.2 Threat table

| Threat | Mitigation |
|---|---|
| Network attacker reads relay traffic | Outer TLS on both legs; inner TLS between controller and node |
| Network attacker modifies traffic | TLS integrity on both legs; fingerprints pinned on both legs |
| Relay operator reads commands | Inner TLS; the relay never has the node auth key or the node's TLS private key |
| Relay file leak | Tokens grant registration only; no command execution; inner TLS still fails without the node key |
| Compromised node registers as another node | Per-node token HMAC; it does not have the other node's token |
| Compromised node floods the relay | Per-IP registration/connect limits, auth-failure bans, bounded replay cache, parked cap |
| Replay of a registration or connect | Timestamp ±30 s, 60 s nonce cache, HMAC |
| Malicious relay pairs the wrong socket | Inner TLS node fingerprint pin fails; the controller retries and then refuses |
| Relay admin key leak | Attacker can enroll/revoke/connect (availability), still cannot read inner TLS; rotate the key and re-enroll |
| Node token leak | Attacker can park as that node (availability/DoS); cannot pass inner TLS without the node's private key; revoke and rotate |
| Bootstrap channel sniffing | SSH (encrypted) or local generation; never the agent's plaintext data channel |
| Downgrade to plaintext | Both legs refuse to start without certificates; controller refuses without fingerprints |
| Lateral movement node → node | No node-to-node action exists in the relay protocol; a node can only register and wait |
| One controller exhausting the node | Per-`client_id` rate and concurrency limits plus a global cap |

### 10.3 What the relay can still do

The relay can deny service: drop connections, refuse to pair, or pair a
controller with the wrong node (which then fails the fingerprint check). It
cannot read or alter the inner stream without breaking TLS. This is the
same trust level as "the network between controller and node", which is
acceptable for a self-hosted relay and is stated in SECURITY.md. The relay
necessarily holds node tokens because it must verify registration HMACs;
that is documented as availability-only exposure.

## 11. Compatibility and migration

- Direct mode is unchanged; no existing node record or command changes
  meaning.
- `cm node add` without `--relay` is byte-for-byte the old behavior.
- `NodeKeyring` schema is untouched. Relay settings are sidecars; a missing
  sidecar means "direct".
- `NodeClient.from_config` keeps its old behavior when called without a
  node name, so third-party callers keep working.
- The node agent can run without the relay module; `relay` mode prints a
  clear "relay module not installed" error.
- The installer copies `cloudmesh_relay.py` alongside `cloudmesh_node.py`
  and creates `~/.cloudmesh-node/relay/` for the relay config and token
  registry on relay hosts.
- `cm panic` rotates node auth keys as before. Relay tokens are independent;
  rotating a node key does not invalidate its relay registration. A future
  release will wire relay token rotation into panic; this is documented as a
  Phase 1 limitation.
- No change to the REST API, queue semantics, or existing storage.

## 12. Testing strategy

All new behavior is test-first. The suite must run on Windows without a
Linux/BSD host.

**Unit tests**

- Handshake MAC computation for register/connect/admin; timestamp skew;
  nonce replay; malformed JSON; oversized frame; malformed `client_id`.
- Enrollment/revocation registry (atomic writes, `0600`, duplicate relay ID,
  corrupt file recovery with a named error).
- Relay profile and node sidecar parsing, missing fields, corrupt files.
- Fingerprint computation and constant-time comparison for both legs.
- Relay client backoff and pool accounting with fake sockets.
- Per-`client_id` rate limiting and ban isolation.
- Service restart command selection with a fake runner (systemd, rc.d,
  service, none).
- CLI argument wiring for every new command, including mutually exclusive
  `--ssh-user` and `--local`.

**Integration tests (real sockets on localhost)**

- Start the relay on an ephemeral port; start a fake node with a generated
  self-signed cert; connect a `NodeClient` in relay mode; run `ping`,
  `execute`, `info`, upload/download, and a job.
- Assert the relay's captured bytes do not contain the command, the output,
  or the node auth key.
- Assert the relay's captured bytes do not contain the node token after the
  enrollment exchange complete.
- Pair two controllers concurrently with a pool of two slots; both succeed.
- Three controllers, two slots: the third waits and gets `"node offline"`
  after the timeout; the first two complete.
- A paired request plus a replacement registration does not trip the parked
  cap.
- Relay restart: kill and restart; the node re-registers; the next command
  succeeds.
- Relay certificate mismatch: the node and the controller both refuse.
- Node fingerprint mismatch: present a different cert; the controller
  refuses and the node key never appears on the wire.
- Revoked token: the node cannot re-register.
- Duplicate registration beyond the parked cap is rejected.
- One `client_id` exceeding 120 requests/minute is rejected without
  affecting a second controller.

**Bootstrap tests**

- SSH mode against a fake SSH runner: files uploaded with `0600`, sidecar
  written, enrollment sent, restart command chosen.
- SSH failure before restart: sidecar and relay token are rolled back.
- Local mode: config written, import line printed, controller import
  enrolls, and the fake node's next registration succeeds.
- Full disk while writing each sidecar: the old file survives.

**Fault injection**

- Corrupt `.node_relay.json` / `.relays.json` / `relay.json`: named error, no
  silent fallback to direct, no rewrite of the damaged file.
- Relay dies mid-pump: both sides get EOF, no hang.
- Node dies mid-request: controller returns a named error within the timeout.
- Clock skew beyond 30 s: auth failure with a clear message.
- TLS private key missing on the node: agent refuses relay mode, direct mode
  still works.
- Relay TLS key missing: `cm relay serve` refuses to start.

**Regression**

- The entire existing suite, including `cm test --suite --coverage` at the
  45% floor.
- The wheel smoke test and the installer tests.

## 13. Rollout

- Version 4.3.0 (minor). No breaking changes.
- Docs: README section "Nodes behind NAT (relay)" with the topology diagram
  and the four-command workflow; `docs/UPGRADING.md` note; `SECURITY.md`
  threat model; `docs/LTS.md` current release.
- Changelog entry with the security properties and the Phase 1 limitations.
- Release assets follow the 4.2.6 process: wheel, sdist, three installers,
  SBOM, `SHA256SUMS`; the installers include the relay module.
- The release workflow must not publish a tag whose CI is red. This is the
  process improvement identified after 4.2.6: the release job should depend
  on the CI result for the tagged commit, or run the suite itself.

## 14. Phase 2 outline (not in 4.3.0)

Phase 2 builds on the relay identity:

- Each node gets an Ed25519 keypair; the controller signs short-lived
  capability tokens (`node A may submit job type X to node B until T`).
- The controller publishes a signed peer directory to the relay; nodes can
  fetch it and connect directly or through the relay.
- Node-to-node job forwarding uses the token, not a shared cluster key.
- Trust scoring compares controller observations with node self-reports.
- No node can execute on another node without a token signed by the
  controller.

Phase 2 is deliberately not designed in detail until Phase 1 ships and is
used on a real NAT'd node. Its shape depends on what Phase 1 teaches.

## 15. Open questions (yours)

1. **Where will the relay run?** Recommendation: one small public VPS, or a
   node that already has a public IP. The user's laptop only works if it is
   reachable (public IP or port forward), because the node must dial it.
   This is an operational choice; it does not change the build.
2. **Is 4.3.0 the right version?** Recommendation: yes; new feature, no
   breaking change.
3. **Ship a service unit for the relay?** Recommendation: yes, a generator
   for systemd and rc.d plus a clear "run it yourself" message, because a
   relay that dies on logout is not operable.

The six questions raised by the independent review are answered in sections
8, 9.3–9.8, and 10; none of them remains blocking.

## 16. Acceptance checklist

- [ ] Relay starts on Linux/BSD with a certificate and logs its listen address.
- [ ] Node registers outbound, parks four connections, and survives relay
      restarts.
- [ ] Controller runs `test`, `info`, `exec`, `monitor`, upload/download,
      and async jobs through the relay.
- [ ] Relay capture contains no plaintext command/output/node key, and no node
      token after enrollment.
- [ ] Relay and node certificate mismatches, and revoked tokens, fail closed
      with named errors.
- [ ] SSH and local bootstrap both work; failed SSH bootstrap rolls back.
- [ ] Direct mode behavior is unchanged; full suite green; coverage ≥ 45%.
- [ ] `cm doctor` reports relay profile/config/certs/fingerprints/reachability.
- [ ] README, SECURITY, LTS, UPGRADING, CHANGELOG, version surfaces updated.
- [ ] 4.3.0 wheel, sdist, installers, SBOM, SHA256SUMS released and verified.

## 17. What is left to the builder

- Exact class and function boundaries inside `cloudmesh_relay.py`,
  `node_relay.py`, and `RelayClient`.
- The internal thread/condition layout of the relay's parking registry,
  provided the pairing and replay rules above hold.
- The precise wording of log lines and CLI help.
- The TLS key algorithm (ECDSA P-256 is the default; RSA 2048 is acceptable
  if a platform's `ssl` build rejects ECDSA).
- The certificate-generation fallback order (controller `cryptography`, then
  `openssl`, then operator-provided PEMs).
- The service-unit generator's exact filenames and restart commands, provided
  they cover systemd, rc.d, and the no-service-manager fallback with a clear
  message.
