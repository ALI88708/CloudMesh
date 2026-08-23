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
from core.panic import PanicManager, TripwireManager, ShamirPanicManager
from core.weather import WeatherForecast
from core.gossip import GossipManager
from core.checkpoint import CheckpointManager
from core.advanced import (
    discover_network, run_full_benchmark, ScheduleManager, NotifyManager,
    CloudMeshAPI, ProfileManager, audit_server, quick_ssh,
    TemplateManager, generate_network_map,
)

console = Console()

NODE_KEYS_FILE = Path(__file__).parent / ".node_keys.json"


def cmd_docker(args):
    from core.docker import DockerManager
    dm = DockerManager()
    if args.action == "list-servers":
        result = dm.list_servers()
    elif args.action == "containers":
        result = dm.list_containers(args.server)
    elif args.action == "compose":
        result = dm.docker_compose(args.path, args.server, args.action)
    elif args.action == "stats":
        result = dm.container_stats(args.server)
    elif args.action == "images":
        result = dm.list_images(args.server)
    elif args.action == "pull":
        result = dm.pull_image(args.image, args.server)
    elif args.action == "exec":
        result = dm.exec_command(args.container, args.cmd, args.server)
    elif args.action == "logs":
        result = dm.container_logs(args.container, args.server, args.lines)
    elif args.action == "cleanup":
        result = dm.cleanup(args.server)
    elif args.action == "prune":
        result = dm.prune(args.server)
    else:
        console.print("[red]Usage: cm docker <action>[/]")
        return
    console.print(result)


def cmd_firewall(args):
    from core.firewall import FirewallManager
    fm = FirewallManager()
    if args.action == "list-rules":
        rules = fm.list_rules(args.server if hasattr(args, "server") else None)
        if not rules:
            console.print("[yellow]No rules found[/]")
            return
        table = Table(title="Firewall Rules", box=box.ROUNDED)
        table.add_column("#", style="dim")
        table.add_column("Port", style="cyan")
        table.add_column("Protocol")
        table.add_column("Action", style="green")
        table.add_column("Source")
        for i, r in enumerate(rules, 1):
            table.add_row(str(i), str(r.get("port")), r.get("protocol", "tcp"), r.get("action", "allow"), r.get("source", "*"))
        console.print(table)
    elif args.action == "add-rule":
        result = fm.add_rule(args.port, args.proto, args.action, getattr(args, "server", None))
        console.print(f"[green]{result}[/]")
    elif args.action == "remove-rule":
        result = fm.remove_rule(args.port, args.proto, getattr(args, "server", None))
        console.print(f"[green]{result}[/]")
    elif args.action == "status":
        result = fm.status(getattr(args, "server", None))
        console.print(result)
    elif args.action == "check-port":
        result = fm.check_port(args.port, getattr(args, "server", None))
        console.print(result)
    elif args.action == "backup":
        result = fm.backup(getattr(args, "server", None), args.output)
        console.print(f"[green]{result}[/]")
    elif args.action == "load":
        result = fm.load_rules(args.file, getattr(args, "server", None))
        console.print(f"[green]{result}[/]")
    else:
        console.print("[red]Usage: cm firewall <action>[/]")


def cmd_ssl(args):
    from core.sslcheck import SSLChecker
    sc = SSLChecker()
    if args.action == "check":
        result = sc.check_domain(args.domain, args.port)
        if isinstance(result, dict):
            table = Table(title=f"SSL: {args.domain}", box=box.ROUNDED)
            table.add_column("Property", style="cyan")
            table.add_column("Value")
            for k, v in result.items():
                table.add_row(k, str(v))
            console.print(table)
        else:
            console.print(result)
    elif args.action == "check-all":
        results = sc.check_all()
        table = Table(title="SSL Check All", box=box.ROUNDED)
        table.add_column("Domain", style="cyan")
        table.add_column("Valid")
        table.add_column("Issuer")
        table.add_column("Expiry")
        table.add_column("Days Left")
        for r in results:
            days = r.get("days_left", "?")
            color = "green" if isinstance(days, int) and days > 30 else "red"
            table.add_row(r.get("domain"), str(r.get("valid")), r.get("issuer", "?"), r.get("expiry", "?"), f"[{color}]{days}[/]")
        console.print(table)
    elif args.action == "domains":
        domains = sc.list_domains()
        if not domains:
            console.print("[yellow]No domains configured[/]")
            return
        for d in domains:
            console.print(f"  - {d}")
    elif args.action == "add":
        result = sc.add_domain(args.domain, args.port)
        console.print(f"[green]{result}[/]")
    elif args.action == "remove":
        result = sc.remove_domain(args.domain)
        console.print(f"[green]{result}[/]")
    elif args.action == "history":
        history = sc.history()
        table = Table(title="SSL History", box=box.ROUNDED)
        table.add_column("Domain", style="cyan")
        table.add_column("Check Time")
        table.add_column("Valid")
        table.add_column("Days Left")
        for h in history[-20:]:
            table.add_row(h.get("domain"), h.get("time"), str(h.get("valid")), str(h.get("days_left")))
        console.print(table)
    elif args.action == "renew-check":
        result = sc.renew_check()
        console.print(result)
    else:
        console.print("[red]Usage: cm ssl <action>[/]")


def cmd_logagg(args):
    from core.logagg import LogAggregator
    la = LogAggregator()
    if args.action == "add-source":
        result = la.add_source(args.server, args.path, args.tag)
        console.print(f"[green]{result}[/]")
    elif args.action == "sources":
        sources = la.list_sources()
        if not sources:
            console.print("[yellow]No sources configured[/]")
            return
        table = Table(title="Log Sources", box=box.ROUNDED)
        table.add_column("Tag", style="cyan")
        table.add_column("Server")
        table.add_column("Path")
        for s in sources:
            table.add_row(s.get("tag", ""), s.get("server", "local"), s.get("path", ""))
        console.print(table)
    elif args.action == "search":
        results = la.search(args.pattern, args.source, args.since, args.limit)
        if not results:
            console.print("[yellow]No matching logs[/]")
            return
        for r in results:
            console.print(f"[dim]{r.get('time', '')}[/] [{r.get('level', 'info')}]{r.get('message', '')}[/]")
    elif args.action == "filter":
        results = la.filter_logs(args.source, args.level, args.since, args.limit)
        if not results:
            console.print("[yellow]No matching logs[/]")
            return
        for r in results:
            console.print(f"[dim]{r.get('time', '')}[/] [{r.get('level', 'info')}]{r.get('message', '')}[/]")
    elif args.action == "subscribe":
        la.subscribe(args.source, args.filter, args.interval)
    elif args.action == "stats":
        result = la.stats()
        console.print(result)
    elif args.action == "clear":
        result = la.clear(args.source)
        console.print(f"[green]{result}[/]")
    else:
        console.print("[red]Usage: cm logagg <action>[/]")


def cmd_reshistory(args):
    from core.reshistory import snapshot, show_history, summary, clear_history
    if args.action == "snapshot":
        result = snapshot()
        console.print(f"[green]{result}[/]")
    elif args.action == "show":
        entries = show_history(args.server, getattr(args, "metric", None), args.limit)
        if isinstance(entries, str):
            console.print(f"[yellow]{entries}[/]")
            return
        table = Table(title=f"History: {args.server}", box=box.ROUNDED)
        table.add_column("Time", style="dim")
        table.add_column("CPU %", style="cyan")
        table.add_column("RAM %", style="green")
        table.add_column("Disk %", style="yellow")
        for e in entries:
            table.add_row(e.get("time", ""), f"{e.get('cpu', 0):.1f}", f"{e.get('ram', 0):.1f}", f"{e.get('disk', 0)}%")
        console.print(table)
    elif args.action == "summary":
        result = summary(args.server)
        if isinstance(result, dict) and "error" in result:
            console.print(f"[yellow]{result['error']}[/]")
            return
        table = Table(title=f"Summary: {args.server}", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Min")
        table.add_column("Max")
        table.add_column("Avg/Latest")
        for m in ["cpu", "ram", "disk"]:
            if m in result:
                d = result[m]
                table.add_row(m.upper(), f"{d.get('min', 0):.1f}", f"{d.get('max', 0):.1f}", f"{d.get('avg', d.get('latest', 0)):.1f}")
        console.print(table)
    elif args.action == "clear":
        result = clear_history(getattr(args, "server", None))
        console.print(f"[green]{result}[/]")
    else:
        console.print("[red]Usage: cm reshistory <action>[/]")


def cmd_plugins(args):
    from core.plugins import list_plugins, add_plugin, remove_plugin, run_plugin, import_plugin, export_plugin
    if args.action == "list":
        plugins = list_plugins()
        if not plugins:
            console.print("[yellow]No plugins installed[/]")
            return
        table = Table(title="Plugins", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Description")
        table.add_column("Command")
        table.add_column("Targets")
        for p in plugins:
            table.add_row(p.get("name"), p.get("description", ""), p.get("command", "")[:50], p.get("targets", "all"))
        console.print(table)
    elif args.action == "add":
        result = add_plugin(args.name, args.command, getattr(args, "desc", ""), getattr(args, "targets", "all"))
        console.print(f"[green]{result}[/]")
    elif args.action == "remove":
        result = remove_plugin(args.name)
        console.print(f"[green]{result}[/]")
    elif args.action == "run":
        result = run_plugin(args.name, getattr(args, "server", None))
        if isinstance(result, dict):
            for s, o in result.items():
                console.print(f"[cyan]{s}:[/] {o}")
        else:
            console.print(result)
    elif args.action == "import":
        result = import_plugin(args.file)
        console.print(f"[green]{result}[/]")
    elif args.action == "export":
        if not hasattr(args, "output") or not args.output:
            args.output = f"{args.name}_plugin.json"
        result = export_plugin(args.name, args.output)
        console.print(f"[green]{result}[/]")
    else:
        console.print("[red]Usage: cm plugins <action>[/]")


def cmd_acl(args):
    from core.acl import list_users, add_user, remove_user, set_role, enable_user, disable_user, list_roles, add_role, remove_role
    if args.action == "users":
        users = list_users()
        if not users:
            console.print("[yellow]No users configured[/]")
            return
        table = Table(title="Users", box=box.ROUNDED)
        table.add_column("Username", style="cyan")
        table.add_column("Role")
        table.add_column("Enabled")
        table.add_column("Created")
        for u in users:
            color = "green" if u.get("enabled") else "red"
            table.add_row(u.get("username"), u.get("role"), f"[{color}]{'Yes' if u.get('enabled') else 'No'}[/]", u.get("created", ""))
        console.print(table)
    elif args.action == "add-user":
        result = add_user(args.username, args.password, args.role)
        console.print(f"[green]{result}[/]")
    elif args.action == "remove-user":
        result = remove_user(args.username)
        console.print(f"[green]{result}[/]")
    elif args.action == "set-role":
        result = set_role(args.username, args.role)
        console.print(f"[green]{result}[/]")
    elif args.action == "enable":
        result = enable_user(args.username)
        console.print(f"[green]{result}[/]")
    elif args.action == "disable":
        result = disable_user(args.username)
        console.print(f"[green]{result}[/]")
    elif args.action == "roles":
        roles = list_roles()
        table = Table(title="Roles", box=box.ROUNDED)
        table.add_column("Role", style="cyan")
        table.add_column("Permissions")
        for role, perms in roles.items():
            table.add_row(role, ", ".join(perms))
        console.print(table)
    elif args.action == "add-role":
        perms = [p.strip() for p in args.perms.split(",")]
        result = add_role(args.name, perms)
        console.print(f"[green]{result}[/]")
    elif args.action == "remove-role":
        result = remove_role(args.name)
        console.print(f"[green]{result}[/]")
    else:
        console.print("[red]Usage: cm acl <action>[/]")


def cmd_webhooks(args):
    from core.webhooks import list_webhooks, add_webhook, remove_webhook, send_webhook, test_webhook, webhook_log, enable_webhook, disable_webhook
    if args.action == "list":
        whs = list_webhooks()
        if not whs:
            console.print("[yellow]No webhooks configured[/]")
            return
        table = Table(title="Webhooks", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("URL")
        table.add_column("Events")
        table.add_column("Enabled")
        for w in whs:
            color = "green" if w.get("enabled") else "red"
            table.add_row(w.get("name"), w.get("type"), w.get("url", "")[:40], ",".join(w.get("events", [])), f"[{color}]{'Yes' if w.get('enabled') else 'No'}[/]")
        console.print(table)
    elif args.action == "add":
        events = [e.strip() for e in args.events.split(",")]
        result = add_webhook(args.name, args.url, args.type, events)
        console.print(f"[green]{result}[/]")
    elif args.action == "remove":
        result = remove_webhook(args.name)
        console.print(f"[green]{result}[/]")
    elif args.action == "test":
        results = test_webhook(args.name)
        for r in results:
            console.print(f"  {r.get('webhook')}: {r.get('status')}")
    elif args.action == "log":
        logs = webhook_log()
        if not logs:
            console.print("[yellow]No webhook log[/]")
            return
        for l in logs:
            console.print(f"[dim]{l.get('time', '')}[/] {l.get('webhook', '')} [{l.get('event', '')}] {l.get('message', '')}")
    elif args.action == "send":
        results = send_webhook(args.message, args.event)
        for r in results:
            console.print(f"  {r.get('webhook')}: {r.get('status')}")
    elif args.action == "enable-all":
        whs = list_webhooks()
        for w in whs:
            enable_webhook(w["name"])
        console.print(f"[green]Enabled {len(whs)} webhooks[/]")
    elif args.action == "disable-all":
        whs = list_webhooks()
        for w in whs:
            disable_webhook(w["name"])
        console.print(f"[green]Disabled {len(whs)} webhooks[/]")
    else:
        console.print("[red]Usage: cm webhooks <action>[/]")


def cmd_watcher(args):
    from core.watcher import add_watcher, remove_watcher, list_watchers, check_process, check_all_watchers, watcher_alerts
    if args.action == "list":
        watchers = list_watchers()
        if not watchers:
            console.print("[yellow]No watchers configured[/]")
            return
        table = Table(title="Process Watchers", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Process")
        table.add_column("Server")
        table.add_column("Alert On")
        table.add_column("Enabled")
        for w in watchers:
            color = "green" if w.get("enabled") else "red"
            table.add_row(w.get("name"), w.get("process", ""), w.get("server", "all"), w.get("alert_on", "stop"), f"[{color}]{'Yes' if w.get('enabled') else 'No'}[/]")
        console.print(table)
    elif args.action == "add":
        result = add_watcher(args.name, args.process, getattr(args, "server", None), args.alert_on)
        console.print(f"[green]{result}[/]")
    elif args.action == "remove":
        result = remove_watcher(args.name)
        console.print(f"[green]{result}[/]")
    elif args.action == "check":
        results = check_all_watchers()
        table = Table(title="Watcher Status", box=box.ROUNDED)
        table.add_column("Watcher", style="cyan")
        table.add_column("Triggered")
        for r in results:
            color = "red" if r.get("triggered") else "green"
            table.add_row(r.get("watcher", ""), f"[{color}]{'YES' if r.get('triggered') else 'No'}[/]")
        console.print(table)
    elif args.action == "check-status":
        result = check_process(args.server, args.process)
        color = "green" if result.get("running") else "red"
        console.print(f"  {result.get('process')}: [{color}]{'Running' if result.get('running') else 'Stopped'}[/] ({result.get('instances', 0)} instances)")
    elif args.action == "alerts":
        alerts = watcher_alerts()
        if not alerts:
            console.print("[yellow]No alerts[/]")
            return
        for a in alerts:
            console.print(f"[dim]{a.get('time', '')}[/] [red]{a.get('alert', '')}[/]")
    else:
        console.print("[red]Usage: cm watcher <action>[/]")



def cmd_tunnel(args):
    from core.tunnels import list_tunnels, add_tunnel, remove_tunnel, start_tunnel, stop_tunnel, stop_all_tunnels, tunnel_status, quick_tunnel
    if args.action == "list":
        tunnels = list_tunnels()
        if not tunnels:
            console.print("[yellow]No tunnels configured[/]")
            return
        table = Table(title="SSH Tunnels", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Host")
        table.add_column("Local Port")
        table.add_column("Remote")
        table.add_column("Created")
        for t in tunnels:
            table.add_row(t.get("name"), t.get("host", ""), str(t.get("local_port", "")), f"{t.get('remote_host', '')}:{t.get('remote_port', '')}", t.get("created", ""))
        console.print(table)
    elif args.action == "add":
        result = add_tunnel(args.name, args.host, args.user, args.local_port, args.remote_host, args.remote_port, getattr(args, "key", None))
        console.print(f"[green]{result}[/]")
    elif args.action == "remove":
        result = remove_tunnel(args.name)
        console.print(f"[green]{result}[/]")
    elif args.action == "start":
        result = start_tunnel(args.name)
        console.print(f"[green]{result}[/]")
    elif args.action == "stop":
        result = stop_tunnel(args.name)
        console.print(f"[green]{result}[/]")
    elif args.action == "stop-all":
        result = stop_all_tunnels()
        console.print(f"[green]{result}[/]")
    elif args.action == "status":
        status = tunnel_status()
        console.print(f"Total: {status.get('total', 0)} | Active: {len(status.get('active', []))} | Inactive: {len(status.get('inactive', []))}")
        for a in status.get("active", []):
            console.print(f"  [green]ACTIVE[/] {a.get('name')} (started {a.get('started', '')})")
    elif args.action == "quick":
        result = quick_tunnel(args.host, args.user, args.local_port, args.remote_port, getattr(args, "key", None))
        console.print(f"[green]{result}[/]")
    else:
        console.print("[red]Usage: cm tunnel <action>[/]")


def cmd_database(args):
    from core.database import list_databases, db_status, db_query, db_backup, db_check_all
    kw = {"db_type": getattr(args, "type", "mysql"), "host": getattr(args, "host", "127.0.0.1"), "port": getattr(args, "port", None), "user": getattr(args, "user", "root"), "password": getattr(args, "password", "")}
    if args.action == "list":
        result = list_databases(args.server, **kw)
        console.print(result)
    elif args.action == "status":
        result = db_status(args.server, **kw)
        console.print(result)
    elif args.action == "query":
        result = db_query(args.server, args.sql, **kw)
        console.print(result)
    elif args.action == "backup":
        result = db_backup(args.server, args.database, args.path, **kw)
        console.print(f"[green]{result}[/]")
    else:
        console.print("[red]Usage: cm database <action>[/]")


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
    if args.verify:
        result = cmd_log.verify()
        if result["valid"]:
            console.print(f"[green]{result['message']}[/]")
        else:
            console.print(f"[red bold]{result['message']}[/]")
            if "entry" in result:
                entry = result["entry"]
                console.print(f"  Entry #{result['broken_at']}: {entry.get('command', '?')} at {entry.get('timestamp', '?')}")
        return
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


def cmd_doctor(args):
    console.print(Panel("[bold bright_blue]CloudMesh Doctor — Security & Health Check[/]", border_style="bright_blue"))
    checks = []

    api_src = Path(__file__).parent / "core" / "advanced.py"
    if api_src.exists():
        content = api_src.read_text()
        api_ok = "compare_digest" in content
        bind_ok = '"127.0.0.1"' in content
        ddos_ok = "DDoSProtection" in content
        checks.append(("API: hmac.compare_digest", api_ok, "Uses timing-safe comparison"))
        checks.append(("API: localhost binding", bind_ok, "Bound to 127.0.0.1"))
        checks.append(("API: DDoS protection", ddos_ok, "Rate limiting enabled"))
    else:
        checks.append(("API source", False, "advanced.py not found"))

    node_src = Path(__file__).parent / "node" / "cloudmesh_node.py"
    if node_src.exists():
        ncontent = node_src.read_text()
        auth_ok = "compare_digest" in ncontent
        path_ok = "relative_to" in ncontent and "realpath" in ncontent
        ddos_node = "DDoSProtection" in ncontent
        spa_ok = "spa_mode" in ncontent
        checks.append(("Node: hmac.compare_digest", auth_ok, "Uses timing-safe comparison"))
        checks.append(("Node: path traversal guard", path_ok, "Validates paths with realpath+relative_to"))
        checks.append(("Node: DDoS protection", ddos_node, "Anti-DDoS enabled"))
        checks.append(("Node: SPA support", spa_ok, "Single Packet Authorization"))
    else:
        checks.append(("Node source", False, "cloudmesh_node.py not found"))

    ddos_src = Path(__file__).parent / "core" / "ddos.py"
    checks.append(("DDoS module", ddos_src.exists(), "core/ddos.py present"))

    ssh_src = Path(__file__).parent / "core" / "ssh_util.py"
    if ssh_src.exists():
        sc = ssh_src.read_text()
        checks.append(("SSH: centralized", "MITMWarning" in sc, "MITM warnings enabled"))
    else:
        checks.append(("SSH: centralized", False, "ssh_util.py not found"))

    fw_src = Path(__file__).parent / "core" / "firewall.py"
    if fw_src.exists():
        fc = fw_src.read_text()
        checks.append(("Firewall: allowlist", "ALLOWED_RULES" in fc, "Rule validation enabled"))
    else:
        checks.append(("Firewall", False, "firewall.py not found"))

    db_src = Path(__file__).parent / "core" / "database.py"
    if db_src.exists():
        dc = db_src.read_text()
        checks.append(("Database: temp config", "/tmp/" in dc, "Passwords via temp files"))
    else:
        checks.append(("Database", False, "database.py not found"))

    tests_dir = Path(__file__).parent / "tests"
    has_tests = (tests_dir / "test_security.py").exists()
    checks.append(("Test suite", has_tests, "tests/test_security.py exists"))

    secret_key = Path(__file__).parent / ".secret.key"
    if secret_key.exists():
        key_size = secret_key.stat().st_size
        checks.append(("Encryption key", key_size > 10, f"Key file present ({key_size} bytes)"))
    else:
        checks.append(("Encryption key", False, ".secret.key missing"))

    node_keys = Path(__file__).parent / ".node_keys.json"
    if node_keys.exists():
        try:
            nk = json.loads(node_keys.read_text())
            checks.append(("Cloud nodes", len(nk) > 0, f"{len(nk)} node(s) configured"))
        except Exception:
            checks.append(("Cloud nodes", False, "Corrupt .node_keys.json"))
    else:
        checks.append(("Cloud nodes", False, "No nodes configured"))

    sched = Path(__file__).parent / ".schedule.json"
    if sched.exists():
        try:
            s = json.loads(sched.read_text())
            active = sum(1 for v in s.values() if v.get("enabled"))
            checks.append(("Schedules", True, f"{active} active schedule(s)"))
        except Exception:
            checks.append(("Schedules", False, "Corrupt schedule file"))
    else:
        checks.append(("Schedules", True, "No schedules"))

    table = Table(box=box.ROUNDED)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details", style="dim")
    all_ok = True
    for label, ok, detail in checks:
        status = "[green]PASS[/]" if ok else "[red]FAIL[/]"
        table.add_row(label, status, detail)
        if not ok:
            all_ok = False
    console.print(table)
    console.print()
    if all_ok:
        console.print("[green bold]All checks passed![/]")
    else:
        console.print("[yellow]Some checks failed — review above[/]")


def cmd_update(args):
    import subprocess
    import shutil

    repo_dir = Path(__file__).parent.parent
    if not (repo_dir / ".git").exists():
        console.print("[red]Not a git repository. Cannot self-update.[/]")
        return

    console.print("[cyan]Checking for updates...[/]")
    try:
        result = subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=str(repo_dir), capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            console.print(f"[red]Fetch failed: {result.stderr.strip()}[/]")
            return

        behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=str(repo_dir), capture_output=True, text=True, timeout=10
        )
        behind_count = int(behind.stdout.strip()) if behind.returncode == 0 else 0

        if behind_count == 0:
            console.print("[green]Already up to date![/]")
            return

        console.print(f"[yellow]Found {behind_count} new commit(s)[/]")

        if not args.yes:
            from rich.prompt import Confirm
            if not Confirm.ask("Pull and install?", default=True):
                console.print("[dim]Update cancelled[/]")
                return

        console.print("[cyan]Pulling latest changes...[/]")
        pull = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=str(repo_dir), capture_output=True, text=True, timeout=30
        )
        if pull.returncode != 0:
            console.print(f"[red]Pull failed: {pull.stderr.strip()}[/]")
            return

        console.print("[cyan]Reinstalling dependencies...[/]")
        req = repo_dir / "cloudmesh" / "requirements.txt"
        if req.exists():
            pip = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
                capture_output=True, text=True, timeout=120
            )
            if pip.returncode != 0:
                console.print(f"[yellow]pip install warning: {pip.stderr.strip()[:200]}[/]")

        new_ver = "unknown"
        vf = repo_dir / "cloudmesh" / "core" / "features.py"
        if vf.exists():
            for line in vf.read_text().splitlines():
                if '"version"' in line and ':' in line:
                    new_ver = line.split('"version"')[1].split('"')[1]
                    break

        console.print(f"[green bold]Updated to CloudMesh v{new_ver}[/]")
    except subprocess.TimeoutExpired:
        console.print("[red]Network timeout — try again later[/]")
    except Exception as e:
        console.print(f"[red]Update failed: {e}[/]")


def cmd_status(args):
    mgr = ServerManager()
    servers = mgr.list_servers()
    if not servers:
        if getattr(args, "as_json", False):
            console.print("{}")
        else:
            console.print("[dim]No servers configured. Use `cm server add` to add one.[/]")
        return

    results = {}
    table = Table(title="CloudMesh Status", box=box.ROUNDED)
    table.add_column("Name", style="bold")
    table.add_column("Host")
    table.add_column("Status")
    table.add_column("CPU")
    table.add_column("RAM")
    table.add_column("Disk")

    for name, info in servers.items():
        host = info.get("host", "?")
        entry = {"host": host, "status": "offline", "cpu": None, "ram": None, "disk": None}
        try:
            client = NodeClient(host, info.get("port", 9999), info.get("auth_key", ""))
            pong = client.send({"action": "ping"})
            if pong and pong.get("type") == "pong":
                metrics = client.send({"action": "metrics"})
                if metrics and metrics.get("type") == "metrics":
                    m = metrics["data"]
                    cpu = f"{m.get('cpu_percent', 0):.0f}%"
                    ram = f"{m.get('ram_percent', 0):.0f}%"
                    disk = f"{m.get('disk_percent', 0):.0f}%"
                    entry["status"] = "online"
                    entry["cpu"] = m.get("cpu_percent", 0)
                    entry["ram"] = m.get("ram_percent", 0)
                    entry["disk"] = m.get("disk_percent", 0)
                    table.add_row(name, host, "[green]ONLINE[/]", cpu, ram, disk)
                else:
                    entry["status"] = "online"
                    table.add_row(name, host, "[green]ONLINE[/]", "-", "-", "-")
            else:
                entry["status"] = "unreachable"
                table.add_row(name, host, "[red]UNREACHABLE[/]", "-", "-", "-")
        except Exception:
            table.add_row(name, host, "[red]OFFLINE[/]", "-", "-", "-")
        results[name] = entry

    if getattr(args, "as_json", False):
        console.print(json.dumps(results, indent=2))
    else:
        console.print(table)
        online = sum(1 for v in results.values() if v["status"] == "online")
        console.print(f"\n[dim]{online}/{len(results)} server(s) online[/]")


def cmd_exec(args):
    keys = _load_node_keys()
    command = args.command

    if args.all_nodes:
        names = list(keys.keys())
    elif args.nodes:
        names = [n.strip() for n in args.nodes.split(",")]
    elif args.name:
        names = [args.name]
    else:
        console.print("[red]Specify --name, --nodes, or --all[/]")
        return

    if not names:
        console.print("[dim]No nodes configured.[/]")
        return

    console.print(f"[cyan]Executing on {len(names)} node(s): {command}[/]")

    import concurrent.futures
    results = {}

    def run_on_node(n):
        if n not in keys:
            return n, {"success": False, "error": "Node not found"}
        info = keys[n]
        client = NodeClient(info["host"], info["port"], info["key"])
        result = client.execute(command)
        return n, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(names), 10)) as pool:
        futures = {pool.submit(run_on_node, n): n for n in names}
        for future in concurrent.futures.as_completed(futures):
            name, result = future.result()
            results[name] = result

    if getattr(args, "as_json", False):
        console.print(json.dumps(results, indent=2))
        return

    table = Table(title="Execution Results", box=box.ROUNDED)
    table.add_column("Node", style="bold")
    table.add_column("Status")
    table.add_column("Exit Code")
    table.add_column("Output")
    for name, res in results.items():
        if res.get("success"):
            table.add_row(name, "[green]OK[/]", str(res.get("exit_code", 0)), (res.get("stdout", "") or "")[:80])
        else:
            table.add_row(name, "[red]FAIL[/]", "-", (res.get("error", res.get("stderr", "")) or "")[:80])
    console.print(table)
    ok = sum(1 for r in results.values() if r.get("success"))
    console.print(f"\n[dim]{ok}/{len(results)} succeeded[/]")


def cmd_watch(args):
    import time
    import subprocess as _sp

    interval = args.interval
    keys = _load_node_keys()
    security, server_mgr, monitor, *_ = init_components()

    console.print(f"[cyan]Watching every {interval}s — Press Ctrl+C to stop[/]\n")

    try:
        while True:
            _sp.run(["cls" if sys.platform == "win32" else "clear"], shell=False)
            now = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            console.print(Panel(f"[bold]CloudMesh Watch[/] — {now}", border_style="bright_blue"))

            names_ssh = server_mgr.list_servers()
            names_node = list(keys.keys())

            if names_ssh:
                table = Table(title="SSH Servers", box=box.SIMPLE_HEAVY)
                table.add_column("Name", style="bold", min_width=15)
                table.add_column("CPU", justify="right")
                table.add_column("RAM", justify="right")
                table.add_column("Disk", justify="right")
                table.add_column("Weight", justify="right")
                for name in names_ssh:
                    try:
                        m = monitor.get_all_metrics(name)
                        if m:
                            cpu = m.get("cpu_percent", 0)
                            ram = (m.get("ram") or {}).get("percent", 0)
                            disk = (m.get("disk") or {}).get("percent", 0)
                            w = monitor.calculate_weight(m)
                            cc = "red" if cpu > 80 else "yellow" if cpu > 50 else "green"
                            rc = "red" if ram > 80 else "yellow" if ram > 50 else "green"
                            dc = "red" if disk > 80 else "yellow" if disk > 50 else "green"
                            table.add_row(name, f"[{cc}]{cpu}%[/]", f"[{rc}]{ram}%[/]", f"[{dc}]{disk}%[/]", str(w))
                        else:
                            table.add_row(name, "[red]?[/]", "[red]?[/]", "[red]?[/]", "?")
                    except Exception:
                        table.add_row(name, "[red]ERR[/]", "-", "-", "-")
                console.print(table)

            if names_node:
                table = Table(title="Cloud Nodes", box=box.SIMPLE_HEAVY)
                table.add_column("Name", style="bold", min_width=15)
                table.add_column("CPU", justify="right")
                table.add_column("RAM", justify="right")
                table.add_column("Disk", justify="right")
                table.add_column("Status")
                for name in names_node:
                    info = keys[name]
                    try:
                        client = NodeClient(info["host"], info["port"], info["key"])
                        metrics = client.get_metrics()
                        if metrics:
                            cpu = metrics.get("cpu_percent", 0)
                            ram = (metrics.get("ram") or {}).get("percent", 0)
                            disk = (metrics.get("disk") or {}).get("percent", 0)
                            cc = "red" if cpu > 80 else "yellow" if cpu > 50 else "green"
                            rc = "red" if ram > 80 else "yellow" if ram > 50 else "green"
                            dc = "red" if disk > 80 else "yellow" if disk > 50 else "green"
                            table.add_row(name, f"[{cc}]{cpu}%[/]", f"[{rc}]{ram}%[/]", f"[{dc}]{disk}%[/]", "[green]ON[/]")
                        else:
                            table.add_row(name, "-", "-", "-", "[yellow]?[/]")
                    except Exception:
                        table.add_row(name, "-", "-", "-", "[red]OFF[/]")
                console.print(table)

            total = len(names_ssh) + len(names_node)
            console.print(f"\n[dim]{total} server(s) | Refreshing in {interval}s | Ctrl+C to stop[/]")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped[/]")


def cmd_keys(args):
    home = Path.home()
    ssh_dir = home / ".ssh"
    keys_file = Path(__file__).parent / ".ssh_keys.json"

    def load_keys():
        if keys_file.exists():
            try:
                return json.loads(keys_file.read_text())
            except Exception:
                return {}
        return {}

    def save_keys(data):
        keys_file.write_text(json.dumps(data, indent=2))

    if args.action == "generate":
        key_name = args.name or "cloudmesh_key"
        key_path = ssh_dir / key_name
        if key_path.exists() and not args.force:
            console.print(f"[red]Key {key_path} already exists. Use --force to overwrite.[/]")
            return
        ssh_dir.mkdir(exist_ok=True)
        bits = args.bits or 4096
        console.print(f"[cyan]Generating {bits}-bit SSH key: {key_path}[/]")
        result = __import__("subprocess").run(
            ["ssh-keygen", "-t", "ed25519" if bits == 256 else "rsa", "-b", str(bits),
             "-f", str(key_path), "-N", args.passphrase or "", "-C", f"cloudmesh@{key_name}"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            saved = load_keys()
            saved[key_name] = {"path": str(key_path), "pub": str(key_path) + ".pub", "bits": bits, "created": __import__("datetime").datetime.now().isoformat()}
            save_keys(saved)
            console.print(f"[green]Key generated: {key_path}[/]")
            console.print(f"[green]Public key: {key_path}.pub[/]")
        else:
            console.print(f"[red]Key generation failed: {result.stderr}[/]")

    elif args.action == "list":
        saved = load_keys()
        ssh_dir = home / ".ssh"
        all_keys = []
        if ssh_dir.exists():
            for f in ssh_dir.iterdir():
                if f.suffix == "" and not f.name.endswith(".pub") and f.name not in (".", ".."):
                    try:
                        result = __import__("subprocess").run(
                            ["ssh-keygen", "-l", "-f", str(f)],
                            capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            all_keys.append({"path": str(f), "info": result.stdout.strip()})
                    except Exception:
                        pass
        if saved:
            for name, info in saved.items():
                all_keys.append({"path": info.get("path", "?"), "info": f"[managed: {name}] bits={info.get('bits', '?')}"})

        if not all_keys:
            console.print("[dim]No SSH keys found in ~/.ssh[/]")
            return
        table = Table(title="SSH Keys", box=box.ROUNDED)
        table.add_column("Path", style="bold")
        table.add_column("Info")
        for k in all_keys:
            console.print(f"  {k['path']}: {k['info']}")
        console.print(f"\n[dim]{len(all_keys)} key(s) found[/]")

    elif args.action == "show":
        pub_path = Path(args.pub_file)
        if not pub_path.exists():
            console.print(f"[red]File not found: {pub_path}[/]")
            return
        content = pub_path.read_text().strip()
        console.print(Panel(content, title=f"Public Key: {pub_path.name}", border_style="cyan"))

    elif args.action == "deploy":
        _, server_mgr, *_ = init_components()
        pub_path = Path(args.pub_file)
        if not pub_path.exists():
            console.print(f"[red]Public key not found: {pub_path}[/]")
            return
        pub_content = pub_path.read_text().strip()
        names = [args.server] if args.server else server_mgr.list_servers()
        if not names:
            console.print("[dim]No servers configured[/]")
            return
        console.print(f"[cyan]Deploying key to {len(names)} server(s)...[/]")
        for name in names:
            try:
                result = server_mgr.execute(name, f"mkdir -p ~/.ssh && echo '{pub_content}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys")
                if result.get("exit_code") == 0:
                    console.print(f"  [green]{name}: Deployed[/]")
                else:
                    console.print(f"  [red]{name}: Failed — {result.get('stderr', '')[:80]}[/]")
            except Exception as e:
                console.print(f"  [red]{name}: Error — {e}[/]")

    elif args.action == "remove-managed":
        name = args.name
        saved = load_keys()
        if name not in saved:
            console.print(f"[red]Managed key '{name}' not found[/]")
            return
        del saved[name]
        save_keys(saved)
        console.print(f"[green]Removed '{name}' from managed keys[/]")

    else:
        console.print("[dim]Use: cm keys generate|list|show|deploy|remove-managed[/]")


def cmd_config(args):
    config_dir = Path(__file__).parent
    config_files = {
        "servers": config_dir / "data" / "servers.json",
        "node_keys": config_dir / ".node_keys.json",
        "secret_key": config_dir / ".secret.key",
        "groups": config_dir / "data" / "groups.json",
        "aliases": config_dir / ".aliases.json",
        "templates": config_dir / ".templates.json",
        "profiles": config_dir / ".profiles",
        "schedule": config_dir / ".schedule.json",
        "webhooks": config_dir / "data" / "webhooks.json",
        "watchers": config_dir / "data" / "watchers.json",
        "tunnels": config_dir / "data" / "tunnels.json",
        "ssl_domains": config_dir / "data" / "ssl_domains.json",
        "log_sources": config_dir / "data" / "log_sources.json",
        "plugins": config_dir / "data" / "plugins.json",
        "acl": config_dir / "data" / "acl.json",
        "alerts": config_dir / "alerts.json",
    }

    if args.action == "list":
        table = Table(title="Config Files", box=box.ROUNDED)
        table.add_column("Name", style="bold")
        table.add_column("Path")
        table.add_column("Size")
        table.add_column("Modified")
        for name, path in config_files.items():
            if path.exists():
                size = path.stat().st_size
                mtime = __import__("datetime").datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                table.add_row(name, str(path), f"{size} B", mtime)
            else:
                table.add_row(name, str(path), "[dim]missing[/]", "-")
        console.print(table)

    elif args.action == "export":
        import shutil as _sh
        out_dir = Path(args.output) if args.output else Path(f"cloudmesh_backup_{__import__('time').strftime('%Y%m%d_%H%M%S')}")
        out_dir.mkdir(parents=True, exist_ok=True)
        exported = 0
        for name, path in config_files.items():
            if path.exists():
                if path.is_file():
                    _sh.copy2(str(path), str(out_dir / path.name))
                    exported += 1
                elif path.is_dir():
                    _sh.copytree(str(path), str(out_dir / path.name), dirs_exist_ok=True)
                    exported += 1
        console.print(f"[green]Exported {exported} config file(s) to {out_dir}[/]")

    elif args.action == "import":
        import shutil as _sh
        src_dir = Path(args.source)
        if not src_dir.exists():
            console.print(f"[red]Source directory not found: {src_dir}[/]")
            return
        imported = 0
        for f in src_dir.iterdir():
            for name, path in config_files.items():
                if f.name == path.name or f.name == path.name.replace(".json", ""):
                    if path.is_file():
                        _sh.copy2(str(f), str(path))
                        imported += 1
                        console.print(f"  [green]Restored {name}[/]")
                    break
        console.print(f"[green]Imported {imported} config file(s)[/]")

    elif args.action == "show":
        name = args.name
        if name not in config_files:
            console.print(f"[red]Unknown config: {name}. Available: {', '.join(config_files.keys())}[/]")
            return
        path = config_files[name]
        if not path.exists():
            console.print(f"[dim]{name}: not found[/]")
            return
        if path.is_file():
            try:
                data = json.loads(path.read_text())
                console.print(Panel(json.dumps(data, indent=2)[:2000], title=f"Config: {name}", border_style="cyan"))
            except Exception:
                content = path.read_text()[:2000]
                console.print(Panel(content, title=f"Config: {name}", border_style="cyan"))
        else:
            console.print(f"[dim]{name}: directory with {len(list(path.iterdir()))} items[/]")

    else:
        console.print("[dim]Use: cm config list|export|import|show[/]")


def cmd_completions(args):
    shell = args.shell or "bash"
    cm_path = Path(__file__).parent.parent / "cm.bat"
    if not cm_path.exists():
        cm_path = Path(__file__).parent.parent / "cm"

    if shell == "bash":
        script = f'''#!/bin/bash
_cloudmesh_completions() {{
    local cur prev commands
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    commands="server monitor dashboard run plan transfer sync history deploy alerts group service compare cmdlog slice autosync interactive backup ping uptime top disk network who find logs export import encrypt decrypt speed scan cleanup report alias version doctor update status discover bench schedule notify api panic tripwire weather trust profile audit ssh template map docker firewall ssl logagg reshistory plugins acl webhooks watcher tunnel database node exec keys config completions"
    if [[ $cur == -* ]]; then
        COMPREPLY=( $(compgen -W "--help --version --json --yes --all --name --nodes --interval --force" -- "$cur") )
    else
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
    fi
    return 0
}}
complete -F _cloudmesh_completions cm 2>/dev/null
complete -F _cloudmesh_completions cloudmesh 2>/dev/null
'''
        out_path = Path(args.output) if args.output else Path("cloudmesh-completions.bash")
        out_path.write_text(script)
        console.print(f"[green]Bash completions saved to {out_path}[/]")
        console.print(f"[dim]Source it: source {out_path}[/]")

    elif shell == "zsh":
        script = f'''#compdef cm cloudmesh

_cloudmesh() {{
    local -a commands
    commands=(
        'server:Manage servers/devices'
        'monitor:Monitor resources'
        'dashboard:Show dashboard'
        'run:Run command on servers'
        'plan:Distribution plan'
        'transfer:Transfer files'
        'sync:Sync directories'
        'history:Resource history'
        'deploy:Deploy packages'
        'alerts:Manage alerts'
        'group:Manage device groups'
        'service:Background service'
        'compare:Compare devices'
        'cmdlog:Command log'
        'slice:File distribution'
        'autosync:Auto-sync directories'
        'interactive:Interactive mode'
        'backup:Backup management'
        'ping:Ping all servers'
        'uptime:Show uptime'
        'top:Top processes'
        'disk:Disk usage'
        'network:Network info'
        'who:Logged in users'
        'find:Search files'
        'logs:Recent logs'
        'export:Export config'
        'import:Import config'
        'encrypt:Encrypt file'
        'decrypt:Decrypt file'
        'speed:Network speed test'
        'scan:Scan subnet'
        'cleanup:Clean old files'
        'report:Generate report'
        'alias:Manage aliases'
        'version:Version info'
        'doctor:Security check'
        'update:Update from GitHub'
        'status:Server status'
        'discover:Auto-discover nodes'
        'bench:Benchmark'
        'schedule:Schedule commands'
        'notify:Notifications'
        'api:REST API server'
        'panic:Emergency key rotate'
        'tripwire:Tripwire keys'
        'weather:Resource forecast'
        'trust:Distributed trust'
        'profile:Config profiles'
        'audit:Security audit'
        'ssh:Quick SSH command'
        'template:Command templates'
        'map:Network map'
        'docker:Docker management'
        'firewall:Firewall rules'
        'ssl:SSL certificate check'
        'logagg:Log aggregation'
        'reshistory:Resource history'
        'plugins:Plugin management'
        'acl:Access control'
        'webhooks:Webhook management'
        'watcher:Process watchers'
        'tunnel:SSH tunnels'
        'database:Database management'
        'node:Cloud node management'
        'exec:Execute on nodes'
        'keys:SSH key management'
        'config:Config management'
        'completions:Shell completions'
    )
    _arguments -s -S \\
        '1:command:->commands' \\
        '*::arg:->args'
    case $state in
        commands) _describe 'command' commands ;;
        args) _cloudmesh_args ;;
    esac
}}
_cloudmesh_args() {{
    local -a subcommands
    case $words[1] in
        server) subcommands='add remove list test info' ;;
        node) subcommands='add remove list test info monitor exec install dashboard gpu job' ;;
        keys) subcommands='generate list show deploy remove-managed' ;;
        config) subcommands='list export import show' ;;
    esac
    _describe 'subcommand' subcommands
}}
_cloudmesh "$@"
'''
        out_path = Path(args.output) if args.output else Path("cloudmesh-completions.zsh")
        out_path.write_text(script)
        console.print(f"[green]Zsh completions saved to {out_path}[/]")
        console.print(f"[dim]Source it: source {out_path}[/]")

    elif shell == "powershell":
        script = '''Register-ArgumentCompleter -Native -CommandName cm -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $commands = @(
        "server", "monitor", "dashboard", "run", "plan", "transfer", "sync",
        "history", "deploy", "alerts", "group", "service", "compare", "cmdlog",
        "slice", "autosync", "interactive", "backup", "ping", "uptime", "top",
        "disk", "network", "who", "find", "logs", "export", "import", "encrypt",
        "decrypt", "speed", "scan", "cleanup", "report", "alias", "version",
        "doctor", "update", "status", "discover", "bench", "schedule", "notify",
        "api", "panic", "tripwire", "weather", "trust", "profile", "audit",
        "ssh", "template", "map", "docker", "firewall", "ssl", "logagg",
        "reshistory", "plugins", "acl", "webhooks", "watcher", "tunnel",
        "database", "node", "exec", "keys", "config", "completions"
    )
    $commands | Where-Object { $_ -like "$wordToComplete*" } |
        ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }
}
'''
        out_path = Path(args.output) if args.output else Path("cloudmesh-completions.ps1")
        out_path.write_text(script)
        console.print(f"[green]PowerShell completions saved to {out_path}[/]")
        console.print(f"[dim]Import it: . {out_path}[/]")

    else:
        console.print(f"[red]Unsupported shell: {shell}. Use bash, zsh, or powershell[/]")

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
    console.print(f"[green]API running on http://127.0.0.1:{port}[/]")
    console.print(f"[bold yellow]API Key: {api.api_key}[/]")
    console.print("[dim]Use header: X-Api-Key: <key>[/]")
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


def _alias_docker(args, action):
    args.action = action
    cmd_docker(args)

def _alias_docker_exec(args):
    args.action = "exec"
    args.container = getattr(args, "container", "")
    args.cmd = getattr(args, "dc_cmd", "")
    args.server = getattr(args, "server", None)
    cmd_docker(args)

def _alias_docker_logs(args):
    args.action = "logs"
    args.container = getattr(args, "container", "")
    args.server = getattr(args, "server", None)
    args.lines = getattr(args, "lines", 50)
    cmd_docker(args)

def _alias_firewall(args, action):
    args.action = action
    args.server = getattr(args, "server", None)
    cmd_firewall(args)

def _alias_firewall_add(args):
    args.action = "add-rule"
    cmd_firewall(args)

def _alias_ssl(args, action):
    args.action = action
    if not hasattr(args, "domain"):
        args.domain = ""
    if not hasattr(args, "port"):
        args.port = 443
    cmd_ssl(args)

def _alias_logagg_search(args):
    args.action = "search"
    cmd_logagg(args)

def _alias_plugin_run(args):
    args.action = "run"
    cmd_plugins(args)

def _alias_webhook_send(args):
    args.action = "send"
    args.name = getattr(args, "name", None)
    args.event = getattr(args, "event", "alert")
    cmd_webhooks(args)

def _alias_watcher(args, action):
    args.action = action
    cmd_watcher(args)

def _alias_tunnel_add(args):
    args.action = "add"
    args.remote_host = "127.0.0.1"
    cmd_tunnel(args)

def _alias_tunnel_start(args):
    args.action = "start"
    cmd_tunnel(args)

def _alias_tunnel_stop(args):
    args.action = "stop"
    cmd_tunnel(args)

def _alias_db_query(args):
    args.action = "query"
    args.host = "127.0.0.1"
    args.port = None
    args.user = "root"
    cmd_database(args)

def _alias_db_backup(args):
    args.action = "backup"
    args.path = "/tmp"
    args.host = "127.0.0.1"
    args.port = None
    args.user = "root"
    cmd_database(args)

def _alias_db_status(args):
    args.action = "status"
    args.host = "127.0.0.1"
    args.port = None
    args.user = "root"
    cmd_database(args)

def _alias_acl(args, action):
    args.action = action
    cmd_acl(args)

def _alias_acl_add(args):
    args.action = "add-user"
    cmd_acl(args)

def _alias_acl_rm(args):
    args.action = "remove-user"
    cmd_acl(args)


# === 5 NEW FEATURES (v1.2.0) ===


def cmd_panic(args):
    if hasattr(args, "panic_action") and args.panic_action:
        shamir = ShamirPanicManager()
        if args.panic_action == "setup":
            shares = shamir.setup_shares()
            console.print(Panel("[bold red]PANIC SHARES GENERATED[/]", border_style="red"))
            console.print("[yellow]Store each share on a separate device. You need 2 of 3 to execute panic.[/]")
            console.print(f"[dim]Threshold: 2 of {len(shares)} shares[/]\n")
            for s in shares:
                console.print(f"  [bold]Share #{s['id']}[/] ({s['label']})")
                console.print(f"    {s['share']}")
                console.print()
            console.print("[red bold]IMPORTANT: These shares cannot be recovered if lost![/]")
            return
        elif args.panic_action == "execute":
            if not args.share:
                console.print("[red]Need at least 2 --share IDs to execute panic[/]")
                return
            console.print(Panel("[bold red]PANIC — Executing with Shamir Shares[/]", border_style="red"))
            console.print(f"[yellow]Using shares: {args.share}[/]")
            actions, error = shamir.execute_with_shares(args.share)
            if error:
                console.print(f"[red]FAILED: {error}[/]")
                return
            for action in actions:
                console.print(f"  [green]+[/] {action}")
            console.print()
            console.print("[red bold]Panic complete. All keys rotated.[/]")
            return
        elif args.panic_action == "shares":
            info = shamir.get_shares_info()
            if not info:
                console.print("[dim]No shares configured. Run: cm panic setup[/]")
                return
            table = Table(title="Panic Shares", box=box.ROUNDED)
            table.add_column("ID", style="bold")
            table.add_column("Label")
            table.add_column("Created")
            for s in info["shares"]:
                table.add_row(str(s["id"]), s["label"], s["created_at"][:19])
            console.print(table)
            console.print(f"[dim]Threshold: {info['threshold']} of {info['n_shares']} shares required[/]")
            return
        elif args.panic_action == "rotate":
            console.print(Panel("[bold red]PANIC ROTATE — Rotating keys on all remote nodes[/]", border_style="red"))
            from core.node_client import NodeClient
            cfg = _load_config()
            nodes = cfg.get("nodes", {})
            if not nodes:
                console.print("[dim]No nodes configured[/]")
                return
            for name, srv in nodes.items():
                host = srv.get("host", "")
                port = srv.get("port", 9999)
                key = srv.get("auth_key", "")
                client = NodeClient(host, port, key)
                try:
                    import secrets as _secrets
                    new_auth = _secrets.token_hex(32)
                    result = client.rotate_key(new_auth)
                    if result.get("success"):
                        console.print(f"  [green]+[/] {name}: rotated successfully")
                    else:
                        console.print(f"  [red]![/] {name}: {result.get('message', 'failed')}")
                except Exception as e:
                    console.print(f"  [red]![/] {name}: {e}")
            console.print("\n[red bold]All node keys rotated. Update your local node_keys.json![/]")
            return
        elif args.panic_action == "retry-pending":
            console.print(Panel("[bold yellow]Retrying pending key rotations...[/]", border_style="yellow"))
            actions = panic.retry_pending()
            for action in actions:
                console.print(f"  [green]+[/] {action}")
            return

    panic = PanicManager()
    if args.dry_run:
        console.print(Panel("[bold red]PANIC — Dry Run[/]", border_style="red"))
        actions = panic.dry_run()
        for action_type, desc in actions:
            console.print(f"  [yellow]{action_type}[/]: {desc}")
        console.print("\n[dim]No changes made (dry run)[/]")
        return

    console.print(Panel("[bold red]PANIC — Executing Emergency Reset[/]", border_style="red"))
    console.print("[yellow]Rotating all encryption keys and node auth keys...[/]")
    actions = panic.execute_panic()
    for action in actions:
        console.print(f"  [green]+[/] {action}")
    console.print()
    console.print("[red bold]All keys rotated. Re-add nodes with new auth keys.[/]")


def cmd_tripwire(args):
    tw = TripwireManager()
    if args.tripwire_action == "plant":
        key = tw.plant(args.node, args.host, args.port)
        console.print(Panel("[bold red]TRIPWIRE PLANTED[/]", border_style="red"))
        console.print(f"  [bold]Node:[/] {args.node}")
        console.print(f"  [bold]Host:[/] {args.host}:{args.port}")
        console.print(f"  [bold]Key:[/]  {key}")
        console.print("\n[yellow]If anyone connects with this key, it's a 100% confirmed breach.[/]")
        console.print("[dim]Do NOT use this key. Store it somewhere safe as proof.[/]")
    elif args.tripwire_action == "list":
        tripwires = tw.list_tripwires()
        if not tripwires:
            console.print("[dim]No tripwires planted.[/]")
            return
        table = Table(title="Tripwire Keys", box=box.ROUNDED)
        table.add_column("Node", style="bold")
        table.add_column("Host")
        table.add_column("Planted At")
        table.add_column("Key (masked)")
        for name, info in tripwires.items():
            table.add_row(name, f"{info['host']}:{info['port']}", info["planted_at"][:19], info["key_masked"])
        console.print(table)
    elif args.tripwire_action == "remove":
        result = tw.remove(args.node)
        console.print(f"[green]{result}[/]")
    elif args.tripwire_action == "check":
        triggered = tw.get_triggered()
        if not triggered:
            console.print("[green]No tripwire activations detected.[/]")
            return
        console.print(f"[red bold]ALERT: {len(triggered)} tripwire activation(s) detected![/]")
        table = Table(title="Tripwire Breaches", box=box.ROUNDED)
        table.add_column("Time")
        table.add_column("Source IP")
        table.add_column("Key Hash")
        for entry in triggered:
            table.add_row(entry.get("timestamp", "?")[:19], entry.get("source_ip", "?"), entry.get("key_hash", "?"))
        console.print(table)


def cmd_weather(args):
    weather = WeatherForecast()
    if args.learn:
        _, server_mgr, monitor, *_ = init_components()
        keys = _load_node_keys()
        count = 0
        for name in server_mgr.list_servers():
            try:
                metrics = monitor.get_all_metrics(name)
                weather.learn_from_metrics(name, metrics)
                count += 1
            except Exception:
                pass
        for name, info in keys.items():
            try:
                client = NodeClient(info["host"], info["port"], info["key"])
                metrics = client.get_metrics()
                weather.learn_from_metrics(name, metrics)
                count += 1
            except Exception:
                pass
        console.print(f"[green]Recorded resource snapshot for {count} server(s)/node(s)[/]")
        return

    if args.clear:
        weather.clear(args.clear if args.clear != "all" else None)
        console.print("[green]Weather data cleared.[/]")
        return

    if args.server:
        pred = weather.predict(args.server, args.hour)
        profile = weather.get_hourly_profile(args.server)
        console.print(Panel(f"[bold]{args.server}[/]", title="Resource Weather", border_style="cyan"))
        table = Table(box=box.ROUNDED)
        table.add_column("Hour", style="bold")
        table.add_column("CPU EMA")
        table.add_column("RAM EMA")
        table.add_column("Samples")
        for slot in profile:
            cpu_str = f"{slot['cpu_ema']:.1f}%" if slot["cpu_ema"] is not None else "—"
            ram_str = f"{slot['ram_ema']:.1f}%" if slot["ram_ema"] is not None else "—"
            table.add_row(str(slot["hour"]), cpu_str, ram_str, str(slot["samples"]))
        console.print(table)
        if pred.get("status") == "predicted":
            next_h = (datetime.now().hour + 1) % 24
            console.print(f"\n  [cyan]Next hour ({next_h}:00) prediction:[/] CPU {pred['cpu_ema']:.1f}% / RAM {pred['ram_ema']:.1f}%")
        return

    all_preds = weather.predict_all(args.hour)
    if not all_preds:
        console.print("[dim]No weather data collected yet. Run: cm weather --learn[/]")
        return

    table = Table(title="Resource Weather Forecast", box=box.ROUNDED)
    table.add_column("Server", style="bold")
    table.add_column("Next Hour")
    table.add_column("Predicted CPU")
    table.add_column("Predicted RAM")
    table.add_column("Samples")
    next_h = (datetime.now().hour + 1) % 24
    for name, pred in all_preds.items():
        if pred.get("status") == "predicted":
            cpu_color = "green" if pred["cpu_ema"] < 50 else "yellow" if pred["cpu_ema"] < 80 else "red"
            table.add_row(name, f"{next_h}:00", f"[{cpu_color}]{pred['cpu_ema']:.1f}%[/]", f"{pred['ram_ema']:.1f}%", str(pred["samples"]))
        else:
            table.add_row(name, f"{next_h}:00", "[dim]no data[/]", "[dim]—[/]", "0")
    console.print(table)


def cmd_trust(args):
    gossip = GossipManager()
    if args.scan:
        console.print("[cyan]Scanning all nodes for trust evaluation...[/]")
        _, server_mgr, *_ = init_components()
        keys = _load_node_keys()
        gossip.scan_all(server_mgr, keys)
        console.print("[green]Scan complete.[/]")

    status = gossip.get_trust_status()
    if not status:
        console.print("[dim]No trust data. Run: cm trust --scan[/]")
        return

    table = Table(title="Distributed Trust Status", box=box.ROUNDED)
    table.add_column("Node", style="bold")
    table.add_column("Trust")
    table.add_column("Score")
    table.add_column("Status")
    table.add_column("Reason")

    for name, node in status.items():
        trust_color = "green" if node.get("trust_score", 0) >= 80 else "yellow" if node.get("trust_score", 0) >= 50 else "red"
        status_str = node.get("status", "unknown")
        reason = node.get("reason") or ""
        table.add_row(
            name,
            f"[{trust_color}]{status_str}[/]",
            f"{node.get('trust_score', '?')}",
            status_str,
            reason[:50] if reason else "",
        )

    console.print(table)

    suspicious = gossip.get_suspicious_nodes()
    if suspicious:
        console.print()
        console.print(f"[red bold]WARNING: {len(suspicious)} suspicious node(s) detected![/]")


# === CHECKPOINT COMMANDS (part of node job) ===

def cmd_job_checkpoint(args):
    keys = _load_node_keys()
    if args.name not in keys:
        console.print(f"[red]Node '{args.name}' not found.[/]")
        return
    info = keys[args.name]
    client = NodeClient(info["host"], info["port"], info["key"])
    result = client.check_job(args.job_id)
    if not result:
        console.print("[red]Job not found.[/]")
        return
    jm = JobManager()
    cp_result = jm.checkpoint_job(
        args.job_id,
        stdout=result.get("stdout", ""),
        stderr=result.get("stderr", ""),
        exit_code=result.get("exit_code"),
    )
    if cp_result:
        console.print(f"[green]Job '{args.job_id}' checkpointed successfully.[/]")
    else:
        console.print(f"[red]Failed to checkpoint job '{args.job_id}'.[/]")


def cmd_job_recover(args):
    jm = JobManager()
    recoverable = jm.get_recoverable_jobs()
    if not recoverable:
        console.print("[dim]No recoverable jobs found.[/]")
        return
    table = Table(title="Recoverable Jobs", box=box.ROUNDED)
    table.add_column("Job ID", style="bold")
    table.add_column("Command")
    table.add_column("Original Server")
    table.add_column("Progress")
    table.add_column("Checkpointed At")
    for cp in recoverable:
        table.add_row(
            cp.get("job_id", "?"),
            cp.get("command", "?")[:40],
            cp.get("server", "?"),
            str(cp.get("progress", 0)) + "%",
            cp.get("checkpointed_at", "?")[:19],
        )
    console.print(table)
    if args.relaunch:
        for cp in recoverable:
            result = jm.recover_job(cp["job_id"], args.target)
            if result:
                console.print(f"[green]Recovered {cp['job_id']} -> new job {result['new_job_id']} on {result['server']}[/]")
            else:
                console.print(f"[red]Failed to recover {cp['job_id']}[/]")


def cmd_job_checkpoints(args):
    cp = CheckpointManager()
    checkpoints = cp.list_checkpoints()
    if not checkpoints:
        console.print("[dim]No checkpoints found.[/]")
        return
    table = Table(title="Job Checkpoints", box=box.ROUNDED)
    table.add_column("Job ID", style="bold")
    table.add_column("Command")
    table.add_column("Server")
    table.add_column("Progress")
    table.add_column("Checkpointed At")
    for c in checkpoints:
        table.add_row(
            c.get("job_id", "?"),
            c.get("command", "?")[:40],
            c.get("server", "?"),
            str(c.get("progress", 0)) + "%",
            c.get("checkpointed_at", "?")[:19],
        )
    console.print(table)


def main():
    parser = argparse.ArgumentParser(prog="cloudmesh", description="CloudMesh - Connect devices & servers into one resource pool")
    parser.add_argument("--version", "-V", action="version", version="CloudMesh 2.0.0")
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
    cl.add_argument("--verify", action="store_true", help="Verify command log chain integrity")

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

    doc = subparsers.add_parser("doctor", help="Security & health check")

    upd = subparsers.add_parser("update", help="Update CloudMesh from GitHub")
    upd.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")

    sts = subparsers.add_parser("status", help="Quick status of all servers")
    sts.add_argument("--json", "-j", action="store_true", dest="as_json", help="Output as JSON")

    exec_p = subparsers.add_parser("exec", help="Execute command on nodes")
    exec_p.add_argument("command", help="Command to execute")
    exec_p.add_argument("--name", "-n", help="Target node name")
    exec_p.add_argument("--nodes", help="Comma-separated node names")
    exec_p.add_argument("--all", dest="all_nodes", action="store_true", help="Execute on all nodes")
    exec_p.add_argument("--json", "-j", action="store_true", dest="as_json", help="Output as JSON")

    watch_p = subparsers.add_parser("watch", help="Real-time monitoring dashboard")
    watch_p.add_argument("--interval", "-i", type=int, default=3, help="Refresh interval in seconds")

    keys_p = subparsers.add_parser("keys", help="SSH key management")
    keys_sub = keys_p.add_subparsers(dest="action")
    kgen = keys_sub.add_parser("generate", help="Generate SSH key pair")
    kgen.add_argument("--name", "-n", help="Key name")
    kgen.add_argument("--bits", "-b", type=int, help="Key bits (256 for ed25519, 4096 for rsa)")
    kgen.add_argument("--passphrase", "-p", default="", help="Key passphrase")
    kgen.add_argument("--force", "-f", action="store_true", help="Overwrite existing key")
    keys_sub.add_parser("list", help="List SSH keys")
    ksh = keys_sub.add_parser("show", help="Show public key")
    ksh.add_argument("pub_file", help="Path to public key file")
    kdep = keys_sub.add_parser("deploy", help="Deploy public key to servers")
    kdep.add_argument("pub_file", help="Path to public key file")
    kdep.add_argument("--server", "-s", help="Target server (all if omitted)")
    krm = keys_sub.add_parser("remove-managed", help="Remove managed key entry")
    krm.add_argument("--name", "-n", required=True, help="Managed key name")

    cfg_p = subparsers.add_parser("config", help="Configuration management")
    cfg_sub = cfg_p.add_subparsers(dest="action")
    cfg_sub.add_parser("list", help="List all config files")
    cfg_exp = cfg_sub.add_parser("export", help="Export all config to directory")
    cfg_exp.add_argument("--output", "-o", help="Output directory")
    cfg_imp = cfg_sub.add_parser("import", help="Import config from directory")
    cfg_imp.add_argument("source", help="Source directory")
    cfg_shw = cfg_sub.add_parser("show", help="Show config file contents")
    cfg_shw.add_argument("name", help="Config name (use 'config list' to see names)")

    comp_p = subparsers.add_parser("completions", help="Generate shell completions")
    comp_p.add_argument("--shell", "-s", choices=["bash", "zsh", "powershell"], default="bash", help="Shell type")
    comp_p.add_argument("--output", "-o", help="Output file path")

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

    # === v1.2.0 NEW COMMANDS ===

    panic_p = subparsers.add_parser("panic", help="Emergency: rotate all keys")
    panic_p.add_argument("--dry-run", action="store_true", help="Preview without changes")
    panic_sub = panic_p.add_subparsers(dest="panic_action")
    panic_sub.add_parser("setup", help="Split panic key into 3 Shamir shares")
    panic_exec = panic_sub.add_parser("execute", help="Execute panic with 2-of-3 shares")
    panic_exec.add_argument("--share", "-s", type=int, nargs="+", required=True, help="Share IDs to use (need >= 2)")
    panic_sub.add_parser("shares", help="Show current share status")
    panic_sub.add_parser("rotate", help="Rotate keys on all remote nodes")
    panic_sub.add_parser("retry-pending", help="Retry rotations that failed (nodes were offline)")

    tw_p = subparsers.add_parser("tripwire", help="Tripwire key management")
    tw_sub = tw_p.add_subparsers(dest="tripwire_action")
    tw_plant = tw_sub.add_parser("plant", help="Plant a tripwire key")
    tw_plant.add_argument("--node", "-n", required=True, help="Tripwire name")
    tw_plant.add_argument("--host", "-H", required=True, help="Fake host IP")
    tw_plant.add_argument("-p", dest="port", type=int, default=9999)
    tw_sub.add_parser("list", help="List planted tripwires")
    tw_rm = tw_sub.add_parser("remove", help="Remove a tripwire")
    tw_rm.add_argument("--node", "-n", required=True)
    tw_sub.add_parser("check", help="Check if any tripwire was triggered")

    tw_alias = subparsers.add_parser("tw", help="[alias] Tripwire key management")
    tw_alias_sub = tw_alias.add_subparsers(dest="tripwire_action")
    tw_alias_sub.add_parser("plant", help="Plant a tripwire key")
    tw_alias_sub.add_parser("list", help="List planted tripwires")
    tw_alias_sub.add_parser("remove", help="Remove a tripwire")
    tw_alias_sub.add_parser("check", help="Check if any tripwire was triggered")

    triw_alias = subparsers.add_parser("triw", help="[alias] Tripwire key management")
    triw_alias_sub = triw_alias.add_subparsers(dest="tripwire_action")
    triw_alias_sub.add_parser("plant", help="Plant a tripwire key")
    triw_alias_sub.add_parser("list", help="List planted tripwires")
    triw_alias_sub.add_parser("remove", help="Remove a tripwire")
    triw_alias_sub.add_parser("check", help="Check if any tripwire was triggered")

    wea = subparsers.add_parser("weather", help="Resource weather forecast")
    wea.add_argument("--server", "-s", help="Show forecast for specific server")
    wea.add_argument("--hour", "-H", type=int, help="Predict for specific hour (0-23)")
    wea.add_argument("--learn", action="store_true", help="Record current resource snapshot")
    wea.add_argument("--clear", nargs="?", const="all", help="Clear weather data")

    trust_p = subparsers.add_parser("trust", help="Distributed trust status")
    trust_p.add_argument("--scan", action="store_true", help="Scan all nodes and evaluate trust")

    job_cp = job_sub.add_parser("checkpoint", help="Checkpoint a running job")
    job_cp.add_argument("--name", "-n", required=True)
    job_cp.add_argument("--job-id", "-j", required=True)

    job_rc = job_sub.add_parser("recover", help="Show/recover jobs from failed nodes")
    job_rc.add_argument("--relaunch", action="store_true", help="Auto-relaunch recoverable jobs")
    job_rc.add_argument("--target", "-t", help="Target node for recovery")

    job_cp2 = job_sub.add_parser("checkpoints", help="List all job checkpoints")

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

    docker_p = subparsers.add_parser("docker", help="Docker management")
    docker_sub = docker_p.add_subparsers(dest="action")
    docker_sub.add_parser("list-servers", help="List servers with Docker")
    dc = docker_sub.add_parser("containers", help="List containers")
    dc.add_argument("--server", "-s")
    dco = docker_sub.add_parser("compose", help="Run docker-compose")
    dco.add_argument("path")
    dco.add_argument("--server", "-s")
    dco.add_argument("--action", "-a", default="up")
    dds = docker_sub.add_parser("stats", help="Container stats")
    dds.add_argument("--server", "-s")
    ddi = docker_sub.add_parser("images", help="List images")
    ddi.add_argument("--server", "-s")
    ddp = docker_sub.add_parser("pull", help="Pull image")
    ddp.add_argument("image")
    ddp.add_argument("--server", "-s")
    ddx = docker_sub.add_parser("exec", help="Exec in container")
    ddx.add_argument("container")
    ddx.add_argument("cmd")
    ddx.add_argument("--server", "-s")
    ddl = docker_sub.add_parser("logs", help="Container logs")
    ddl.add_argument("container")
    ddl.add_argument("--server", "-s")
    ddl.add_argument("--lines", "-n", type=int, default=50)
    ddcl = docker_sub.add_parser("cleanup", help="Cleanup Docker")
    ddcl.add_argument("--server", "-s")
    ddpr = docker_sub.add_parser("prune", help="Prune everything")
    ddpr.add_argument("--server", "-s")

    fw_p = subparsers.add_parser("firewall", help="Firewall management")
    fw_sub = fw_p.add_subparsers(dest="action")
    fw_sub.add_parser("list-rules", help="List rules")
    fw_add = fw_sub.add_parser("add-rule", help="Add rule")
    fw_add.add_argument("--port", "-p", required=True, type=int)
    fw_add.add_argument("--proto", default="tcp")
    fw_add.add_argument("--action", "-a", default="allow")
    fw_add.add_argument("--server", "-s")
    fwr = fw_sub.add_parser("remove-rule", help="Remove rule")
    fwr.add_argument("--port", "-p", required=True, type=int)
    fwr.add_argument("--proto", default="tcp")
    fwr.add_argument("--server", "-s")
    fw_sub.add_parser("status", help="Firewall status")
    fw_status = fw_sub.add_parser("check-port", help="Check if port open")
    fw_status.add_argument("--port", "-p", required=True, type=int)
    fw_status.add_argument("--server", "-s")
    fwb = fw_sub.add_parser("backup", help="Backup rules")
    fwb.add_argument("--server", "-s")
    fwb.add_argument("--output", "-o", default="firewall_backup.json")
    fwl = fw_sub.add_parser("load", help="Load rules from file")
    fwl.add_argument("file")
    fwl.add_argument("--server", "-s")

    ssl_p = subparsers.add_parser("ssl", help="SSL certificate monitor")
    ssl_sub = ssl_p.add_subparsers(dest="action")
    sslc = ssl_sub.add_parser("check", help="Check certificate")
    sslc.add_argument("domain")
    sslc.add_argument("--port", "-p", type=int, default=443)
    ssl_sub.add_parser("check-all", help="Check all domains")
    ssld = ssl_sub.add_parser("domains", help="List domains")
    ssla = ssl_sub.add_parser("add", help="Add domain")
    ssla.add_argument("domain")
    ssla.add_argument("--port", "-p", type=int, default=443)
    sslr = ssl_sub.add_parser("remove", help="Remove domain")
    sslr.add_argument("domain")
    ssl_sub.add_parser("history", help="Expiry history")
    ssl_sub.add_parser("renew-check", help="Check renewal status")

    log_p = subparsers.add_parser("logagg", help="Log aggregation")
    log_sub = log_p.add_subparsers(dest="action")
    log_src = log_sub.add_parser("add-source", help="Add log source")
    log_src.add_argument("--server", "-s")
    log_src.add_argument("--path", required=True)
    log_src.add_argument("--tag", "-t", default="default")
    log_sub.add_parser("sources", help="List sources")
    logs = log_sub.add_parser("search", help="Search logs")
    logs.add_argument("--pattern", "-p", required=True)
    logs.add_argument("--source", "-s")
    logs.add_argument("--since", default="1h")
    logs.add_argument("--limit", "-n", type=int, default=50)
    logf = log_sub.add_parser("filter", help="Filter logs")
    logf.add_argument("--source", "-s")
    logf.add_argument("--level", "-l", choices=["error", "warn", "info", "debug"])
    logf.add_argument("--since", default="1h")
    logf.add_argument("--limit", "-n", type=int, default=50)
    logsub = log_sub.add_parser("subscribe", help="Tail logs live")
    logsub.add_argument("--source", "-s")
    logsub.add_argument("--filter", "-f")
    logsub.add_argument("--interval", "-i", type=int, default=2)
    log_sub.add_parser("stats", help="Log statistics")
    logcl = log_sub.add_parser("clear", help="Clear log index")
    logcl.add_argument("--source", "-s")

    rh_p = subparsers.add_parser("reshistory", help="Resource history")
    rh_sub = rh_p.add_subparsers(dest="action")
    rh_sub.add_parser("snapshot", help="Take snapshot")
    rhs = rh_sub.add_parser("show", help="Show history")
    rhs.add_argument("server")
    rhs.add_argument("--metric", "-m")
    rhs.add_argument("--limit", "-n", type=int, default=20)
    rhsum = rh_sub.add_parser("summary", help="Summary")
    rhsum.add_argument("server")
    rhcl = rh_sub.add_parser("clear", help="Clear history")
    rhcl.add_argument("--server", "-s")

    plg_p = subparsers.add_parser("plugins", help="Custom plugins")
    plg_sub = plg_p.add_subparsers(dest="action")
    plg_sub.add_parser("list", help="List plugins")
    plga = plg_sub.add_parser("add", help="Add plugin")
    plga.add_argument("--name", "-n", required=True)
    plga.add_argument("--command", "-c", required=True)
    plga.add_argument("--desc", "-d", default="")
    plga.add_argument("--targets", "-t", default="all")
    plgr = plg_sub.add_parser("remove", help="Remove plugin")
    plgr.add_argument("--name", "-n", required=True)
    plgrun = plg_sub.add_parser("run", help="Run plugin")
    plgrun.add_argument("--name", "-n", required=True)
    plgrun.add_argument("--server", "-s")
    plgi = plg_sub.add_parser("import", help="Import plugins")
    plgi.add_argument("file")
    plge = plg_sub.add_parser("export", help="Export plugin")
    plge.add_argument("--name", "-n", required=True)
    plge.add_argument("--output", "-o")

    acl_p = subparsers.add_parser("acl", help="Multi-user ACL")
    acl_sub = acl_p.add_subparsers(dest="action")
    acl_sub.add_parser("users", help="List users")
    aclu = acl_sub.add_parser("add-user", help="Add user")
    aclu.add_argument("--username", "-u", required=True)
    aclu.add_argument("--password", "-p", required=True)
    aclu.add_argument("--role", "-r", default="viewer")
    aclrm = acl_sub.add_parser("remove-user", help="Remove user")
    aclrm.add_argument("--username", "-u", required=True)
    aclsr = acl_sub.add_parser("set-role", help="Set role")
    aclsr.add_argument("--username", "-u", required=True)
    aclsr.add_argument("--role", "-r", required=True)
    aclen = acl_sub.add_parser("enable", help="Enable user")
    aclen.add_argument("--username", "-u", required=True)
    acldi = acl_sub.add_parser("disable", help="Disable user")
    acldi.add_argument("--username", "-u", required=True)
    acl_sub.add_parser("roles", help="List roles")
    aclar = acl_sub.add_parser("add-role", help="Add role")
    aclar.add_argument("--name", "-n", required=True)
    aclar.add_argument("--perms", required=True, help="comma-separated")
    aclrr = acl_sub.add_parser("remove-role", help="Remove role")
    aclrr.add_argument("--name", "-n", required=True)

    wh_p = subparsers.add_parser("webhooks", help="Webhook integrations")
    wh_sub = wh_p.add_subparsers(dest="action")
    wh_sub.add_parser("list", help="List webhooks")
    wha = wh_sub.add_parser("add", help="Add webhook")
    wha.add_argument("--name", "-n", required=True)
    wha.add_argument("--url", required=True)
    wha.add_argument("--type", "-t", default="custom", choices=["discord", "slack", "telegram", "custom"])
    wha.add_argument("--events", "-e", default="alert,error")
    whr = wh_sub.add_parser("remove", help="Remove webhook")
    whr.add_argument("--name", "-n", required=True)
    wht = wh_sub.add_parser("test", help="Test webhook")
    wht.add_argument("--name", "-n", required=True)
    wh_sub.add_parser("log", help="Webhook log")
    whs = wh_sub.add_parser("send", help="Send custom message")
    whs.add_argument("--name", "-n")
    whs.add_argument("message")
    whs.add_argument("--event", "-e", default="alert")
    wh_sub.add_parser("enable-all", help="Enable all webhooks")
    wh_sub.add_parser("disable-all", help="Disable all webhooks")

    wt_p = subparsers.add_parser("watcher", help="Process watcher")
    wt_sub = wt_p.add_subparsers(dest="action")
    wt_list = wt_sub.add_parser("list", help="List watchers")
    wta = wt_sub.add_parser("add", help="Add watcher")
    wta.add_argument("--name", "-n", required=True)
    wta.add_argument("--process", required=True)
    wta.add_argument("--server", "-s")
    wta.add_argument("--alert-on", default="stop", choices=["stop", "start"])
    wtr = wt_sub.add_parser("remove", help="Remove watcher")
    wtr.add_argument("--name", "-n", required=True)
    wtc = wt_sub.add_parser("check", help="Check all watchers")
    wts = wt_sub.add_parser("check-status", help="Check process on server")
    wts.add_argument("--server", "-s", required=True)
    wts.add_argument("--process", required=True)
    wt_sub.add_parser("alerts", help="Watcher alerts")

    tun_p = subparsers.add_parser("tunnel", help="SSH tunnel manager")
    tun_sub = tun_p.add_subparsers(dest="action")
    tun_sub.add_parser("list", help="List tunnels")
    tuna = tun_sub.add_parser("add", help="Add tunnel")
    tuna.add_argument("--name", "-n", required=True)
    tuna.add_argument("--host", required=True)
    tuna.add_argument("--user", "-u", default="root")
    tuna.add_argument("--local-port", "-l", type=int, required=True)
    tuna.add_argument("--remote-host", default="127.0.0.1")
    tuna.add_argument("--remote-port", "-r", type=int, required=True)
    tuna.add_argument("--key", "-k")
    tunr = tun_sub.add_parser("remove", help="Remove tunnel")
    tunr.add_argument("--name", "-n", required=True)
    tunstart = tun_sub.add_parser("start", help="Start tunnel")
    tunstart.add_argument("--name", "-n", required=True)
    tunstop = tun_sub.add_parser("stop", help="Stop tunnel")
    tunstop.add_argument("--name", "-n", required=True)
    tun_sub.add_parser("stop-all", help="Stop all tunnels")
    tun_sub.add_parser("status", help="Tunnel status")
    tunq = tun_sub.add_parser("quick", help="Quick tunnel")
    tunq.add_argument("--host", required=True)
    tunq.add_argument("--user", "-u", default="root")
    tunq.add_argument("--local-port", "-l", type=int, required=True)
    tunq.add_argument("--remote-port", "-r", type=int, required=True)
    tunq.add_argument("--key", "-k")

    db_p = subparsers.add_parser("database", help="Database manager")
    db_sub = db_p.add_subparsers(dest="action")
    dbl = db_sub.add_parser("list", help="List databases")
    dbl.add_argument("--server", "-s", required=True)
    dbl.add_argument("--type", "-t", default="mysql", choices=["mysql", "postgres"])
    dbl.add_argument("--host", default="127.0.0.1")
    dbl.add_argument("--port", "-p", type=int)
    dbl.add_argument("--user", "-u", default="root")
    dbl.add_argument("--password", "-P", default="")
    dbs = db_sub.add_parser("status", help="Database status")
    dbs.add_argument("--server", "-s", required=True)
    dbs.add_argument("--type", "-t", default="mysql")
    dbs.add_argument("--host", default="127.0.0.1")
    dbs.add_argument("--port", "-p", type=int)
    dbs.add_argument("--user", "-u", default="root")
    dbs.add_argument("--password", "-P", default="")
    dbq = db_sub.add_parser("query", help="Run query")
    dbq.add_argument("--server", "-s", required=True)
    dbq.add_argument("sql")
    dbq.add_argument("--database", "-d", default="mysql")
    dbq.add_argument("--type", "-t", default="mysql")
    dbq.add_argument("--host", default="127.0.0.1")
    dbq.add_argument("--port", "-p", type=int)
    dbq.add_argument("--user", "-u", default="root")
    dbq.add_argument("--password", "-P", default="")
    dbb = db_sub.add_parser("backup", help="Backup database")
    dbb.add_argument("--server", "-s", required=True)
    dbb.add_argument("--database", "-d", required=True)
    dbb.add_argument("--path", default="/tmp")
    dbb.add_argument("--type", "-t", default="mysql")
    dbb.add_argument("--host", default="127.0.0.1")
    dbb.add_argument("--port", "-p", type=int)
    dbb.add_argument("--user", "-u", default="root")
    dbb.add_argument("--password", "-P", default="")

    mon = subparsers.add_parser("mon", help="[alias] Monitor resources")
    mon.add_argument("--name", "-n")

    dash = subparsers.add_parser("dash", help="[alias] Live dashboard")

    ls = subparsers.add_parser("ls", help="[alias] List servers")
    ls.add_argument("--name", "-n")

    add_alias = subparsers.add_parser("add", help="[alias] Add server")
    add_alias.add_argument("--name", "-n", required=True)
    add_alias.add_argument("--host", "-H", required=True)
    add_alias.add_argument("--user", "-u", required=True)
    add_alias.add_argument("--port", "-p", type=int, default=22)
    add_alias.add_argument("--key", "-k")
    add_alias.add_argument("--password")

    rm_alias = subparsers.add_parser("rm", help="[alias] Remove server")
    rm_alias.add_argument("--name", "-n", required=True)

    rm_node = subparsers.add_parser("rmnode", help="[alias] Remove node")
    rm_node.add_argument("--name", "-n", required=True)

    test_alias = subparsers.add_parser("test", help="[alias] Test connection")
    test_alias.add_argument("--name", "-n")

    info_alias = subparsers.add_parser("info", help="[alias] Server info")
    info_alias.add_argument("--name", "-n")

    up = subparsers.add_parser("up", help="[alias] Show uptime")
    up.add_argument("--name", "-n")

    df = subparsers.add_parser("df", help="[alias] Disk usage")
    df.add_argument("--name", "-n")

    log_alias = subparsers.add_parser("log", help="[alias] System logs")
    log_alias.add_argument("--name", "-n", required=True)
    log_alias.add_argument("--file", "-f", default="/var/log/syslog")
    log_alias.add_argument("--lines", "-l", type=int, default=50)

    net = subparsers.add_parser("net", help="[alias] Network info")
    net.add_argument("--name", "-n")

    cp = subparsers.add_parser("cp", help="[alias] Transfer file")
    cp.add_argument("--server", "-s", required=True)
    cp.add_argument("--local", "-l")
    cp.add_argument("--remote", "-r")
    cp.add_argument("--direction", "-d", default="upload", choices=["upload", "download"])

    enc_alias = subparsers.add_parser("enc", help="[alias] Encrypt file")
    enc_alias.add_argument("file")

    dec_alias = subparsers.add_parser("dec", help="[alias] Decrypt file")
    dec_alias.add_argument("file")

    exp = subparsers.add_parser("exp", help="[alias] Export config")
    exp.add_argument("--file", "-f", default="cloudmesh_export.json")

    imp = subparsers.add_parser("imp", help="[alias] Import config")
    imp.add_argument("--file", "-f", required=True)

    js = subparsers.add_parser("js", help="[alias] Start async job")
    js.add_argument("--name", "-n", required=True)
    js.add_argument("job_cmd")
    js.add_argument("--timeout", "-t", type=int, default=300)

    monnode = subparsers.add_parser("monnode", help="[alias] Monitor node")
    monnode.add_argument("--name", "-n")

    gpunode = subparsers.add_parser("gpunode", help="[alias] GPU on node")
    gpunode.add_argument("--name", "-n")

    installnode = subparsers.add_parser("nodeinstall", help="[alias] Install node")
    installnode.add_argument("--host", "-H", required=True)
    installnode.add_argument("--user", "-u", default="root")
    installnode.add_argument("--key", "-k")

    dcls = subparsers.add_parser("dcls", help="[alias] Docker containers")
    dcls.add_argument("--server", "-s")

    dcstats = subparsers.add_parser("dcstats", help="[alias] Docker stats")
    dcstats.add_argument("--server", "-s")

    dcexec = subparsers.add_parser("dcexec", help="[alias] Docker exec")
    dcexec.add_argument("container")
    dcexec.add_argument("dc_cmd")
    dcexec.add_argument("--server", "-s")

    dclogs = subparsers.add_parser("dclogs", help="[alias] Docker logs")
    dclogs.add_argument("container")
    dclogs.add_argument("--server", "-s")
    dclogs.add_argument("--lines", "-n", type=int, default=50)

    fw = subparsers.add_parser("fw", help="[alias] Firewall status")

    fwadd = subparsers.add_parser("fwadd", help="[alias] Add firewall rule")
    fwadd.add_argument("--port", "-p", required=True, type=int)
    fwadd.add_argument("--proto", default="tcp")
    fwadd.add_argument("--action", "-a", default="allow")
    fwadd.add_argument("--server", "-s")

    sslchk = subparsers.add_parser("sslchk", help="[alias] Check SSL")
    sslchk.add_argument("domain")
    sslchk.add_argument("--port", "-p", type=int, default=443)

    sslall = subparsers.add_parser("sslall", help="[alias] Check all SSL")

    logsearch = subparsers.add_parser("logsearch", help="[alias] Search logs")
    logsearch.add_argument("--pattern", "-p", required=True)
    logsearch.add_argument("--source", "-s")
    logsearch.add_argument("--since", default="1h")
    logsearch.add_argument("--limit", "-n", type=int, default=50)

    pluginrun = subparsers.add_parser("pluginrun", help="[alias] Run plugin")
    pluginrun.add_argument("--name", "-n", required=True)
    pluginrun.add_argument("--server", "-s")

    whsend = subparsers.add_parser("whsend", help="[alias] Send webhook")
    whsend.add_argument("--name", "-n")
    whsend.add_argument("message")
    whsend.add_argument("--event", "-e", default="alert")

    wtchk = subparsers.add_parser("wtchk", help="[alias] Check watchers")

    tunadd = subparsers.add_parser("tunadd", help="[alias] Add tunnel")
    tunadd.add_argument("--name", "-n", required=True)
    tunadd.add_argument("--host", required=True)
    tunadd.add_argument("--user", "-u", default="root")
    tunadd.add_argument("--local-port", "-l", type=int, required=True)
    tunadd.add_argument("--remote-port", "-r", type=int, required=True)
    tunadd.add_argument("--key", "-k")

    tunstart = subparsers.add_parser("tunstart", help="[alias] Start tunnel")
    tunstart.add_argument("--name", "-n", required=True)

    tunstop = subparsers.add_parser("tunstop", help="[alias] Stop tunnel")
    tunstop.add_argument("--name", "-n", required=True)

    dbq = subparsers.add_parser("dbq", help="[alias] Database query")
    dbq.add_argument("--server", "-s", required=True)
    dbq.add_argument("sql")
    dbq.add_argument("--database", "-d", default="mysql")
    dbq.add_argument("--type", "-t", default="mysql")
    dbq.add_argument("--password", "-P", default="")

    dbbak = subparsers.add_parser("dbbak", help="[alias] Database backup")
    dbbak.add_argument("--server", "-s", required=True)
    dbbak.add_argument("--database", "-d", required=True)
    dbbak.add_argument("--type", "-t", default="mysql")
    dbbak.add_argument("--password", "-P", default="")

    dbstatus = subparsers.add_parser("dbstatus", help="[alias] Database status")
    dbstatus.add_argument("--server", "-s", required=True)
    dbstatus.add_argument("--type", "-t", default="mysql")
    dbstatus.add_argument("--password", "-P", default="")

    aclu = subparsers.add_parser("aclu", help="[alias] List ACL users")
    acladd = subparsers.add_parser("acladd", help="[alias] Add ACL user")
    acladd.add_argument("--username", "-u", required=True)
    acladd.add_argument("--password", "-p", required=True)
    acladd.add_argument("--role", "-r", default="viewer")

    aclrm = subparsers.add_parser("aclrm", help="[alias] Remove ACL user")
    aclrm.add_argument("--username", "-u", required=True)

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
            "checkpoint": cmd_job_checkpoint,
            "recover": cmd_job_recover,
            "checkpoints": cmd_job_checkpoints,
        }.get(args.action, lambda: node.print_help())(args),
        "monitor": lambda: cmd_monitor(args),
        "mon": lambda: cmd_monitor(args),
        "dashboard": lambda: cmd_dashboard(args),
        "dash": lambda: cmd_dashboard(args),
        "run": lambda: cmd_run(args),
        "plan": lambda: cmd_plan(args),
        "transfer": lambda: cmd_transfer(args),
        "cp": lambda: cmd_transfer(args),
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
        "up": lambda: cmd_uptime(args),
        "top": lambda: cmd_top(args),
        "disk": lambda: cmd_disk(args),
        "df": lambda: cmd_disk(args),
        "network": lambda: cmd_network(args),
        "net": lambda: cmd_network(args),
        "who": lambda: cmd_who(args),
        "find": lambda: cmd_find(args),
        "logs": lambda: cmd_logs(args),
        "log": lambda: cmd_logs(args),
        "export": lambda: cmd_export(args),
        "exp": lambda: cmd_export(args),
        "import": lambda: cmd_import(args),
        "imp": lambda: cmd_import(args),
        "encrypt": lambda: cmd_encrypt(args),
        "enc": lambda: cmd_encrypt(args),
        "decrypt": lambda: cmd_decrypt(args),
        "dec": lambda: cmd_decrypt(args),
        "speed": lambda: cmd_speed(args),
        "scan": lambda: cmd_scan(args),
        "cleanup": lambda: cmd_cleanup(args),
        "report": lambda: cmd_report(args),
        "alias": lambda: cmd_alias(args),
        "version": lambda: cmd_version(args),
        "doctor": lambda: cmd_doctor(args),
        "update": lambda: cmd_update(args),
        "status": lambda: cmd_status(args),
        "exec": lambda: cmd_exec(args),
        "watch": lambda: cmd_watch(args),
        "keys": lambda: cmd_keys(args),
        "config": lambda: cmd_config(args),
        "completions": lambda: cmd_completions(args),
        "discover": lambda: cmd_discover(args),
        "bench": lambda: cmd_bench(args),
        "schedule": lambda: cmd_schedule(args),
        "notify": lambda: cmd_notify(args),
        "api": lambda: cmd_api(args),
        "panic": lambda: cmd_panic(args),
        "tripwire": lambda: cmd_tripwire(args),
        "tw": lambda: cmd_tripwire(args),
        "triw": lambda: cmd_tripwire(args),
        "weather": lambda: cmd_weather(args),
        "trust": lambda: cmd_trust(args),
        "profile": lambda: cmd_profile(args),
        "audit": lambda: cmd_audit(args),
        "ssh": lambda: cmd_ssh(args),
        "template": lambda: cmd_template(args),
        "map": lambda: cmd_map(args),
        "docker": lambda: cmd_docker(args),
        "firewall": lambda: cmd_firewall(args),
        "ssl": lambda: cmd_ssl(args),
        "logagg": lambda: cmd_logagg(args),
        "reshistory": lambda: cmd_reshistory(args),
        "plugins": lambda: cmd_plugins(args),
        "acl": lambda: cmd_acl(args),
        "webhooks": lambda: cmd_webhooks(args),
        "watcher": lambda: cmd_watcher(args),
        "tunnel": lambda: cmd_tunnel(args),
        "database": lambda: cmd_database(args),
        "ls": lambda: cmd_server_list(args),
        "add": lambda: cmd_server_add(args),
        "rm": lambda: cmd_server_remove(args),
        "rmnode": lambda: cmd_node_remove(args),
        "test": lambda: cmd_server_test(args),
        "info": lambda: cmd_node_info(args),
        "monnode": lambda: cmd_node_monitor(args),
        "gpunode": lambda: cmd_node_gpu(args),
        "exec": lambda: cmd_node_exec(args),
        "nodeinstall": lambda: cmd_node_install(args),
        "dcls": lambda: _alias_docker(args, "containers"),
        "dcstats": lambda: _alias_docker(args, "stats"),
        "dcexec": lambda: _alias_docker_exec(args),
        "dclogs": lambda: _alias_docker_logs(args),
        "fw": lambda: _alias_firewall(args, "status"),
        "fwadd": lambda: _alias_firewall_add(args),
        "sslchk": lambda: _alias_ssl(args, "check"),
        "sslall": lambda: _alias_ssl(args, "check-all"),
        "logsearch": lambda: _alias_logagg_search(args),
        "pluginrun": lambda: _alias_plugin_run(args),
        "whsend": lambda: _alias_webhook_send(args),
        "wtchk": lambda: _alias_watcher(args, "check"),
        "tunadd": lambda: _alias_tunnel_add(args),
        "tunstart": lambda: _alias_tunnel_start(args),
        "tunstop": lambda: _alias_tunnel_stop(args),
        "dbq": lambda: _alias_db_query(args),
        "dbbak": lambda: _alias_db_backup(args),
        "dbstatus": lambda: _alias_db_status(args),
        "aclu": lambda: _alias_acl(args, "users"),
        "acladd": lambda: _alias_acl_add(args),
        "aclrm": lambda: _alias_acl_rm(args),
    }
    handler = cmds.get(args.command)
    if handler:
        handler()


if __name__ == "__main__":
    main()
