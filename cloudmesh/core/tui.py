from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
import sys


console = Console()


class InteractiveTUI:
    def __init__(self, server_manager, resource_monitor, scheduler, groups_mgr, command_log):
        self.server_mgr = server_manager
        self.monitor = resource_monitor
        self.scheduler = scheduler
        self.groups = groups_mgr
        self.cmd_log = command_log

    def run(self):
        console.clear()
        while True:
            self._show_menu()
            choice = Prompt.ask("\n[bold cyan]Choose[/]", choices=["1","2","3","4","5","6","7","8","9","0"])
            if choice == "0":
                console.print("[dim]Goodbye![/]")
                break
            self._handle_choice(choice)

    def _show_menu(self):
        console.print()
        console.print(Panel("[bold bright_blue]CloudMesh Interactive Menu[/]", border_style="bright_blue"))
        console.print()
        console.print("  [bold cyan]1[/] - List all devices")
        console.print("  [bold cyan]2[/] - Monitor resources")
        console.print("  [bold cyan]3[/] - Run command on best device")
        console.print("  [bold cyan]4[/] - Run command on all devices")
        console.print("  [bold cyan]5[/] - Distribution plan")
        console.print("  [bold cyan]6[/] - Transfer file")
        console.print("  [bold cyan]7[/] - Manage groups")
        console.print("  [bold cyan]8[/] - Compare devices")
        console.print("  [bold cyan]9[/] - Command history")
        console.print("  [bold cyan]0[/] - Exit")
        console.print()

    def _handle_choice(self, choice):
        actions = {
            "1": self._list_devices,
            "2": self._monitor,
            "3": self._run_best,
            "4": self._run_all,
            "5": self._plan,
            "6": self._transfer,
            "7": self._manage_groups,
            "8": self._compare,
            "9": self._history,
        }
        action = actions.get(choice)
        if action:
            action()
        Prompt.ask("\nPress Enter to continue")

    def _list_devices(self):
        servers = self.server_mgr.list_servers()
        if not servers:
            console.print("[dim]No devices configured.[/]")
            return
        table = Table(title="Connected Devices", box=box.ROUNDED)
        table.add_column("#", style="dim")
        table.add_column("Name", style="bold")
        table.add_column("Host")
        table.add_column("OS")
        table.add_column("Status")
        for i, name in enumerate(servers, 1):
            info = self.server_mgr.get_server_info(name)
            table.add_row(str(i), name, info["host"], info.get("os_type","?"), info.get("status","?"))
        console.print(table)

    def _monitor(self):
        servers = self.server_mgr.list_servers()
        if not servers:
            console.print("[dim]No devices configured.[/]")
            return
        for name in servers:
            try:
                m = self.monitor.get_all_metrics(name)
                if m is None:
                    console.print(f"[red]{name}: Unable to fetch[/]")
                    continue
                cpu = m.get("cpu_percent") or 0
                ram = (m.get("ram") or {}).get("percent", 0)
                disk = (m.get("disk") or {}).get("percent", 0)
                color = "green" if cpu < 50 else "yellow" if cpu < 80 else "red"
                console.print(f"  [bold]{name}[/]  CPU: [{color}]{cpu}%[/]  RAM: {ram}%  Disk: {disk}%")
            except Exception as e:
                console.print(f"  [red]{name}: {e}[/]")

    def _run_best(self):
        cmd = Prompt.ask("Command to run")
        console.print("[cyan]Running on best device...[/]")
        self.cmd_log.log("run --best", cmd)
        result = self.scheduler.run_on_best(cmd)
        if result["success"]:
            console.print(f"[green]OK on {result['server']}:[/]")
            if result.get("output"):
                console.print(result["output"])
        else:
            console.print(f"[red]Failed: {result.get('error','?')}[/]")

    def _run_all(self):
        cmd = Prompt.ask("Command to run")
        console.print("[cyan]Running on all devices...[/]")
        self.cmd_log.log("run --all", cmd)
        results = self.scheduler.distribute_command(cmd)
        for name, res in results.items():
            icon = "[green]OK[/]" if res["success"] else "[red]FAIL[/]"
            console.print(f"  {icon} {name}")

    def _plan(self):
        try:
            n = int(Prompt.ask("Number of tasks", default="5"))
        except ValueError:
            console.print("[red]Please enter a valid number[/]")
            return
        tasks = [f"task_{i+1}" for i in range(n)]
        plan = self.scheduler.get_distribution_plan(tasks)
        table = Table(title="Distribution Plan", box=box.ROUNDED)
        table.add_column("Device", style="bold")
        table.add_column("Tasks")
        table.add_column("%")
        for name, data in plan.items():
            table.add_row(name, ", ".join(data["tasks"]), f"{data['proportion']}%")
        console.print(table)

    def _transfer(self):
        servers = self.server_mgr.list_servers()
        if not servers:
            console.print("[dim]No devices configured.[/]")
            return
        console.print("  [bold]1[/] Upload file to device")
        console.print("  [bold]2[/] Download file from device")
        ch = Prompt.ask("Choice", choices=["1","2"])
        file_path = Prompt.ask("File path")
        for i, name in enumerate(servers, 1):
            console.print(f"  [{i}] {name}")
        try:
            idx = int(Prompt.ask("Device number")) - 1
        except ValueError:
            console.print("[red]Please enter a valid number[/]")
            return
        if idx < 0 or idx >= len(servers):
            console.print("[red]Invalid choice[/]")
            return
        target = servers[idx]
        from .transfer import FileTransfer
        transfer = FileTransfer(self.server_mgr)
        try:
            if ch == "1":
                remote = Prompt.ask("Remote path", default=file_path)
                r = transfer.upload(target, file_path, remote)
            else:
                local = Prompt.ask("Local save path", default=file_path)
                r = transfer.download(target, file_path, local)
            console.print(f"[green]{r['message']}[/]")
        except Exception as e:
            console.print(f"[red]{e}[/]")

    def _manage_groups(self):
        console.print("  [bold]1[/] List groups")
        console.print("  [bold]2[/] Create group")
        console.print("  [bold]3[/] Add device to group")
        console.print("  [bold]4[/] Remove device from group")
        console.print("  [bold]5[/] Run command on group")
        ch = Prompt.ask("Choice", choices=["1","2","3","4","5"])
        if ch == "1":
            groups = self.groups.list_groups()
            if not groups:
                console.print("[dim]No groups.[/]")
                return
            for g, devs in groups.items():
                console.print(f"  [bold]{g}[/]: {', '.join(devs)}")
        elif ch == "2":
            name = Prompt.ask("Group name")
            self.groups.create_group(name)
            console.print(f"[green]Group '{name}' created.[/]")
        elif ch == "3":
            name = Prompt.ask("Group name")
            dev = Prompt.ask("Device name")
            self.groups.add_to_group(name, dev)
            console.print(f"[green]Added '{dev}' to '{name}'.[/]")
        elif ch == "4":
            name = Prompt.ask("Group name")
            dev = Prompt.ask("Device name")
            self.groups.remove_from_group(name, dev)
            console.print(f"[green]Removed '{dev}' from '{name}'.[/]")
        elif ch == "5":
            name = Prompt.ask("Group name")
            cmd = Prompt.ask("Command")
            devs = self.groups.get_group_devices(name)
            if not devs:
                console.print(f"[red]Group '{name}' is empty or not found.[/]")
                return
            results = self.scheduler.distribute_command(cmd, devs)
            for d, r in results.items():
                icon = "[green]OK[/]" if r["success"] else "[red]FAIL[/]"
                console.print(f"  {icon} {d}")

    def _compare(self):
        servers = self.server_mgr.list_servers()
        if len(servers) < 2:
            console.print("[dim]Need at least 2 devices to compare.[/]")
            return
        table = Table(title="Device Comparison", box=box.ROUNDED)
        table.add_column("Metric", style="bold")
        for name in servers:
            table.add_column(name)
        metrics_map = {}
        for name in servers:
            try:
                m = self.monitor.get_all_metrics(name)
                metrics_map[name] = m
            except Exception:
                metrics_map[name] = None
        cpu_vals = [((m or {}).get("cpu_percent") or "N/A") for m in metrics_map.values()]
        ram_vals = [(((m or {}).get("ram") or {}).get("percent") or "N/A") for m in metrics_map.values()]
        disk_vals = [(((m or {}).get("disk") or {}).get("percent") or "N/A") for m in metrics_map.values()]
        table.add_row("CPU %", *[str(v) for v in cpu_vals])
        table.add_row("RAM %", *[str(v) for v in ram_vals])
        table.add_row("Disk %", *[str(v) for v in disk_vals])
        weights = [self.monitor.calculate_weight(m) for m in metrics_map.values()]
        table.add_row("Weight", *[str(w) for w in weights])
        console.print(table)

    def _history(self):
        entries = self.cmd_log.get_recent(20)
        if not entries:
            console.print("[dim]No command history.[/]")
            return
        table = Table(title="Command History", box=box.ROUNDED)
        table.add_column("Time", style="dim")
        table.add_column("Command")
        for e in entries:
            table.add_row(e["timestamp"][:19], e["command"])
        console.print(table)
