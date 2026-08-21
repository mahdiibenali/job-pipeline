from scheduler.budget_guard import BudgetGuard


class TestBudgetGuard:
    def test_consume_returns_true_when_budget_available(self):
        guard = BudgetGuard()
        assert guard.consume("httpx_requests") is True

    def test_consume_returns_false_when_exhausted(self):
        guard = BudgetGuard()
        for _ in range(2000):
            guard.consume("httpx_requests")
        assert guard.consume("httpx_requests") is False

    def test_remaining(self):
        guard = BudgetGuard()
        guard.consume("gemini_calls", amount=10)
        remaining = guard.remaining("gemini_calls")
        assert remaining <= 40

    def test_unknown_resource_blocks(self):
        guard = BudgetGuard()
        assert guard.consume("nonexistent_resource") is False

    def test_report_includes_all_resources(self):
        guard = BudgetGuard()
        report = guard.report()
        assert "gemini_calls" in report
        assert "httpx_requests" in report
        for resource, data in report.items():
            assert "used" in data
            assert "limit" in data
            assert "pct" in data

    def test_report_shows_usage(self):
        guard = BudgetGuard()
        guard.consume("gemini_calls", amount=5)
        report = guard.report()
        assert report["gemini_calls"]["used"] == 5
        assert report["gemini_calls"]["limit"] == 50
