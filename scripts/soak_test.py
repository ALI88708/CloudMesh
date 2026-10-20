#!/usr/bin/env python3
"""Run CloudMesh under repeated load and fail on the first error or leak.

The harness drives the same surfaces a long-lived install uses: the REST API
(status, servers, nodes), the SQLite storage layer, and the tamper-evident
command ledger. It runs for a fixed duration, records a CSV of every
iteration, and exits non-zero on the first failure so a release can be gated
on a clean hour.

Usage:
    python scripts/soak_test.py --duration 3600 --interval 2 --workspace <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
import time
import traceback
import urllib.request
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_KEY = "soak"
SERVER_NAME = "soak-node"
WARMUP_ITERATIONS = 10
MAX_RSS_GROWTH = 200 * 1024 * 1024
BACKUP_EVERY = 30
RESTART_EVERY = 100


def parse_args(argv=None):
    """Parse the harness arguments."""
    parser = argparse.ArgumentParser(description="Soak-test CloudMesh.")
    parser.add_argument(
        "--duration",
        type=float,
        default=3600.0,
        help="how long to run, in seconds (default: 3600)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="seconds between iterations (default: 2)",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="directory for the state and the results CSV (default: a temp dir)",
    )
    return parser.parse_args(argv)


def _get_json(port, path, timeout=10):
    """Call an API endpoint with the soak key and decode the JSON body."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers={"X-Api-Key": API_KEY},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"{path} returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def _start_api(server_mgr):
    """Start the API on an ephemeral port and return it with its port."""
    from cloudmesh.core.advanced import CloudMeshAPI

    api = CloudMeshAPI(server_mgr, None, {}, port=0, api_key=API_KEY)
    # The harness is the only client and it is trusted. The API's own rate
    # limiter would otherwise ban it part-way through a long run, so the
    # limit is raised for this in-process server only.
    api._ddos.rate_limiter.max_requests = 1_000_000
    return api, api.start()


def _run_iteration(index, port, storage, server_mgr, ledger):
    """Exercise every surface once and return the recorded status."""
    status = _get_json(port, "/api/status")
    if status.get("status") != "ok":
        raise RuntimeError(f"iteration {index}: /api/status returned {status!r}")

    servers = _get_json(port, "/api/servers")
    if SERVER_NAME not in servers.get("servers", {}):
        raise RuntimeError(f"iteration {index}: {SERVER_NAME} missing from /api/servers")

    nodes = _get_json(port, "/api/nodes")
    if "nodes" not in nodes:
        raise RuntimeError(f"iteration {index}: /api/nodes returned {nodes!r}")

    stored = [row.get("name") for row in storage.list_servers()]
    if SERVER_NAME not in stored:
        raise RuntimeError(f"iteration {index}: {SERVER_NAME} missing from storage")
    if SERVER_NAME not in server_mgr.list_servers():
        raise RuntimeError(f"iteration {index}: {SERVER_NAME} missing from the server manager")

    ledger.log("soak", str(index))
    verdict = ledger.verify()
    if not verdict.get("valid"):
        raise RuntimeError(f"iteration {index}: command ledger is invalid: {verdict!r}")
    return "ok"


def run_soak(duration, interval, workspace):
    """Run the soak loop and return the iteration count and elapsed seconds."""
    from cloudmesh.core.cmdlog import CommandLog
    from cloudmesh.core.security import SecurityManager
    from cloudmesh.core.server import ServerManager
    from cloudmesh.core.storage import StorageManager

    storage = StorageManager(workspace)
    security = SecurityManager(workspace)
    server_mgr = ServerManager(security, storage=storage)

    if storage.get_server(SERVER_NAME) is None:
        added = storage.add_server(
            SERVER_NAME, "127.0.0.1", "soak", port=22, password="soak-secret"
        )
        if not added:
            raise RuntimeError(f"storage rejected the {SERVER_NAME} server")

    api, port = _start_api(server_mgr)
    ledger = CommandLog()
    process = psutil.Process()
    results_path = Path(workspace) / "soak_results.csv"

    iterations = 0
    baseline_rss = None
    started = time.monotonic()

    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["elapsed", "iteration", "rss_bytes", "status"])

        while True:
            elapsed = time.monotonic() - started
            if elapsed >= duration and iterations > 0:
                break

            index = iterations + 1
            status = _run_iteration(index, port, storage, server_mgr, ledger)
            rss = process.memory_info().rss
            writer.writerow([f"{elapsed:.3f}", index, rss, status])
            handle.flush()
            iterations = index

            if index == WARMUP_ITERATIONS:
                baseline_rss = rss
            elif baseline_rss is not None and rss - baseline_rss > MAX_RSS_GROWTH:
                raise RuntimeError(
                    f"memory grew {rss - baseline_rss} bytes after warm-up, "
                    f"above the {MAX_RSS_GROWTH} byte limit"
                )

            if index % BACKUP_EVERY == 0:
                storage.backup_database()
            if index % RESTART_EVERY == 0:
                api.stop()
                api, port = _start_api(server_mgr)
                if _get_json(port, "/api/status").get("status") != "ok":
                    raise RuntimeError("the API did not rebind after a restart")

            if iterations % 100 == 0:
                print(f"soak progress: {iterations} iterations in {elapsed:.0f}s")

            time.sleep(interval)

    return iterations, time.monotonic() - started


def main(argv=None):
    """Run the harness and return the process exit code."""
    args = parse_args(argv)
    if args.workspace:
        workspace = Path(args.workspace).expanduser().resolve()
    else:
        workspace = Path(tempfile.mkdtemp(prefix="cloudmesh-soak-"))
    workspace.mkdir(parents=True, exist_ok=True)

    # Every module that keeps state resolves its directory from this
    # variable, so it has to be set before the first CloudMesh import.
    os.environ["CLOUDMESH_DIR"] = str(workspace)

    try:
        iterations, elapsed = run_soak(args.duration, args.interval, workspace)
    except Exception:
        traceback.print_exc()
        print("soak failed", file=sys.stderr)
        return 1

    print(f"soak passed: {iterations} iterations in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
