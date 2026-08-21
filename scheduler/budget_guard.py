import logging
from datetime import datetime, timezone

from config.settings import get_settings
from db.connection import get_connection

log = logging.getLogger(__name__)
settings = get_settings()

DAILY_BUDGETS: dict[str, int] = {
    "brave_api": settings.budget_brave,
    "serp_api": settings.budget_serp,
    "gemini_calls": settings.budget_gemini,
    "adzuna_calls": settings.budget_adzuna,
    "playwright_sessions": settings.budget_playwright,
    "smtp_handshakes": settings.budget_smtp,
    "httpx_requests": settings.budget_httpx,
    "ddg_queries": settings.budget_ddg,
}


class BudgetGuard:
    def __init__(self) -> None:
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = get_connection()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS budget_counters ("
            "    budget_date TEXT NOT NULL,"
            "    resource    TEXT NOT NULL,"
            "    used        INTEGER DEFAULT 0,"
            "    PRIMARY KEY (budget_date, resource)"
            ")"
        )
        conn.commit()

    def _today_str(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def remaining(self, resource: str) -> int:
        conn = get_connection()
        today = self._today_str()
        row = conn.execute(
            "SELECT used FROM budget_counters WHERE budget_date=? AND resource=?",
            (today, resource),
        ).fetchone()
        used = row["used"] if row else 0
        limit = DAILY_BUDGETS.get(resource, 0)
        return max(0, limit - used)

    def consume(self, resource: str, amount: int = 1) -> bool:
        conn = get_connection()
        today = self._today_str()
        limit = DAILY_BUDGETS.get(resource)

        if limit is None:
            log.warning("[BudgetGuard] Unknown resource: '%s'. Blocking.", resource)
            return False

        conn.execute(
            "INSERT INTO budget_counters (budget_date, resource, used) "
            "VALUES (?, ?, 0) "
            "ON CONFLICT (budget_date, resource) DO NOTHING",
            (today, resource),
        )

        row = conn.execute(
            "SELECT used FROM budget_counters WHERE budget_date=? AND resource=?",
            (today, resource),
        ).fetchone()
        used = row["used"] if row else 0

        if used >= limit:
            log.warning("[BudgetGuard] %s: budget exhausted (%d/%d). Block.", resource, used, limit)
            return False

        conn.execute(
            "UPDATE budget_counters SET used = used + ? WHERE budget_date=? AND resource=?",
            (amount, today, resource),
        )
        conn.commit()
        log.debug("[BudgetGuard] %s: consumed %d. Remaining: %d", resource, amount, limit - used - amount)
        return True

    def report(self) -> dict[str, dict]:
        conn = get_connection()
        today = self._today_str()
        rows = conn.execute(
            "SELECT resource, used FROM budget_counters WHERE budget_date=?", (today,)
        ).fetchall()

        usage = {}
        for row in rows:
            resource = row["resource"]
            used = row["used"]
            limit = DAILY_BUDGETS.get(resource, 0)
            pct = round((used / limit * 100), 1) if limit else 0.0
            usage[resource] = {"used": used, "limit": limit, "pct": pct}

        for resource, limit in DAILY_BUDGETS.items():
            if resource not in usage:
                usage[resource] = {"used": 0, "limit": limit, "pct": 0.0}

        return usage

    def print_report(self) -> None:
        from rich.console import Console
        from rich.table import Table

        report = self.report()
        console = Console()
        table = Table(title=f"Budget Report {self._today_str()}", show_lines=True)
        table.add_column("Resource", style="cyan")
        table.add_column("Used", justify="right")
        table.add_column("Limit", justify="right")
        table.add_column("Remaining", justify="right")
        table.add_column("Usage %", justify="right")

        for resource, data in sorted(report.items()):
            remaining = data["limit"] - data["used"]
            pct_str = f"{data['pct']}%"
            style = "green" if remaining > 0 else "yellow"
            table.add_row(
                resource,
                str(data["used"]),
                str(data["limit"]),
                str(remaining),
                f"[{style}]{pct_str}[/{style}]",
            )

        console.print(table)
