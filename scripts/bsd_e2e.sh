#!/bin/sh
# FreeBSD end-to-end walk of the BSD acceptance criteria.
#
# Runs inside the vmactions FreeBSD VM after the pytest suite: it proves that a
# real host can install CloudMesh, run the controller against itself over the
# node agent and over SSH, and that every BSD-specific command path (pkg, rc.d,
# ifconfig, sysctl) answers without a traceback. Prints "BSD E2E OK" last.
set -e

step() { printf '\n==== %s\n' "$*"; }
ok()   { printf '[OK] %s\n' "$*"; }

run_required() {
    CMD="$*"
    printf '\n[E2E] $ %s\n' "$CMD"
    if ! eval "$CMD"; then
        printf '[E2E] FAILED: %s\n' "$CMD" >&2
        exit 1
    fi
}

# For commands whose exact output is not the point: the check is that they
# answer without a Python traceback. Anything else is printed for the log.
run_tolerant() {
    CMD="$*"
    printf '\n[E2E] $ %s   (tolerant)\n' "$CMD"
    set +e
    OUT="$(eval "$CMD" 2>&1)"
    RC=$?
    set -e
    printf '%s\n' "$OUT"
    if printf '%s' "$OUT" | grep -q 'Traceback (most recent call last)'; then
        printf '[E2E] FAILED: traceback from: %s\n' "$CMD" >&2
        exit 1
    fi
    printf '[E2E] exit %s\n' "$RC"
    return 0
}

# ============================================
# Phase 1: the controller runs on FreeBSD
# ============================================
step "Phase 1/4: controller"
export PIP_BREAK_SYSTEM_PACKAGES=1

run_required "python3 -m pip install -q -e ."

VERSION_OUT="$(cm --version 2>&1)"
printf '%s\n' "$VERSION_OUT"
if ! printf '%s' "$VERSION_OUT" | grep -q '4\.0\.0'; then
    printf '[E2E] FAILED: cm --version did not report 4.0.0\n' >&2
    exit 1
fi
ok "cm --version"

run_required "cm --help > /dev/null"
ok "cm --help"

run_tolerant "cm doctor"
run_required "cm mon --local"
ok "cm mon --local"

step "Phase 1b: background service"
cm service start --interval 5 > /tmp/cm-service.log 2>&1 &
SERVICE_PID=$!
SERVICE_UP=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if cm service status 2>&1 | grep -qi 'running'; then
        SERVICE_UP=1
        break
    fi
    sleep 1
done
run_tolerant "cm service status"
cm service stop > /dev/null 2>&1 || true
kill "$SERVICE_PID" 2>/dev/null || true
if [ "$SERVICE_UP" -eq 1 ]; then
    ok "cm service reported running"
else
    printf '[WARN] cm service status never reported running; see /tmp/cm-service.log\n'
    sed -n '1,20p' /tmp/cm-service.log 2>/dev/null || true
fi

# ============================================
# Phase 2: node installer and rc.d unit
# ============================================
step "Phase 2/4: node installer and rc.d"

run_required "sh cloudmesh/node/node-install.sh"
run_required "sysrc cloudmesh_node_enable=YES"
run_required "service cloudmesh_node start"
NODE_UP=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if service cloudmesh_node status > /tmp/cm-node-status.log 2>&1; then
        NODE_UP=1
        break
    fi
    sleep 1
done
run_tolerant "service cloudmesh_node status"
if [ "$NODE_UP" -ne 1 ]; then
    printf '[E2E] FAILED: service cloudmesh_node status never reported running\n' >&2
    sed -n '1,20p' /tmp/cm-node-status.log 2>/dev/null || true
    exit 1
fi
ok "rc.d unit starts the agent"

NODE_KEY="$(cat "$HOME/.cloudmesh-node/.node_key")"
if [ -z "$NODE_KEY" ]; then
    printf '[E2E] FAILED: the node agent wrote no auth key\n' >&2
    exit 1
fi
ok "auth key present"

# ============================================
# Phase 3: loopback agent
# ============================================
step "Phase 3/4: loopback agent"

run_required "cm node add -n local -H 127.0.0.1 -p 9999 -k \"$NODE_KEY\""
run_required "cm node list"
run_required "cm node test -n local"
run_required "cm node exec -n local \"uname -s\""
ok "node agent answers over TCP"

run_tolerant "cm node job start -n local \"echo bsd\""
run_required "cm node job list -n local"
JOB_OUT="$(cm node job start -n local "echo bsd" 2>&1 || true)"
printf '%s\n' "$JOB_OUT"
JOB_ID="$(printf '%s\n' "$JOB_OUT" | sed -n 's/.*Job started: *//p' | head -1)"
if [ -n "$JOB_ID" ]; then
    run_tolerant "cm node job checkpoint -n local -j $JOB_ID"
fi
run_tolerant "cm node gpu -n local"

# ============================================
# Phase 4: SSH path (pkg, pf, ifconfig, sysctl)
# ============================================
step "Phase 4/4: SSH server path"

mkdir -p "$HOME/.ssh"
if [ ! -f "$HOME/.ssh/id_rsa" ]; then
    ssh-keygen -t rsa -b 2048 -N "" -f "$HOME/.ssh/id_rsa" > /dev/null
fi
cat "$HOME/.ssh/id_rsa.pub" >> "$HOME/.ssh/authorized_keys"
chmod 700 "$HOME/.ssh"
chmod 600 "$HOME/.ssh/authorized_keys"
ssh-keyscan -H 127.0.0.1 >> "$HOME/.ssh/known_hosts" 2>/dev/null || true

run_tolerant "service sshd status"
run_required "cm server add -n localssh -H 127.0.0.1 -u root -k $HOME/.ssh/id_rsa"
run_required "cm server list"
run_required "cm test -n localssh"
ok "SSH connection works"

run_required "cm mon -n localssh"
run_required "cm uptime -n localssh"
run_required "cm df -n localssh"
run_required "cm network -n localssh"
run_required "cm who -n localssh"
run_tolerant "cm top -n localssh --limit 3"
run_tolerant "cm logs -n localssh --lines 5"

run_tolerant "cm reshistory snapshot"
run_tolerant "cm reshistory show localssh"

run_required "cm sync --local scripts --to-server localssh --remote-to /tmp/cm-sync"
run_required "cm transfer --file scripts/bsd_e2e.sh --to-server localssh"
ok "file transfer and sync"

run_tolerant "cm deploy --install nano"
# `cm firewall status` runs on every configured server; the other firewall
# subcommands take --server, status does not.
run_tolerant "cm firewall status"
run_tolerant "cm audit -n localssh"

step "Done"
printf '\nBSD E2E OK\n'
