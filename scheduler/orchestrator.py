import argparse
import asyncio
import logging

from rich.box import SIMPLE
from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from agents.discovery import run_discovery
from config.settings import get_settings
from db.models import init_db
from scheduler.budget_guard import BudgetGuard
from scheduler.circuit_breaker import CircuitBreaker
from scheduler.state_machine import reclaim_stale_leases, get_queue_stats

log = logging.getLogger(__name__)
console = Console()
settings = get_settings()

SWEEPER_INTERVAL_S = 300
DISCOVERY_INTERVAL_S = 1800

ALL_STATES = [
    "PENDING", "PROCESSING", "EXTRACTED", "QUALIFIED",
    "CV_DONE", "CL_DONE", "PENDING_REVIEW", "REJECTED",
    "DISQUALIFIED", "ARCHIVED", "FAILED", "DEAD_LETTER",
]


def build_status_panel(budget: BudgetGuard) -> Panel:
    stats = get_queue_stats()

    q_table = Table(title="Queue State", title_style="bold cyan", box=SIMPLE)
    q_table.add_column("State", style="cyan")
    q_table.add_column("Count", justify="right", style="bold white")

    for state in ALL_STATES:
        count = stats.get(state, 0)
        style = ""
        if state == "APPROVED":
            style = "bold green"
        elif state in ("FAILED", "DEAD_LETTER", "REJECTED"):
            style = "red"
        elif state in ("PENDING",):
            style = "white"
        q_table.add_row(f"[{style}]{state}[/{style}]", str(count))

    b_table = Table(title="Daily Budget", title_style="bold yellow", box=SIMPLE)
    b_table.add_column("Resource", style="yellow")
    b_table.add_column("Used", justify="right")
    b_table.add_column("Limit", justify="right")
    b_table.add_column("%", justify="right")

    for resource, data in sorted(budget.report().items()):
        pct_color = "green" if data["pct"] < 80 else "yellow"
        b_table.add_row(
            resource, str(data["used"]), str(data["limit"]),
            f"[{pct_color}]{data['pct']}%[/{pct_color}]",
        )

    cb_table = Table(title="Circuit Breakers", title_style="bold magenta", box=SIMPLE)
    cb_table.add_column("Source", style="magenta")
    cb_table.add_column("State", justify="center")
    cb_table.add_column("Cooldown", justify="right")

    for cb in CircuitBreaker.status_all():
        state_color = "red" if cb["state"] == "OPEN" else "yellow" if cb["state"] == "HALF_OPEN" else "green"
        cd = cb["cooldown_remaining_s"]
        cb_table.add_row(
            cb["source"],
            f"[{state_color}]{cb['state']}[/{state_color}]",
            f"{cd}s" if cd else "-",
        )

    return Panel(
        Columns([q_table, b_table, cb_table], equal=True, expand=True),
        title="[bold]Autonomous Job Pipeline - Phase 1[/bold]",
        border_style="blue",
    )


async def sweeper_loop() -> None:
    while True:
        reclaimed = reclaim_stale_leases()
        if reclaimed:
            console.print(f"[yellow][Sweeper] Reclaimed {reclaimed} stale jobs.[/yellow]")
        await asyncio.sleep(SWEEPER_INTERVAL_S)


async def main(dry_run: bool = False, single_run: bool = False) -> None:
    console.print("[bold blue]Initializing Pipeline[/bold blue]")
    init_db()
    console.print("[green]Database initialized[/green]")

    budget = BudgetGuard()

    if single_run:
        await run_discovery(persist=not dry_run)
        return

    console.print("[green]Entering continuous mode (Ctrl+C to stop)[/green]")

    sweeper_task = asyncio.create_task(sweeper_loop())

    try:
        with Live(refresh_per_second=4, console=console) as live:
            cycle = 0
            while True:
                cycle += 1
                panel = build_status_panel(budget)
                live.update(panel)

                if cycle % 2 == 0:
                    await run_discovery(persist=not dry_run)
                    budget.print_report()

                await asyncio.sleep(DISCOVERY_INTERVAL_S)
    except KeyboardInterrupt:
        console.print("[bold red]Pipeline stopped by user.[/bold red]")
    finally:
        sweeper_task.cancel()
        try:
            await sweeper_task
        except asyncio.CancelledError:
            pass


def run() -> None:
    parser = argparse.ArgumentParser(description="Job Pipeline Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Run without persisting jobs to DB")
    parser.add_argument("--once", action="store_true", help="Run a single discovery cycle and exit")
    parser.add_argument("--phase", type=int, default=1, help="Pipeline phase to run (default: 1)")
    args = parser.parse_args()

    asyncio.run(main(dry_run=args.dry_run, single_run=args.once))


if __name__ == "__main__":
    from utils.logging import setup_logging

    setup_logging(settings.log_level)
    run()
