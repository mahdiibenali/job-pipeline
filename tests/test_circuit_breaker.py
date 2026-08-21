import time

from db.connection import get_connection
from scheduler.circuit_breaker import CircuitBreaker


class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test_source")
        assert cb.is_available() is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test_open")
        for i in range(5):
            cb.record_failure(Exception(f"error_{i}"))

        assert cb.is_available() is False

    def test_allows_probe_in_half_open(self):
        cb = CircuitBreaker("test_half_open")
        for i in range(5):
            cb.record_failure(Exception(f"e{i}"))

        conn = get_connection()
        conn.execute(
            "UPDATE circuit_breakers SET cooldown_until=? WHERE source=?",
            (time.time() - 1, "test_half_open"),
        )
        conn.commit()

        assert cb.is_available() is True

    def test_records_success_closes_breaker(self):
        cb = CircuitBreaker("test_success")
        for i in range(5):
            cb.record_failure(Exception(f"e{i}"))

        cb.record_success()
        assert cb.is_available() is True

    def test_status_all(self):
        _ = CircuitBreaker("status_test")
        statuses = CircuitBreaker.status_all()
        sources = [s["source"] for s in statuses]
        assert "status_test" in sources

    def test_is_available_false_when_open(self):
        cb = CircuitBreaker("test_raise")
        for i in range(5):
            cb.record_failure(Exception(f"e{i}"))

        assert cb.is_available() is False
