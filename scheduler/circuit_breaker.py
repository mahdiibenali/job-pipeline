import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from config.settings import get_settings
from db.connection import get_connection

log = logging.getLogger(__name__)
settings = get_settings()

SOURCE_COOLDOWNS: dict[str, int] = {
    "linkedin": settings.cb_cooldown_linkedin,
    "wellfound": settings.cb_cooldown_wellfound,
    "weworkremotely": settings.cb_cooldown_weworkremotely,
    "adzuna": settings.cb_cooldown_adzuna,
    "rss": settings.cb_cooldown_rss,
}
FAILURE_THRESHOLD = settings.cb_failure_threshold
DEFAULT_COOLDOWN = settings.cb_default_cooldown_hours


class CircuitOpenError(Exception):
    pass


@dataclass
class CircuitState:
    state: str
    failures: int
    cooldown_until: float


class CircuitBreaker:
    def __init__(self, source: str) -> None:
        self.source = source
        self.cooldown = SOURCE_COOLDOWNS.get(source, DEFAULT_COOLDOWN) * 3600
        self._ensure_row()

    def _ensure_row(self) -> None:
        conn = get_connection()
        conn.execute("INSERT OR IGNORE INTO circuit_breakers (source) VALUES (?)", (self.source,))
        conn.commit()

    def _get_state(self) -> CircuitState:
        conn = get_connection()
        row = conn.execute(
            "SELECT state, failures, cooldown_until FROM circuit_breakers WHERE source=?",
            (self.source,),
        ).fetchone()
        return CircuitState(row["state"], row["failures"], row["cooldown_until"])

    def _set(self, state: str, failures: int, cooldown_until: float) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE circuit_breakers "
            "SET state=?, failures=?, cooldown_until=?, last_updated=? "
            "WHERE source=?",
            (state, failures, cooldown_until, time.time(), self.source),
        )
        conn.commit()

    def is_available(self) -> bool:
        cs = self._get_state()
        now = time.time()

        if cs.state == "CLOSED":
            return True

        if cs.state == "OPEN":
            if now >= cs.cooldown_until:
                self._set("HALF_OPEN", cs.failures, 0)
                log.info("[CB] %s: OPEN -> HALF_OPEN (probe allowed)", self.source)
                return True
            return False

        if cs.state == "HALF_OPEN":
            return True

        return False

    def record_success(self) -> None:
        cs = self._get_state()
        if cs.state != "CLOSED":
            log.info("[CB] %s: reset to CLOSED after success", self.source)
        self._set("CLOSED", 0, 0)

    def record_failure(self, error: Exception | None = None) -> None:
        cs = self._get_state()
        new_failures = cs.failures + 1

        if new_failures >= FAILURE_THRESHOLD:
            until = time.time() + self.cooldown
            self._set("OPEN", new_failures, until)
            until_str = time.strftime("%H:%M:%S", time.localtime(until))
            log.warning(
                "[CB] %s: TRIPPED (%d failures). Cooldown until %s",
                self.source, new_failures, until_str,
            )
        else:
            self._set(cs.state, new_failures, cs.cooldown_until)
            log.debug("[CB] %s: failure #%d", self.source, new_failures)

    async def call(self, fn: Callable, *args: Any, timeout: float = 60.0, **kwargs: Any) -> Any:
        if not self.is_available():
            raise CircuitOpenError(f"Circuit breaker OPEN for source: {self.source}")

        try:
            result = await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise

    @classmethod
    def status_all(cls) -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT source, state, failures, cooldown_until FROM circuit_breakers"
        ).fetchall()
        result = []
        now = time.time()
        for row in rows:
            remaining = max(0.0, row["cooldown_until"] - now) if row["cooldown_until"] else 0.0
            result.append({
                "source": row["source"],
                "state": row["state"],
                "failures": row["failures"],
                "cooldown_remaining_s": round(remaining, 1),
            })
        return result
