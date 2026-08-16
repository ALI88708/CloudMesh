from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.live import Live
from rich import box
import time


console = Console()


def _status_color(status):
    if status in ("connected", "ok"):
        return "green"
    elif status in ("unknown", "disconnected"):
        return "yellow"
    else:
        return "red"


def _usage_color(percent):
    if percent is None:
        return "white"
    if percent < 50:
        return "green"
    elif percent < 80:
        return "yellow"
    else:
        return "red"


def _usage_bar(percent):
    if percent is None:
        return "[white]???[/]"
    filled = int(percent / 5)
    empty = 20 - filled
    color = _usage_color(percent)
    return f"[{color}]{'█' * filled}{'░' * empty}[/] {percent}%"


class Dashboard:
    def __init__(self, scheduler):
        self.scheduler = scheduler

    def build_server_table(self, servers_data):
        table = Table(
            title="CloudMesh - Server Status",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="bright_blue",
        )
        table.add_column("Server", style="bold white", min_width=15)
        table.add_column("Status", min_width=10)
        table.add_column("CPU", min_width=25)
        table.add_column("RAM", min_width=25)
        table.add_column("Disk", min_width=25)
        table.add_column("Weight", min_width=8)

        for name, data in servers_data.items():
            status = data.get("status", "unknown")
            metrics = data.get("metrics")
            weight = data.get("weight", 0)

            sc = _status_color(status)
            status_text = f"[{sc}]{status.upper()}[/]"

            if metrics is None:
                cpu_bar = "[dim]N/A[/]"
                ram_bar = "[dim]N/A[/]"
                disk_bar = "[dim]N/A[/]"
            else:
                cpu_pct = metrics.get("cpu_percent")
                ram = metrics.get("ram") or {}
                disk = metrics.get("disk") or {}
                cpu_bar = _usage_bar(cpu_pct)
                ram_bar = _usage_bar(ram.get("percent"))
                disk_bar = _usage_bar(disk.get("percent"))

            table.add_row(name, status_text, cpu_bar, ram_bar, disk_bar, f"[bold]{weight}[/]")

        return table

    def build_summary_panel(self, summary):
        lines = []
        lines.append(f"[bold]Total Servers:[/] {summary['total_servers']}")
        lines.append(f"[bold green]Connected:[/] {summary['connected_servers']}")
        lines.append(f"[bold cyan]Free CPU:[/] {summary['total_cpu_free']}%")
        lines.append(f"[bold cyan]Free RAM:[/] {summary['total_ram_free_gb']} GB")
        lines.append(f"[bold cyan]Free Disk:[/] {summary['total_disk_free_gb']} GB")

        return Panel(
            "\n".join(lines),
            title="[bold bright_blue]Resource Summary[/]",
            border_style="bright_blue",
            padding=(1, 2),
        )

    def build_distribution_panel(self, plan):
        lines = []
        for name, data in plan.items():
            tasks = data.get("tasks", [])
            proportion = data.get("proportion", 0)
            lines.append(f"[bold]{name}[/] ({proportion}%): {len(tasks)} tasks")
            for t in tasks:
                lines.append(f"  [dim]> {t}[/]")

        return Panel(
            "\n".join(lines) if lines else "[dim]No tasks scheduled[/]",
            title="[bold bright_blue]Task Distribution[/]",
            border_style="bright_blue",
            padding=(1, 2),
        )

    def render_full(self, plan=None):
        console.clear()
        summary = self.scheduler.get_status_summary()
        console.print()
        console.print(
            Panel(
                "[bold bright_blue]CloudMesh Dashboard[/] - Multi-Cloud Resource Manager",
                border_style="bright_blue",
            )
        )
        console.print()

        table = self.build_server_table(summary["servers"])
        console.print(table)
        console.print()

        summary_panel = self.build_summary_panel(summary)
        console.print(summary_panel)

        if plan:
            console.print()
            dist_panel = self.build_distribution_panel(plan)
            console.print(dist_panel)

        console.print()

    def render_live(self, refresh_interval=5):
        try:
            with Live(console=console, refresh_per_second=1) as live:
                while True:
                    summary = self.scheduler.get_status_summary()
                    renderables = []

                    renderables.append(
                        Panel(
                            "[bold bright_blue]CloudMesh Dashboard[/] (Live) - Press Ctrl+C to exit",
                            border_style="bright_blue",
                        )
                    )

                    table = self.build_server_table(summary["servers"])
                    renderables.append(table)
                    renderables.append(self.build_summary_panel(summary))

                    layout = Layout()
                    layout.split_column(*[Layout(r) for r in renderables])
                    live.update(layout)
                    time.sleep(refresh_interval)
        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard closed.[/]")
