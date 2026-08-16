import argparse
import sys
import os
import json
import tempfile
import shlex
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from core.security import SecurityManager
from core.server import ServerManager
from core.monitor import ResourceMonitor
from core.scheduler import TaskScheduler
from core.dashboard import Dashboard
from core.transfer import FileTransfer
from core.history import HistoryManager
from core.deploy import PackageDeployer
from core.alerts import AlertManager
from core.groups import GroupsManager
from core.cmdlog import CommandLog
from core.sync import DirectorySync
from core.service import ServiceMode
from core.node_client import NodeClient
from core.gpu import GPUTelemetry
from core.jobs import JobManager
from core.features import (
    ping_all, get_uptime, get_top_processes, get_disk_detail,
    get_network_info, get_logged_users, search_files, get_recent_logs,
    export_config, import_config, encrypt_file, decrypt_file,
    network_speed_test, scan_subnet, cleanup_old, generate_report,
    create_alias, get_aliases, remove_alias, get_version,
)
from core.advanced import (
    discover_network, run_full_benchmark, ScheduleManager, NotifyManager,
    CloudMeshAPI, ProfileManager, audit_server, quick_ssh,
    TemplateManager, generate_network_map,
)

console = Console()

NODE_KEYS_FILE = Path(__file__).parent / ".node_keys.json"


def init_components():
    security = SecurityManager()
    server_mgr = ServerManager(security)
    monitor = ResourceMonitor(server_mgr)
    scheduler = TaskScheduler(server_mgr, monitor)
    dashboard = Dashboard(scheduler)
    transfer = FileTransfer(server_mgr)
    history = HistoryManager(monitor)
    deployer = PackageDeployer(server_mgr)
    alert_mgr = AlertManager(monitor)
    groups_mgr = GroupsManager(security)
    cmd_log = CommandLog()
    return security, server_mgr, monitor, scheduler, dashboard, transfer, history, deployer, alert_mgr, groups_mgr, cmd_log


def cmd_server_add(args):
    security, server_mgr, *_ = init_components()
    try:
        server_mgr.add_server(
            name=args.name, host=args.host, user=args.user,
            port=args.port, key_path=args.key, password=args.password,
        )
        console.print(f"[green]Server '{args.name}' added successfully.[/]")
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)


def cmd_server_remove(args):
    security, server_mgr, *_ = init_components()
    try:
        server_mgr.remove_server(args.name)
        console.print(f"[green]Server '{args.name}' removed.[/]")
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        sys.exit(1)


def cmd_server_list(args):
    security, server_mgr, *_ = init_components()
    servers = server_mgr.list_servers()
    if not servers:
        console.print("[dim]No servers configured.[/]")
        return
    table = Table(title="Configured Servers", box=box.ROUNDED)
    table.add_column("Name", style="bold")
    table.add_column("Host")
    table.add_column("User")
    table.add_column("Port")
    table.add_column("Status")
    for name in servers:
        info = server_mgr.get_server_info(name)
        table.add_row(name, info["host"], info["user"], str(info.get("port", 22)), info.get("status", "unknown"))
    console.print(table)


def cmd_server_test(args):
    security, server_mgr, *_ = init_components()
    console.print(f"[cyan]Testing connection to '{args.name}'...[/]")
    success, msg = server_mgr.test_connection(args.name)
    if success:
        console.print(f"[green]{msg}[/]")
        server_mgr.detect_os(args.name)
        info = server_mgr.get_server_info(args.name)
        console.print(f"[green]Detected OS: {info.get('os_type', 'unknown')}[/]")
    else:
        console.print(f"[red]{msg}[/]")
        sys.exit(1)


def cmd_monitor(args):
    _, server_mgr, monitor, *_ = init_components()
    if args.local:
        metrics = monitor.get_local_metrics()
        _print_metrics("Local Machine", metrics)
        return
    names = [args.name] if args.name else server_mgr.list_servers()
    if not names:
        console.print("[dim]No servers configured.[/]")
        return
    for name in names:
        try:
            metrics = monitor.get_all_metrics(name)
            _print_metrics(name, metrics)
        except Exception as e:
            console.print(f"[red]Error on {name}: {e}[/]")


def _print_metrics(name, metrics):
    if metrics is None:
        console.print(f"[red]{name}: Unable to fetch metrics[/]")
        return
    cpu = metrics.get("cpu_percent")
    ram = metrics.get("ram") or {}
    disk = metrics.get("disk") or {}
    lines = []
    lines.append(f"  CPU:  {cpu}%" if cpu is not None else "  CPU:  N/A")
    lines.append(f"  RAM:  {ram.get('used_gb', '?')}/{ram.get('total_gb', '?')} GB ({ram.get('percent', '?')}%)")
    lines.append(f"  Disk: {disk.get('used_gb', '?')}/{disk.get('total_gb', '?')} GB ({disk.get('percent', '?')}%)")
    console.print(Panel("\n".join(lines), title=f"[bold]{name}[/]", border_style="cyan", padding=(1, 2)))


def cmd_dashboard(args):
    _, _, _, scheduler, dashboard, *_ = init_components()
    if args.live:
        dashboard.render_live(refresh_interval=args.interval)
    else:
        dashboard.render_full()


def cmd_run(args):
    _, _, _, scheduler, _, _, _, _, _, _, cmd_log = init_components()
    cmd_log.log("run", args.command)
    if args.best:
        console.print("[cyan]Running on best server...[/]")
        result = scheduler.run_on_best(args.command)
        if result["success"]:
            console.print(f"[green]Success on {result['server']} (weight: {result['weight']}):[/]")
            if result.get("output"):
                console.print(result["output"])
        else:
            console.print(f"[red]Failed on {result.get('server', '?')}: {result.get('error', 'Unknown')}[/]")
            sys.exit(1)
    elif args.servers:
        server_names = [s.strip() for s in args.servers.split(",")]
        console.print(f"[cyan]Distributing to: {', '.join(server_names)}[/]")
        results = scheduler.distribute_command(args.command, server_names)
        for name, res in results.items():
            icon = "[green]OK[/]" if res["success"] else "[red]FAIL[/]"
            console.print(f"  {icon} {name}: {res.get('output', '')[:100]}")
    else:
        console.print("[cyan]Running on all servers...[/]")
        results = scheduler.distribute_command(args.command)
        for name, res in results.items():
            icon = "[green]OK[/]" if res["success"] else "[red]FAIL[/]"
            console.print(f"  {icon} {name}: {res.get('output', '')[:100]}")


def cmd_plan(args):
    _, _, _, scheduler, *_ = init_components()
    tasks = [f"task_{i+1}" for i in range(args.tasks)]
    plan = scheduler.get_distribution_plan(tasks)
    table = Table(title="Distribution Plan", box=box.ROUNDED)
    table.add_column("Server", style="bold")
    table.add_column("Tasks")
    table.add_column("Proportion")
    table.add_column("Weight")
    for name, data in plan.items():
        table.add_row(name, ", ".join(data["tasks"]), f"{data['proportion']}%", str(data["weight"]))
    console.print(table)


def cmd_transfer(args):
    _, server_mgr, *_ = init_components()
    transfer = FileTransfer(server_mgr)
    try:
        if args.from_server and args.to_server:
            result = transfer.transfer_between(args.from_server, args.to_server, args.remote, args.to)
            console.print(f"[green]{result['message']}[/]")
        elif args.to_server:
            result = transfer.upload(args.to_server, args.file, args.remote or args.file)
            console.print(f"[green]{result['message']}[/]")
        elif args.from_server:
            result = transfer.download(args.from_server, args.remote, args.file)
            console.print(f"[green]{result['message']}[/]")
        else:
            console.print("[red]Specify --to-server, --from-server, or both[/]")
    except Exception as e:
        console.print(f"[red]Transfer failed: {e}[/]")
        sys.exit(1)


def cmd_sync(args):
    _, server_mgr, *_ = init_components()
    sync = DirectorySync(server_mgr)
    try:
        if args.from_server and args.to_server:
            console.print(f"[cyan]Syncing from {args.from_server} to {args.to_server}...[/]")
            results = sync.sync_between(args.from_server, args.to_server, args.remote_from, args.remote_to)
        elif args.to_server:
            console.print(f"[cyan]Syncing {args.local} to {args.to_server}:{args.remote_to}...[/]")
            results = sync.sync_to(args.local, args.to_server, args.remote_to)
        elif args.from_server:
            console.print(f"[cyan]Syncing from {args.from_server} to {args.local}...[/]")
            results = sync.sync_from(args.from_server, args.remote_from, args.local)
        else:
            console.print("[red]Specify --to-server, --from-server, or both[/]")
            return

        synced = sum(1 for r in results if r.get("action") == "synced")
        skipped = sum(1 for r in results if r.get("action") == "skipped")
        errors = sum(1 for r in results if not r.get("success"))
        console.print(f"[green]Synced: {synced} | Skipped: {skipped} | Errors: {errors}[/]")
        for r in results:
            if not r.get("success"):
                console.print(f"  [red]Error: {r.get('file', '?')} - {r.get('message', '?')}[/]")
    except Exception as e:
        console.print(f"[red]Sync failed: {e}[/]")


def cmd_history(args):
    _, server_mgr, monitor, *_ = init_components()
    history = HistoryManager(monitor)
    if args.record:
        history.record_all_servers(server_mgr.list_servers())
        console.print("[green]Snapshot recorded for all servers.[/]")
    elif args.stats:
        stats = history.get_stats(args.stats)
        if stats is None:
            console.print(f"[dim]No history for '{args.stats}'[/]")
            return
        table = Table(title=f"Stats: {args.stats}", box=box.ROUNDED)
        table.add_column("Metric")
        table.add_column("Avg")
        table.add_column("Min")
        table.add_column("Max")
        for m in ["cpu", "ram", "disk"]:
            d = stats[m]
            table.add_row(m.upper(), f"{d['avg']}%", f"{d['min']}%", f"{d['max']}%")
        console.print(table)
    elif args.clear:
        history.clear_history(args.clear if args.clear != "all" else None)
        console.print("[green]History cleared.[/]")
    elif args.name:
        hist = history.get_history(args.name, limit=args.limit)
        if not hist:
            console.print(f"[dim]No history for '{args.name}'[/]")
            return
        table = Table(title=f"History: {args.name}", box=box.ROUNDED)
        table.add_column("Time", style="dim")
        table.add_column("CPU")
        table.add_column("RAM")
        table.add_column("Disk")
        for row in hist:
            table.add_row(row["timestamp"][:19], f"{row['cpu_percent']}%", f"{row['ram_percent']}%", f"{row['disk_percent']}%")
        console.print(table)
    else:
        console.print("[dim]Use --name, --record, --stats, or --clear[/]")


def cmd_deploy(args):
    _, server_mgr, *_ = init_components()
    deployer = PackageDeployer(server_mgr)
    if args.install:
        console.print(f"[cyan]Installing '{args.install}' on all servers...[/]")
        results = deployer.install_on_all(args.install)
        for name, res in results.items():
            icon = "[green]OK[/]" if res.get("success") else "[red]FAIL[/]"
            msg = res.get("message") or res.get("output", "")[:80] or res.get("error", "Unknown")
            console.print(f"  {icon} {name}: {msg}")
    elif args.check:
        for name in server_mgr.list_servers():
            installed = deployer.check_installed(name, args.check)
            status = "[green]Installed[/]" if installed else "[red]Not Installed[/]"
            console.print(f"  {name}: {status}")
    elif args.script:
        servers = server_mgr.list_servers()
        server = args.server or (servers[0] if servers else None)
        if not server:
            console.print("[red]No server specified or configured[/]")
            return
        console.print(f"[cyan]Running script on {server}...[/]")
        result = deployer.run_script(server, args.script)
        if result["success"]:
            console.print(f"[green]{result['output']}[/]")
        else:
            console.print(f"[red]{result['error']}[/]")
    else:
        console.print("[dim]Use --install, --check, or --script[/]")


def cmd_alerts(args):
    _, _, _, _, _, _, _, _, alert_mgr, *_ = init_components()
    if args.add:
        parts = args.add.split(",")
        if len(parts) < 3:
            console.print("[red]Format: name,metric,threshold (e.g. high-cpu,cpu,80)[/]")
            return
        name, metric, threshold = parts[0], parts[1], float(parts[2])
        server = parts[3] if len(parts) > 3 else None
        alert_mgr.add_rule(name, metric, threshold, server=server)
        console.print(f"[green]Alert '{name}' added: {metric} > {threshold}%[/]")
    elif args.remove:
        alert_mgr.remove_rule(args.remove)
        console.print(f"[green]Alert '{args.remove}' removed.[/]")
    elif args.list_rules:
        rules = alert_mgr.list_rules()
        if not rules:
            console.print("[dim]No alert rules configured.[/]")
            return
        table = Table(title="Alert Rules", box=box.ROUNDED)
        table.add_column("Name", style="bold")
        table.add_column("Metric")
        table.add_column("Threshold")
        table.add_column("Server")
        for r in rules:
            table.add_row(r["name"], r["metric"], f"{r['threshold']}%", r.get("server") or "all")
        console.print(table)
    elif args.check:
        triggered = alert_mgr.check_alerts()
        if not triggered:
            console.print("[green]No alerts triggered.[/]")
        else:
            for a in triggered:
                console.print(f"[red]ALERT: {a['rule']} on {a['server']} - {a['metric']}={a['value']}% > {a['threshold']}%[/]")
    elif args.history:
        hist = alert_mgr.get_history(limit=args.limit)
        if not hist:
            console.print("[dim]No alert history.[/]")
            return
        for a in hist[-10:]:
            console.print(f"  [{a['timestamp'][:19]}] {a['rule']} on {a['server']}: {a['metric']}={a['value']}%")
    else:
        console.print("[dim]Use --add, --remove, --list-rules, --check, or --history[/]")


def cmd_groups(args):
    _, _, _, _, _, _, _, _, _, groups_mgr, _ = init_components()
    if args.action == "list":
        groups = groups_mgr.list_groups()
        if not groups:
            console.print("[dim]No groups configured.[/]")
            return
        table = Table(title="Groups", box=box.ROUNDED)
        table.add_column("Group", style="bold")
        table.add_column("Devices")
        for g, devs in groups.items():
            table.add_row(g, ", ".join(devs) if devs else "[dim]empty[/]")
        console.print(table)
    elif args.action == "create":
        try:
            groups_mgr.create_group(args.name)
            console.print(f"[green]Group '{args.name}' created.[/]")
        except ValueError as e:
            console.print(f"[red]{e}[/]")
    elif args.action == "delete":
        try:
            groups_mgr.delete_group(args.name)
            console.print(f"[green]Group '{args.name}' deleted.[/]")
        except ValueError as e:
            console.print(f"[red]{e}[/]")
    elif args.action == "add":
        groups_mgr.add_to_group(args.group, args.device)
        console.print(f"[green]Added '{args.device}' to '{args.group}'.[/]")
    elif args.action == "remove":
        groups_mgr.remove_from_group(args.group, args.device)
        console.print(f"[green]Removed '{args.device}' from '{args.group}'.[/]")
    elif args.action == "run":
        _, _, _, scheduler, *_ = init_components()
        devs = groups_mgr.get_group_devices(args.group)
        if not devs:
            console.print(f"[red]Group '{args.group}' is empty or not found.[/]")
            return
        console.print(f"[cyan]Running on group '{args.group}': {', '.join(devs)}[/]")
        results = scheduler.distribute_command(args.command, devs)
        for name, res in results.items():
            icon = "[green]OK[/]" if res["success"] else "[red]FAIL[/]"
            console.print(f"  {icon} {name}")


def cmd_service(args):
    _, server_mgr, monitor, _, _, _, history, _, alert_mgr, *_ = init_components()
    service = ServiceMode(server_mgr, monitor, alert_mgr, history)
    if args.action == "start":
        console.print("[cyan]Starting service...[/]")
        service.start(interval=args.interval)
    elif args.action == "stop":
        service.stop()
    elif args.action == "status":
        service.status()
    elif args.action == "logs":
        service.logs(limit=args.limit)


def cmd_compare(args):
    _, server_mgr, monitor, *_ = init_components()
    names = args.devices.split(",") if args.devices else server_mgr.list_servers()
    if len(names) < 2:
        console.print("[red]Need at least 2 devices to compare.[/]")
        return

    table = Table(title="Device Comparison", box=box.ROUNDED)
    table.add_column("Metric", style="bold")
    for name in names:
        table.add_column(name)

    all_metrics = {}
    for name in names:
        try:
            m = monitor.get_all_metrics(name)
            all_metrics[name] = m
        except Exception:
            all_metrics[name] = None

    cpu_vals = []
    ram_vals = []
    disk_vals = []
    weight_vals = []
    for name in names:
        m = all_metrics[name]
        cpu = (m or {}).get("cpu_percent") or "N/A"
        ram = ((m or {}).get("ram") or {}).get("percent") or "N/A"
        disk = ((m or {}).get("disk") or {}).get("percent") or "N/A"
        weight = monitor.calculate_weight(m)
        cpu_vals.append(f"{cpu}%")
        ram_vals.append(f"{ram}%")
        disk_vals.append(f"{disk}%")
        weight_vals.append(str(weight))

    table.add_row("CPU", *cpu_vals)
    table.add_row("RAM", *ram_vals)
    table.add_row("Disk", *disk_vals)
    table.add_row("Weight", *weight_vals)

    best_name = max(names, key=lambda n: monitor.calculate_weight(all_metrics.get(n)))
    table.add_row("Best", *[("[green]YES[/]" if n == best_name else "") for n in names])

    console.print(table)


def cmd_cmdlog(args):
    _, _, _, _, _, _, _, _, _, _, cmd_log = init_components()
    if args.clear:
        cmd_log.clear()
        console.print("[green]Command log cleared.[/]")
    elif args.search:
        entries = cmd_log.search(args.search)
        if not entries:
            console.print(f"[dim]No matches for '{args.search}'[/]")
            return
        table = Table(title=f"Search: {args.search}", box=box.ROUNDED)
        table.add_column("Time", style="dim")
        table.add_column("Command")
        for e in entries[-20:]:
            table.add_row(e["timestamp"][:19], e["command"])
        console.print(table)
    else:
        entries = cmd_log.get_recent(args.limit)
        if not entries:
            console.print("[dim]No command history.[/]")
            return
        table = Table(title="Command History", box=box.ROUNDED)
        table.add_column("Time", style="dim")
        table.add_column("Command")
        for e in entries:
            table.add_row(e["timestamp"][:19], e["command"])
        console.print(table)


def cmd_slice(args):
    _, _, _, scheduler, *_ = init_components()
    files = [f.strip() for f in args.files.split(",") if f.strip()]
    if not files:
        console.print("[red]No files specified. Use --files file1,file2,file3[/]")
        return
    server_names = [s.strip() for s in args.servers.split(",")] if args.servers else None
    plan = scheduler.slice_files(files, server_names)
    if not plan:
        console.print("[dim]No distribution plan generated.[/]")
        return
    table = Table(title="File Distribution Plan", box=box.ROUNDED)
    table.add_column("Server", style="bold")
    table.add_column("Files")
    table.add_column("Count")
    table.add_column("Proportion")
    table.add_column("Weight")
    for name, data in plan.items():
        table.add_row(name, ", ".join(data["files"][:3]) + ("..." if len(data["files"]) > 3 else ""), str(data["count"]), f"{data['proportion']}%", str(data["weight"]))
    console.print(table)
    if args.execute:
        console.print(f"\n[cyan]Executing command on each server...[/]")
        for name, data in plan.items():
            for f in data["files"]:
                cmd = args.execute.replace("{file}", f)
                console.print(f"  [dim]{name}: {cmd}[/]")


def cmd_autosync(args):
    _, server_mgr, *_ = init_components()
    from core.sync import DirectorySync
    sync = DirectorySync(server_mgr)
    if not args.local or not args.to_server:
        console.print("[red]Specify --local and --to-server[/]")
        return
    console.print(f"[cyan]Auto-syncing {args.local} to {args.to_server}...[/]")
    try:
        results = sync.sync_to(args.local, args.to_server, args.remote_to or args.local)
        synced = sum(1 for r in results if r.get("action") == "synced")
        skipped = sum(1 for r in results if r.get("action") == "skipped")
        errors = sum(1 for r in results if not r.get("success"))
        console.print(f"[green]Synced: {synced} | Skipped: {skipped} | Errors: {errors}[/]")
    except Exception as e:
        console.print(f"[red]Auto-sync failed: {e}[/]")


def cmd_interactive(args):
    _, server_mgr, monitor, scheduler, _, _, _, _, _, groups_mgr, cmd_log = init_components()
    from core.tui import InteractiveTUI
    tui = InteractiveTUI(server_mgr, monitor, scheduler, groups_mgr, cmd_log)
    tui.run()


def cmd_backup(args):
    security, *_ = init_components()
    if args.restore:
        try:
            security.restore_backup(args.restore)
            console.print(f"[green]Restored from {args.restore}[/]")
        except Exception as e:
            console.print(f"[red]Restore failed: {e}[/]")
            sys.exit(1)
    else:
        backups = security.list_backups()
        if not backups:
            console.print("[dim]No backups found.[/]")
            return
        table = Table(title="Available Backups", box=box.ROUNDED)
        table.add_column("File", style="bold")
        for b in backups:
            table.add_row(str(b.name))
        console.print(table)


def cmd_node_gpu(args):
    keys = _load_node_keys()
    names = [args.name] if args.name else list(keys.keys())
    if not names:
        console.print("[dim]No nodes configured.[/]")
        return
    gpu_telemetry = GPUTelemetry()
    table = Table(title="GPU Status", box=box.ROUNDED)
    table.add_column("Node", style="bold")
    table.add_column("GPU")
    table.add_column("Usage")
    table.add_column("VRAM")
    table.add_column("Temp")
    for name in names:
        if name not in keys:
            continue
        info = keys[name]
        client = NodeClient(info["host"], info["port"], info["key"])
        gpu = client.get_gpu()
        if gpu and gpu.get("available"):
            for g in gpu.get("gpus", []):
                table.add_row(
                    name,
                    g.get("name", "?"),
                    f"{g.get('utilization_gpu', '?')}%",
                    f"{g.get('memory_used_mb', '?')}/{g.get('memory_total_mb', '?')} MB",
                    f"{g.get('temperature_gpu', '?')}°C",
                )
        else:
            table.add_row(name, "[dim]No GPU[/]", "-", "-", "-")
    console.print(table)


def cmd_node_job(args):
    keys = _load_node_keys()
    if args.action == "start":
        if args.name not in keys:
            console.print(f"[red]Node '{args.name}' not found.[/]")
            return
        info = keys[args.name]
        client = NodeClient(info["host"], info["port"], info["key"])
        console.print(f"[cyan]Starting job on {args.name}: {args.command}[/]")
        result = client.start_job(args.command, timeout=args.timeout)
        if result and result.get("job_id"):
            console.print(f"[green]Job started: {result['job_id']}[/]")
        else:
            console.print(f"[red]Failed: {result}[/]")
    elif args.action == "status":
        if args.name not in keys:
            console.print(f"[red]Node '{args.name}' not found.[/]")
            return
        info = keys[args.name]
        client = NodeClient(info["host"], info["port"], info["key"])
        result = client.check_job(args.job_id)
        if result:
            status_color = "green" if result.get("status") == "completed" else "red" if result.get("status") in ("failed", "error") else "yellow"
            console.print(f"Job [bold]{args.job_id}[/]: [{status_color}]{result.get('status', '?')}[/]")
            console.print(f"  Command: {result.get('command', '?')}")
            console.print(f"  Exit code: {result.get('exit_code', '?')}")
            if result.get("stdout"):
                console.print(f"  stdout: {result['stdout'][:200]}")
            if result.get("stderr"):
                console.print(f"  stderr: {result['stderr'][:200]}")
        else:
            console.print(f"[red]Job not found[/]")
    elif args.action == "list":
        if args.name not in keys:
            console.print(f"[red]Node '{args.name}' not found.[/]")
            return
        info = keys[args.name]
        client = NodeClient(info["host"], info["port"], info["key"])
        jobs = client.list_jobs()
        if not jobs:
            console.print("[dim]No jobs.[/]")
            return
        table = Table(title=f"Jobs on {args.name}", box=box.ROUNDED)
        table.add_column("ID", style="bold")
        table.add_column("Command")
        table.add_column("Status")
        table.add_column("Created")
        for j in jobs:
            status = j.get("status", "?")
            color = "green" if status == "completed" else "red" if status in ("failed", "error") else "yellow"
            table.add_row(j.get("id", "?"), j.get("command", "?")[:40], f"[{color}]{status}[/]", j.get("started_at", "?")[:19])
        console.print(table)
    elif args.action == "kill":
        if args.name not in keys:
            console.print(f"[red]Node '{args.name}' not found.[/]")
            return
        info = keys[args.name]
        client = NodeClient(info["host"], info["port"], info["key"])
        result = client.kill_job(args.job_id)
        if result and result.get("success"):
            console.print(f"[green]{result.get('message', 'Killed')}[/]")
        else:
            console.print(f"[red]{result}[/]")


def cmd_node_info(args):
    _, server_mgr, monitor, *_ = init_components()
    name = args.name
    try:
        metrics = monitor.get_all_metrics(name)
        info = server_mgr.get_server_info(name)
        weight = monitor.calculate_weight(metrics)
        lines = []
        lines.append(f"[bold]Name:[/] {name}")
        lines.append(f"[bold]Host:[/] {info['host']}")
        lines.append(f"[bold]User:[/] {info['user']}")
        lines.append(f"[bold]OS:[/] {info.get('os_type', '?')}")
        lines.append(f"[bold]Status:[/] {info.get('status', '?')}")
        lines.append(f"[bold]Weight:[/] {weight}")
        if metrics:
            cpu = metrics.get("cpu_percent")
            ram = metrics.get("ram") or {}
            disk = metrics.get("disk") or {}
            lines.append(f"\n[bold]CPU:[/] {cpu}%")
            lines.append(f"[bold]RAM:[/] {ram.get('used_gb', '?')}/{ram.get('total_gb', '?')} GB ({ram.get('percent', '?')}%)")
            lines.append(f"[bold]Disk:[/] {disk.get('used_gb', '?')}/{disk.get('total_gb', '?')} GB ({disk.get('percent', '?')}%)")
        console.print(Panel("\n".join(lines), title=f"[bold]{name}[/]", border_style="cyan", padding=(1, 2)))
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")


def _load_node_keys():
    if NODE_KEYS_FILE.exists():
        try:
            return json.loads(NODE_KEYS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_node_keys(keys):
    NODE_KEYS_FILE.write_text(json.dumps(keys, indent=2))


def cmd_node_add_cloud(args):
    keys = _load_node_keys()
    keys[args.name] = {"host": args.host, "port": args.port, "key": args.auth_key}
    _save_node_keys(keys)
    console.print(f"[green]Node '{args.name}' added ({args.host}:{args.port}).[/]")


def cmd_node_remove(args):
    keys = _load_node_keys()
    if args.name in keys:
        del keys[args.name]
        _save_node_keys(keys)
        console.print(f"[green]Node '{args.name}' removed.[/]")
    else:
        console.print(f"[red]Node '{args.name}' not found.[/]")


def cmd_node_list_cloud(args):
    keys = _load_node_keys()
    if not keys:
        console.print("[dim]No nodes configured.[/]")
        return
    table = Table(title="Cloud Nodes", box=box.ROUNDED)
    table.add_column("Name", style="bold")
    table.add_column("Host")
    table.add_column("Port")
    table.add_column("Status")
    for name, info in keys.items():
        client = NodeClient(info["host"], info["port"], info["key"])
        online = client.ping()
        status = "[green]ONLINE[/]" if online else "[red]OFFLINE[/]"
        table.add_row(name, info["host"], str(info["port"]), status)
    console.print(table)


def cmd_node_test(args):
    keys = _load_node_keys()
    if args.name not in keys:
        console.print(f"[red]Node '{args.name}' not found.[/]")
        return
    info = keys[args.name]
    client = NodeClient(info["host"], info["port"], info["key"])
    console.print(f"[cyan]Testing node '{args.name}'...[/]")
    if client.ping():
        node_info = client.get_info()
        console.print(f"[green]Node ONLINE[/]")
        if node_info:
            console.print(f"  Hostname: {node_info.get('hostname', '?')}")
            console.print(f"  Platform: {node_info.get('platform', '?')}")
    else:
        console.print(f"[red]Node OFFLINE or unreachable[/]")


def cmd_node_info_cloud(args):
    keys = _load_node_keys()
    if args.name not in keys:
        console.print(f"[red]Node '{args.name}' not found.[/]")
        return
    info = keys[args.name]
    client = NodeClient(info["host"], info["port"], info["key"])
    metrics = client.get_metrics()
    node_info = client.get_info()
    lines = []
    lines.append(f"[bold]Name:[/] {args.name}")
    lines.append(f"[bold]Host:[/] {info['host']}:{info['port']}")
    if node_info:
        lines.append(f"[bold]Hostname:[/] {node_info.get('hostname', '?')}")
        lines.append(f"[bold]Platform:[/] {node_info.get('platform', '?')}")
    if metrics:
        cpu = metrics.get("cpu_percent")
        ram = metrics.get("ram") or {}
        disk = metrics.get("disk") or {}
        lines.append(f"\n[bold]CPU:[/] {cpu}%")
        lines.append(f"[bold]RAM:[/] {ram.get('used_gb', '?')}/{ram.get('total_gb', '?')} GB ({ram.get('percent', '?')}%)")
        lines.append(f"[bold]Disk:[/] {disk.get('used_gb', '?')}/{disk.get('total_gb', '?')} GB ({disk.get('percent', '?')}%)")
    console.print(Panel("\n".join(lines), title=f"[bold]{args.name}[/]", border_style="cyan", padding=(1, 2)))


def cmd_node_monitor(args):
    keys = _load_node_keys()
    names = [args.name] if args.name else list(keys.keys())
    if not names:
        console.print("[dim]No nodes configured.[/]")
        return
    table = Table(title="Node Resources", box=box.ROUNDED)
    table.add_column("Node", style="bold")
    table.add_column("CPU")
    table.add_column("RAM")
    table.add_column("Disk")
    table.add_column("Weight")
    for name in names:
        if name not in keys:
            continue
        info = keys[name]
        client = NodeClient(info["host"], info["port"], info["key"])
        metrics = client.get_metrics()
        if metrics:
            cpu = metrics.get("cpu_percent") or 0
            ram = (metrics.get("ram") or {}).get("percent", 0)
            disk = (metrics.get("disk") or {}).get("percent", 0)
            weight = 0
            cpu_free = 100 - cpu
            ram_free = (metrics.get("ram") or {}).get("free_gb", 0)
            weight = round(cpu_free * 0.5 + min(ram_free * 2, 50) * 0.3, 1)
            table.add_row(name, f"{cpu}%", f"{ram}%", f"{disk}%", str(weight))
        else:
            table.add_row(name, "[red]N/A[/]", "[red]N/A[/]", "[red]N/A[/]", "0")
    console.print(table)


def cmd_node_exec(args):
    keys = _load_node_keys()
    if args.name not in keys:
        console.print(f"[red]Node '{args.name}' not found.[/]")
        return
    info = keys[args.name]
    client = NodeClient(info["host"], info["port"], info["key"])
    console.print(f"[cyan]Running on {args.name}: {args.command}[/]")
    result = client.execute(args.command)
    if result.get("success"):
        console.print(f"[green]Success (exit {result.get('exit_code', 0)}):[/]")
        if result.get("stdout"):
            console.print(result["stdout"])
    else:
        console.print(f"[red]Failed: {result.get('stderr', 'Unknown error')}[/]")


def cmd_node_install(args):
    console.print(f"[cyan]Installing CloudMesh Node on {args.host}...[/]")
    security = SecurityManager()
    server_mgr = ServerManager(security)
    temp_name = f"_install_{args.host}"
    server_mgr.add_server(temp_name, args.host, args.user, key_path=args.key)
    try:
        console.print("  [dim]Uploading installer...[/]")
        node_script = Path(__file__).parent / "node" / "node-install.sh"
        if not node_script.exists():
            console.print("[red]node-install.sh not found in cloudmesh/node/[/]")
            return
        content = node_script.read_text()
        local_tmp = os.path.join(tempfile.gettempdir(), "node-install.sh")
        with open(local_tmp, "w") as f:
            f.write(content)
        transfer = FileTransfer(server_mgr)
        transfer.upload(temp_name, local_tmp, "/tmp/node-install.sh")
        server_mgr.execute(temp_name, "chmod +x /tmp/node-install.sh")
        os.remove(local_tmp)
        console.print("  [dim]Running installer...[/]")
        result = server_mgr.execute(temp_name, "bash /tmp/node-install.sh")
        if result["exit_code"] == 0:
            console.print("[green]Node installed successfully![/]")
            console.print(result["stdout"])
        else:
            console.print(f"[red]Installation failed:[/]")
            console.print(result["stderr"])
    finally:
        server_mgr.remove_server(temp_name)


# === 20 NEW FEATURES ===

def cmd_ping(args):
    security, server_mgr, *_ = init_components()
    keys = _load_node_keys() if not args.no_nodes else {}
    results = ping_all(server_mgr, keys)
    table = Table(title="Ping Results", box=box.ROUNDED)
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Message")
    for name, r in results.items():
        icon = "[green]ONLINE[/]" if r["online"] else "[red]OFFLINE[/]"
        table.add_row(name, r["type"], icon, r["msg"])
    console.print(table)


def cmd_uptime(args):
    _, server_mgr, *_ = init_components()
    names = [args.name] if args.name else server_mgr.list_servers()
    for name in names:
        up = get_uptime(server_mgr, name)
        console.print(f"  [bold]{name}:[/] {up}")


def cmd_top(args):
    _, server_mgr, *_ = init_components()
    names = [args.name] if args.name else server_mgr.list_servers()
    for name in names:
        procs = get_top_processes(server_mgr, name, args.limit, args.sort)
        table = Table(title=f"Top Processes: {name}", box=box.ROUNDED)
        table.add_column("PID")
        table.add_column(f"{'CPU' if args.sort == 'cpu' else 'RAM'} %")
        table.add_column("Command")
        for p in procs:
            table.add_row(p["pid"], p["usage"], p["name"][:60])
        console.print(table)


def cmd_disk(args):
    _, server_mgr, *_ = init_components()
    names = [args.name] if args.name else server_mgr.list_servers()
    for name in names:
        disks = get_disk_detail(server_mgr, name)
        table = Table(title=f"Disk Usage: {name}", box=box.ROUNDED)
        table.add_column("Device")
        table.add_column("Size")
        table.add_column("Used")
        table.add_column("Avail")
        table.add_column("Use%")
        table.add_column("Mount")
        for d in disks:
            table.add_row(d["device"], d["size"], d["used"], d["avail"], d["use%"], d["mount"])
        console.print(table)


def cmd_network(args):
    _, server_mgr, *_ = init_components()
    names = [args.name] if args.name else server_mgr.list_servers()
    for name in names:
        info = get_network_info(server_mgr, name)
        console.print(Panel(info, title=f"[bold]{name}[/]", border_style="cyan"))


def cmd_who(args):
    _, server_mgr, *_ = init_components()
    names = [args.name] if args.name else server_mgr.list_servers()
    for name in names:
        users = get_logged_users(server_mgr, name)
        console.print(Panel(users, title=f"Logged In: {name}", border_style="cyan"))


def cmd_find(args):
    _, server_mgr, *_ = init_components()
    if args.name not in server_mgr.list_servers():
        console.print(f"[red]Server '{args.name}' not found[/]")
        return
    files = search_files(server_mgr, args.name, args.path, args.pattern)
    if files:
        for f in files:
            console.print(f"  {f}")
    else:
        console.print("[dim]No files found[/]")


def cmd_logs(args):
    _, server_mgr, *_ = init_components()
    logs = get_recent_logs(server_mgr, args.name, args.file, args.lines)
    console.print(Panel(logs, title=f"Logs: {args.name}", border_style="cyan"))


def cmd_export(args):
    security, *_ = init_components()
    export_config(security, args.file)
    console.print(f"[green]Config exported to {args.file}[/]")


def cmd_import(args):
    security, *_ = init_components()
    import_config(security, args.file)
    console.print(f"[green]Config imported from {args.file}[/]")


def cmd_encrypt(args):
    key, out = encrypt_file(args.file)
    console.print(f"[green]Encrypted: {out}[/]")
    console.print(f"[yellow]Key: {key.decode()}[/]")


def cmd_decrypt(args):
    out = decrypt_file(args.file, args.key.encode())
    console.print(f"[green]Decrypted: {out}[/]")


def cmd_speed(args):
    _, server_mgr, *_ = init_components()
    names = [args.name] if args.name else server_mgr.list_servers()
    for name in names:
        result = network_speed_test(server_mgr, name, args.target, args.count)
        console.print(f"  [bold]{name}:[/] {result}")


def cmd_scan(args):
    console.print(f"[cyan]Scanning {args.subnet} on port {args.port}...[/]")
    found = scan_subnet(args.subnet, args.port)
    if found:
        for ip in found:
            console.print(f"  [green]{ip}[/] - Node detected!")
    else:
        console.print("[dim]No nodes found[/]")


def cmd_cleanup(args):
    security, *_ = init_components()
    removed = cleanup_old(security, max_age_days=args.days)
    console.print(f"[green]Cleaned up {removed} old files[/]")


def cmd_report(args):
    _, server_mgr, monitor, *_ = init_components()
    keys = _load_node_keys()
    report = generate_report(server_mgr, monitor, keys)
    out = Path(args.file) if args.file else Path("cloudmesh_report.json")
    out.write_text(json.dumps(report, indent=2))
    console.print(f"[green]Report saved to {out}[/]")


def cmd_alias(args):
    if args.remove:
        if remove_alias(args.remove):
            console.print(f"[green]Alias '{args.remove}' removed[/]")
        else:
            console.print(f"[red]Alias '{args.remove}' not found[/]")
        return
    if args.list:
        aliases = get_aliases()
        if not aliases:
            console.print("[dim]No aliases[/]")
            return
        table = Table(title="Aliases", box=box.ROUNDED)
        table.add_column("Alias", style="bold")
        table.add_column("Command")
        for name, cmd in aliases.items():
            table.add_row(name, cmd)
        console.print(table)
        return
    if args.name and args.cmd:
        create_alias(args.name, args.cmd)
        console.print(f"[green]Alias '{args.name}' -> '{args.cmd}'[/]")


def cmd_version(args):
    v = get_version()
    console.print(Panel(
        f"Version: {v['version']}\nPython: {v['python']}\nPlatform: {v['platform']}",
        title="CloudMesh", border_style="cyan"
    ))


# === 10 ADVANCED KILLER FEATURES ===

def cmd_discover(args):
    console.print(f"[cyan]Scanning {args.subnet}.1-255 on port {args.port}...[/]")
    found = discover_network(args.subnet, args.port, args.timeout)
    if found:
        table = Table(title="Discovered Nodes", box=box.ROUNDED)
        table.add_column("IP", style="bold")
        table.add_column("Port")
        table.add_column("Status")
        for n in found:
            table.add_row(n["ip"], str(n["port"]), f"[green]{n['status']}[/]")
        console.print(table)
        console.print(f"\n[green]Found {len(found)} node(s)[/]")
    else:
        console.print("[dim]No nodes found[/]")


def cmd_bench(args):
    if args.server:
        _, server_mgr, *_ = init_components()
        console.print(f"[cyan]Benchmarking {args.server}...[/]")
        result = run_full_benchmark(server_mgr, args.server)
    else:
        console.print("[cyan]Running local benchmark...[/]")
        result = run_full_benchmark()
    table = Table(title="Benchmark Results", box=box.ROUNDED)
    table.add_column("Test", style="bold")
    table.add_column("Result")
    if isinstance(result.get("cpu"), dict):
        table.add_row("CPU Score", str(result["cpu"].get("score", "?")))
    elif "cpu_score" in result:
        table.add_row("CPU Score", str(result["cpu_score"]))
    if isinstance(result.get("disk"), dict):
        table.add_row("Disk Write", f"{result['disk'].get('write_mb_s', '?')} MB/s")
        table.add_row("Disk Read", f"{result['disk'].get('read_mb_s', '?')} MB/s")
    elif "w" in result:
        table.add_row("Disk Write", f"{result['w']} MB/s")
        table.add_row("Disk Read", f"{result['r']} MB/s")
    if isinstance(result.get("ram"), dict):
        table.add_row("RAM Alloc", f"{result['ram'].get('alloc_time', '?')}s")
        console.print(table)
    else:
        console.print(table)


def cmd_schedule(args):
    mgr = ScheduleManager()
    if args.action == "add":
        mgr.add(args.name, args.sch_cmd, args.interval, args.server)
        console.print(f"[green]Scheduled '{args.name}' every {args.interval}s[/]")
    elif args.action == "remove":
        if mgr.remove(args.name):
            console.print(f"[green]Removed '{args.name}'[/]")
        else:
            console.print(f"[red]Not found '{args.name}'[/]")
    elif args.action == "list":
        schedules = mgr.list_all()
        if not schedules:
            console.print("[dim]No schedules[/]")
            return
        table = Table(title="Schedules", box=box.ROUNDED)
        table.add_column("Name", style="bold")
        table.add_column("Command")
        table.add_column("Interval")
        table.add_column("Next Run")
        table.add_column("Runs")
        for name, s in schedules.items():
            next_run = mgr.get_next_run(name)
            status = "[green]ON[/]" if s["enabled"] else "[red]OFF[/]"
            table.add_row(name, s["command"][:40], f"{s['interval']}s", next_run or "disabled", f"{s['run_count']} {status}")
        console.print(table)
    elif args.action == "toggle":
        if mgr.toggle(args.name):
            console.print(f"[green]Toggled '{args.name}'[/]")
        else:
            console.print(f"[red]Not found '{args.name}'[/]")


def cmd_notify(args):
    mgr = NotifyManager()
    if args.action == "setup-telegram":
        mgr.setup_telegram(args.token, args.chat_id)
        console.print("[green]Telegram configured![/]")
        mgr.send_telegram("CloudMesh notification test!")
        console.print("[dim]Test message sent[/]")
    elif args.action == "setup-discord":
        mgr.setup_discord(args.webhook)
        console.print("[green]Discord configured![/]")
        mgr.send_discord("CloudMesh notification test!")
        console.print("[dim]Test message sent[/]")
    elif args.action == "send":
        results = mgr.notify(args.message)
        for k, v in results.items():
            icon = "[green]OK[/]" if v else "[red]FAIL[/]"
            console.print(f"  {icon} {k}")
    elif args.action == "status":
        status = mgr.get_status()
        for k, v in status.items():
            console.print(f"  [bold]{k}:[/] {v}")


def cmd_api(args):
    _, server_mgr, monitor, *_ = init_components()
    keys = _load_node_keys()
    api = CloudMeshAPI(server_mgr, monitor, keys, args.port)
    port = api.start()
    console.print(f"[green]API running on http://0.0.0.0:{port}[/]")
    console.print("[dim]Endpoints: /api/status, /api/servers, /api/nodes, /api/exec/{server}?cmd={command}[/]")
    console.print("[dim]Press Ctrl+C to stop[/]")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[dim]API stopped[/]")


def cmd_profile(args):
    mgr = ProfileManager()
    if args.action == "list":
        profiles = mgr.list_profiles()
        if not profiles:
            console.print("[dim]No profiles[/]")
            return
        for p in profiles:
            console.print(f"  {p}")
    elif args.action == "save":
        security, *_ = init_components()
        config = security.load_config()
        mgr.save_profile(args.name, config)
        console.print(f"[green]Profile '{args.name}' saved[/]")
    elif args.action == "load":
        security, *_ = init_components()
        config = mgr.load_profile(args.name)
        if config:
            security.save_config(config)
            console.print(f"[green]Profile '{args.name}' loaded[/]")
        else:
            console.print(f"[red]Profile '{args.name}' not found[/]")
    elif args.action == "delete":
        if mgr.delete_profile(args.name):
            console.print(f"[green]Profile '{args.name}' deleted[/]")
        else:
            console.print(f"[red]Profile '{args.name}' not found[/]")


def cmd_audit(args):
    _, server_mgr, *_ = init_components()
    names = [args.name] if args.name else server_mgr.list_servers()
    for name in names:
        console.print(f"[cyan]Auditing {name}...[/]")
        checks = audit_server(server_mgr, name)
        table = Table(title=f"Security Audit: {name}", box=box.ROUNDED)
        table.add_column("Check", style="bold")
        table.add_column("Result")
        table.add_column("Risk")
        for c in checks:
            risk_color = "red" if c["risk"] == "high" else "yellow" if c["risk"] == "medium" else "green" if c["risk"] == "low" else "dim"
            table.add_row(c["check"], c["result"], f"[{risk_color}]{c['risk']}[/]")
        console.print(table)


def cmd_ssh(args):
    _, server_mgr, *_ = init_components()
    if args.name in server_mgr.list_servers():
        info = server_mgr.get_server_info(args.name)
        cmd = quick_ssh(info["host"], info["user"], info.get("port", 22), info.get("key_path"))
        console.print(f"[cyan]{cmd}[/]")
        console.print("[dim]Run this command to connect[/]")
    else:
        cmd = quick_ssh(args.host, args.user or "root", args.port)
        console.print(f"[cyan]{cmd}[/]")


def cmd_template(args):
    mgr = TemplateManager()
    if args.action == "add":
        mgr.add(args.name, args.tmpl_cmd, args.desc or "")
        console.print(f"[green]Template '{args.name}' added[/]")
    elif args.action == "list":
        templates = mgr.list_all()
        if not templates:
            console.print("[dim]No templates[/]")
            return
        table = Table(title="Templates", box=box.ROUNDED)
        table.add_column("Name", style="bold")
        table.add_column("Command")
        table.add_column("Description")
        for name, t in templates.items():
            table.add_row(name, t["command"][:50], t.get("description", "")[:30])
        console.print(table)
    elif args.action == "run":
        kwargs = {}
        if args.params:
            for p in args.params.split(","):
                if "=" in p:
                    k, v = p.split("=", 1)
                    kwargs[k.strip()] = v.strip()
        cmd = mgr.render(args.name, **kwargs)
        if cmd:
            console.print(f"[cyan]{cmd}[/]")
        else:
            console.print(f"[red]Template '{args.name}' not found[/]")
    elif args.action == "remove":
        if mgr.remove(args.name):
            console.print(f"[green]Template '{args.name}' removed[/]")
        else:
            console.print(f"[red]Not found '{args.name}'[/]")


def cmd_map(args):
    _, server_mgr, *_ = init_components()
    keys = _load_node_keys()
    nodes = generate_network_map(server_mgr, keys)
    if not nodes:
        console.print("[dim]No servers or nodes configured[/]")
        return
    console.print()
    console.print(Panel("[bold bright_blue]Network Map[/]", border_style="bright_blue"))
    console.print()
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Host")
    table.add_column("Status")
    for n in nodes:
        status_color = "green" if n["status"] in ("connected", "configured") else "red" if n["status"] == "error" else "yellow"
        table.add_row(n["name"], n["type"], n["host"], f"[{status_color}]{n['status']}[/]")
    console.print(table)
    console.print(f"\n[bold]Total:[/] {len(nodes)} device(s)")
    console.print()


def cmd_node_dashboard(args):
    keys = _load_node_keys()
    if not keys:
        console.print("[dim]No nodes configured.[/]")
        return
    console.print()
    console.print(Panel("[bold bright_blue]CloudMesh Node Dashboard[/]", border_style="bright_blue"))
    console.print()
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Node", style="bold")
    table.add_column("Status")
    table.add_column("CPU", min_width=22)
    table.add_column("RAM", min_width=22)
    table.add_column("Weight")
    for name, info in keys.items():
        client = NodeClient(info["host"], info["port"], info["key"])
        online = client.ping()
        if online:
            metrics = client.get_metrics()
            if metrics:
                cpu = metrics.get("cpu_percent") or 0
                ram = (metrics.get("ram") or {}).get("percent", 0)
                cpu_free = 100 - cpu
                ram_free = (metrics.get("ram") or {}).get("free_gb", 0)
                weight = round(cpu_free * 0.5 + min(ram_free * 2, 50) * 0.3, 1)
                cpu_color = "green" if cpu < 50 else "yellow" if cpu < 80 else "red"
                filled = int(cpu / 5)
                bar = f"[{cpu_color}]{'█' * filled}{'░' * (20 - filled)}[/] {cpu}%"
                ram_filled = int(ram / 5)
                ram_color = "green" if ram < 50 else "yellow" if ram < 80 else "red"
                ram_bar = f"[{ram_color}]{'█' * ram_filled}{'░' * (20 - ram_filled)}[/] {ram}%"
                table.add_row(name, "[green]ONLINE[/]", bar, ram_bar, str(weight))
            else:
                table.add_row(name, "[green]ONLINE[/]", "[dim]N/A[/]", "[dim]N/A[/]", "0")
        else:
            table.add_row(name, "[red]OFFLINE[/]", "[dim]N/A[/]", "[dim]N/A[/]", "0")
    console.print(table)
    console.print()


def main():
    parser = argparse.ArgumentParser(prog="cloudmesh", description="CloudMesh - Connect devices & servers into one resource pool")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    srv = subparsers.add_parser("server", help="Manage servers/devices")
    srv_sub = srv.add_subparsers(dest="action")
    add_p = srv_sub.add_parser("add", help="Add server/device")
    add_p.add_argument("--name", "-n", required=True)
    add_p.add_argument("--host", "-H", required=True)
    add_p.add_argument("--user", "-u", required=True)
    add_p.add_argument("--port", "-p", type=int, default=22)
    add_p.add_argument("--key", "-k", help="SSH key path")
    add_p.add_argument("--password", help="SSH password")
    rm_p = srv_sub.add_parser("remove", help="Remove server/device")
    rm_p.add_argument("--name", "-n", required=True)
    srv_sub.add_parser("list", help="List all connected nodes")
    test_p = srv_sub.add_parser("test", help="Test connection")
    test_p.add_argument("--name", "-n", required=True)
    info_p = srv_sub.add_parser("info", help="Show node details")
    info_p.add_argument("--name", "-n", required=True)

    mon = subparsers.add_parser("monitor", help="Monitor resources")
    mon.add_argument("--name", "-n", help="Server name")
    mon.add_argument("--local", "-l", action="store_true")

    dash = subparsers.add_parser("dashboard", help="Show dashboard")
    dash.add_argument("--live", "-l", action="store_true")
    dash.add_argument("--interval", "-i", type=int, default=5)

    run_p = subparsers.add_parser("run", help="Run command")
    run_p.add_argument("command")
    run_p.add_argument("--best", "-b", action="store_true")
    run_p.add_argument("--servers", "-s")

    plan_p = subparsers.add_parser("plan", help="Distribution plan")
    plan_p.add_argument("--tasks", "-t", type=int, default=5)

    trn = subparsers.add_parser("transfer", help="Transfer files")
    trn.add_argument("--file", "-f", help="Local file path")
    trn.add_argument("--remote", "-r", help="Remote file path")
    trn.add_argument("--to-server", help="Upload to server")
    trn.add_argument("--from-server", help="Download from server")
    trn.add_argument("--to", help="Destination path (server-to-server)")

    sy = subparsers.add_parser("sync", help="Sync directories")
    sy.add_argument("--local", "-l", help="Local directory")
    sy.add_argument("--remote-from", help="Remote directory (source)")
    sy.add_argument("--remote-to", help="Remote directory (destination)")
    sy.add_argument("--to-server", help="Sync to server")
    sy.add_argument("--from-server", help="Sync from server")

    hist = subparsers.add_parser("history", help="Resource history")
    hist.add_argument("--name", "-n", help="Server name")
    hist.add_argument("--record", action="store_true", help="Record snapshot")
    hist.add_argument("--stats", help="Show stats for server")
    hist.add_argument("--clear", help="Clear history (server name or 'all')")
    hist.add_argument("--limit", "-l", type=int, default=20)

    dep = subparsers.add_parser("deploy", help="Deploy packages")
    dep.add_argument("--install", "-i", help="Package to install on all nodes")
    dep.add_argument("--check", "-c", help="Check if package installed")
    dep.add_argument("--script", "-s", help="Run script on node")
    dep.add_argument("--server", help="Target node for script")

    alrt = subparsers.add_parser("alerts", help="Manage alerts")
    alrt.add_argument("--add", "-a", help="Add rule: name,metric,threshold[,node]")
    alrt.add_argument("--remove", "-r", help="Remove rule by name")
    alrt.add_argument("--list-rules", action="store_true")
    alrt.add_argument("--check", action="store_true", help="Check all rules now")
    alrt.add_argument("--history", action="store_true")
    alrt.add_argument("--limit", "-l", type=int, default=50)

    grp = subparsers.add_parser("group", help="Manage device groups")
    grp_sub = grp.add_subparsers(dest="action")
    grp_sub.add_parser("list", help="List groups")
    cr_p = grp_sub.add_parser("create", help="Create group")
    cr_p.add_argument("--name", "-n", required=True)
    dl_p = grp_sub.add_parser("delete", help="Delete group")
    dl_p.add_argument("--name", "-n", required=True)
    ad_p = grp_sub.add_parser("add", help="Add device to group")
    ad_p.add_argument("--group", "-g", required=True)
    ad_p.add_argument("--device", "-d", required=True)
    rm_p2 = grp_sub.add_parser("remove", help="Remove device from group")
    rm_p2.add_argument("--group", "-g", required=True)
    rm_p2.add_argument("--device", "-d", required=True)
    rn_p = grp_sub.add_parser("run", help="Run command on group")
    rn_p.add_argument("--group", "-g", required=True)
    rn_p.add_argument("command")

    svc = subparsers.add_parser("service", help="Background service")
    svc_sub = svc.add_subparsers(dest="action")
    st_p = svc_sub.add_parser("start", help="Start service")
    st_p.add_argument("--interval", "-i", type=int, default=60)
    svc_sub.add_parser("stop", help="Stop service")
    svc_sub.add_parser("status", help="Service status")
    lg_p = svc_sub.add_parser("logs", help="Service logs")
    lg_p.add_argument("--limit", "-l", type=int, default=20)

    cmp = subparsers.add_parser("compare", help="Compare devices")
    cmp.add_argument("--devices", "-d", help="Comma-separated device names")

    cl = subparsers.add_parser("cmdlog", help="Command history")
    cl.add_argument("--search", "-s", help="Search commands")
    cl.add_argument("--clear", action="store_true", help="Clear log")
    cl.add_argument("--limit", "-l", type=int, default=20)

    subparsers.add_parser("interactive", help="Interactive TUI mode")

    node = subparsers.add_parser("node", help="Manage cloud nodes (via socket)")
    node_sub = node.add_subparsers(dest="action")
    na_p = node_sub.add_parser("add", help="Add a cloud node")
    na_p.add_argument("--name", "-n", required=True)
    na_p.add_argument("--host", "-H", required=True)
    na_p.add_argument("--port", "-p", type=int, default=9999)
    na_p.add_argument("--auth-key", "-k", required=True)
    nr_p = node_sub.add_parser("remove", help="Remove node")
    nr_p.add_argument("--name", "-n", required=True)
    node_sub.add_parser("list", help="List all nodes")
    nt_p = node_sub.add_parser("test", help="Test node connection")
    nt_p.add_argument("--name", "-n", required=True)
    ni_p = node_sub.add_parser("info", help="Node details")
    ni_p.add_argument("--name", "-n", required=True)
    nm_p = node_sub.add_parser("monitor", help="Monitor node resources")
    nm_p.add_argument("--name", "-n")
    ne_p = node_sub.add_parser("exec", help="Execute command on node")
    ne_p.add_argument("--name", "-n", required=True)
    ne_p.add_argument("command")
    ns_p = node_sub.add_parser("install", help="Install node on remote server")
    ns_p.add_argument("--host", "-H", required=True)
    ns_p.add_argument("--user", "-u", required=True)
    ns_p.add_argument("--key", "-k", help="SSH key path")
    node_sub.add_parser("dashboard", help="Show node dashboard")

    gpu_p = node_sub.add_parser("gpu", help="GPU status on nodes")
    gpu_p.add_argument("--name", "-n", help="Node name")

    job_p = node_sub.add_parser("job", help="Async jobs on nodes")
    job_sub = job_p.add_subparsers(dest="action")
    js_p = job_sub.add_parser("start", help="Start async job")
    js_p.add_argument("--name", "-n", required=True)
    js_p.add_argument("command")
    js_p.add_argument("--timeout", "-t", type=int, default=300)
    jc_p = job_sub.add_parser("status", help="Check job status")
    jc_p.add_argument("--name", "-n", required=True)
    jc_p.add_argument("--job-id", "-j", required=True)
    jl_p = job_sub.add_parser("list", help="List jobs")
    jl_p.add_argument("--name", "-n", required=True)
    jk_p = job_sub.add_parser("kill", help="Kill a job")
    jk_p.add_argument("--name", "-n", required=True)
    jk_p.add_argument("--job-id", "-j", required=True)

    sl_p = subparsers.add_parser("slice", help="Slice files across servers by resources")
    sl_p.add_argument("--files", "-f", required=True, help="Comma-separated file list")
    sl_p.add_argument("--servers", "-s", help="Comma-separated server list")
    sl_p.add_argument("--execute", "-e", help="Command template with {file} placeholder")

    as_p = subparsers.add_parser("autosync", help="Auto-sync local dir to server")
    as_p.add_argument("--local", "-l", required=True, help="Local directory")
    as_p.add_argument("--to-server", required=True, help="Target server")
    as_p.add_argument("--remote-to", help="Remote destination path")

    bkp = subparsers.add_parser("backup", help="Manage backups")
    bkp.add_argument("--restore", help="Restore from file")

    # === 20 NEW COMMANDS ===
    png = subparsers.add_parser("ping", help="Ping all servers/nodes")
    png.add_argument("--no-nodes", action="store_true", help="Skip nodes")

    upt = subparsers.add_parser("uptime", help="Show server uptime")
    upt.add_argument("--name", "-n")

    top_p = subparsers.add_parser("top", help="Top processes by CPU/RAM")
    top_p.add_argument("--name", "-n")
    top_p.add_argument("--limit", "-l", type=int, default=5)
    top_p.add_argument("--sort", "-s", choices=["cpu", "ram"], default="cpu")

    dsk = subparsers.add_parser("disk", help="Detailed disk usage")
    dsk.add_argument("--name", "-n")

    net = subparsers.add_parser("network", help="Network interfaces")
    net.add_argument("--name", "-n")

    who = subparsers.add_parser("who", help="Logged in users")
    who.add_argument("--name", "-n")

    find = subparsers.add_parser("find", help="Search files on server")
    find.add_argument("--name", "-n", required=True)
    find.add_argument("--path", "-p", default="/")
    find.add_argument("pattern")

    lgs = subparsers.add_parser("logs", help="Recent server logs")
    lgs.add_argument("--name", "-n", required=True)
    lgs.add_argument("--file", "-f", default="/var/log/syslog")
    lgs.add_argument("--lines", "-l", type=int, default=20)

    exp = subparsers.add_parser("export", help="Export config")
    exp.add_argument("--file", "-f", default="cloudmesh_config.json")

    imp = subparsers.add_parser("import", help="Import config")
    imp.add_argument("--file", "-f", required=True)

    enc = subparsers.add_parser("encrypt", help="Encrypt a file")
    enc.add_argument("file")

    dec = subparsers.add_parser("decrypt", help="Decrypt a file")
    dec.add_argument("file")
    dec.add_argument("--key", "-k", required=True)

    spd = subparsers.add_parser("speed", help="Network speed test")
    spd.add_argument("--name", "-n")
    spd.add_argument("--target", "-t", default="8.8.8.8")
    spd.add_argument("--count", "-c", type=int, default=3)

    scn = subparsers.add_parser("scan", help="Scan subnet for nodes")
    scn.add_argument("subnet")
    scn.add_argument("--port", "-p", type=int, default=9999)

    cln = subparsers.add_parser("cleanup", help="Cleanup old files")
    cln.add_argument("--days", "-d", type=int, default=7)

    rpt = subparsers.add_parser("report", help="Generate usage report")
    rpt.add_argument("--file", "-f")

    als = subparsers.add_parser("alias", help="Manage command aliases")
    als.add_argument("--name", "-n")
    als.add_argument("--cmd", help="Command to alias")
    als.add_argument("--list", "-l", action="store_true")
    als.add_argument("--remove", "-r")

    ver = subparsers.add_parser("version", help="Show version info")

    # === 10 ADVANCED KILLER FEATURES ===
    dsc = subparsers.add_parser("discover", help="Auto-discover nodes on network")
    dsc.add_argument("subnet", help="Subnet to scan (e.g. 192.168.1)")
    dsc.add_argument("--port", "-p", type=int, default=9999)
    dsc.add_argument("--timeout", "-t", type=float, default=0.3)

    bch = subparsers.add_parser("bench", help="Benchmark server performance")
    bch.add_argument("--server", "-s", help="Server to benchmark (local if omitted)")

    sch = subparsers.add_parser("schedule", help="Schedule recurring commands")
    sch_sub = sch.add_subparsers(dest="action")
    sa = sch_sub.add_parser("add", help="Add schedule")
    sa.add_argument("--name", "-n", required=True)
    sa.add_argument("sch_cmd")
    sa.add_argument("--interval", "-i", type=int, default=3600)
    sa.add_argument("--server", "-s")
    sr = sch_sub.add_parser("remove", help="Remove schedule")
    sr.add_argument("--name", "-n", required=True)
    sch_sub.add_parser("list", help="List schedules")
    st = sch_sub.add_parser("toggle", help="Toggle schedule")
    st.add_argument("--name", "-n", required=True)

    ntf = subparsers.add_parser("notify", help="Telegram/Discord notifications")
    ntf_sub = ntf.add_subparsers(dest="action")
    nt = ntf_sub.add_parser("setup-telegram", help="Setup Telegram bot")
    nt.add_argument("--token", required=True)
    nt.add_argument("--chat-id", required=True)
    nd = ntf_sub.add_parser("setup-discord", help="Setup Discord webhook")
    nd.add_argument("--webhook", required=True)
    ns = ntf_sub.add_parser("send", help="Send notification")
    ns.add_argument("message")
    ntf_sub.add_parser("status", help="Notification status")

    api_p = subparsers.add_parser("api", help="Start REST API server")
    api_p.add_argument("--port", "-p", type=int, default=8080)

    prf = subparsers.add_parser("profile", help="Config profiles")
    prf_sub = prf.add_subparsers(dest="action")
    prf_sub.add_parser("list", help="List profiles")
    ps = prf_sub.add_parser("save", help="Save current config")
    ps.add_argument("--name", "-n", required=True)
    pl = prf_sub.add_parser("load", help="Load profile")
    pl.add_argument("--name", "-n", required=True)
    pd = prf_sub.add_parser("delete", help="Delete profile")
    pd.add_argument("--name", "-n", required=True)

    aud = subparsers.add_parser("audit", help="Security audit on servers")
    aud.add_argument("--name", "-n")

    ssh_p = subparsers.add_parser("ssh", help="Quick SSH command")
    ssh_p.add_argument("--name", "-n")
    ssh_p.add_argument("--host", "-H")
    ssh_p.add_argument("--user", "-u", default="root")
    ssh_p.add_argument("--port", "-p", type=int, default=22)

    tpl = subparsers.add_parser("template", help="Command templates")
    tpl_sub = tpl.add_subparsers(dest="action")
    tpa = tpl_sub.add_parser("add", help="Add template")
    tpa.add_argument("--name", "-n", required=True)
    tpa.add_argument("tmpl_cmd")
    tpa.add_argument("--desc", "-d", default="")
    tpl_sub.add_parser("list", help="List templates")
    tpr = tpl_sub.add_parser("run", help="Run template")
    tpr.add_argument("--name", "-n", required=True)
    tpr.add_argument("--params", "-p", help="key=value,key=value")
    tprm = tpl_sub.add_parser("remove", help="Remove template")
    tprm.add_argument("--name", "-n", required=True)

    mp = subparsers.add_parser("map", help="Show network map")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    cmds = {
        "server": lambda: {
            "add": cmd_server_add, "remove": cmd_server_remove,
            "list": cmd_server_list, "test": cmd_server_test,
            "info": cmd_node_info,
        }.get(args.action, lambda: srv.print_help())(args),
        "node": lambda: {
            "add": cmd_node_add_cloud, "remove": cmd_node_remove,
            "list": cmd_node_list_cloud, "test": cmd_node_test,
            "info": cmd_node_info_cloud, "monitor": cmd_node_monitor,
            "exec": cmd_node_exec, "install": cmd_node_install,
            "dashboard": cmd_node_dashboard,
            "gpu": cmd_node_gpu, "job": cmd_node_job,
        }.get(args.action, lambda: node.print_help())(args),
        "monitor": lambda: cmd_monitor(args),
        "dashboard": lambda: cmd_dashboard(args),
        "run": lambda: cmd_run(args),
        "plan": lambda: cmd_plan(args),
        "transfer": lambda: cmd_transfer(args),
        "sync": lambda: cmd_sync(args),
        "history": lambda: cmd_history(args),
        "deploy": lambda: cmd_deploy(args),
        "alerts": lambda: cmd_alerts(args),
        "group": lambda: cmd_groups(args),
        "service": lambda: cmd_service(args),
        "compare": lambda: cmd_compare(args),
        "cmdlog": lambda: cmd_cmdlog(args),
        "slice": lambda: cmd_slice(args),
        "autosync": lambda: cmd_autosync(args),
        "interactive": lambda: cmd_interactive(args),
        "backup": lambda: cmd_backup(args),
        "ping": lambda: cmd_ping(args),
        "uptime": lambda: cmd_uptime(args),
        "top": lambda: cmd_top(args),
        "disk": lambda: cmd_disk(args),
        "network": lambda: cmd_network(args),
        "who": lambda: cmd_who(args),
        "find": lambda: cmd_find(args),
        "logs": lambda: cmd_logs(args),
        "export": lambda: cmd_export(args),
        "import": lambda: cmd_import(args),
        "encrypt": lambda: cmd_encrypt(args),
        "decrypt": lambda: cmd_decrypt(args),
        "speed": lambda: cmd_speed(args),
        "scan": lambda: cmd_scan(args),
        "cleanup": lambda: cmd_cleanup(args),
        "report": lambda: cmd_report(args),
        "alias": lambda: cmd_alias(args),
        "version": lambda: cmd_version(args),
        "discover": lambda: cmd_discover(args),
        "bench": lambda: cmd_bench(args),
        "schedule": lambda: cmd_schedule(args),
        "notify": lambda: cmd_notify(args),
        "api": lambda: cmd_api(args),
        "profile": lambda: cmd_profile(args),
        "audit": lambda: cmd_audit(args),
        "ssh": lambda: cmd_ssh(args),
        "template": lambda: cmd_template(args),
        "map": lambda: cmd_map(args),
    }
    handler = cmds.get(args.command)
    if handler:
        handler()


if __name__ == "__main__":
    main()
