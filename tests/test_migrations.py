from db.connection import get_connection
from db.migrations import _get_current_version


def test_migration_applied():
    version = _get_current_version()
    assert version == "1.0"


def test_all_tables_exist():
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = [row["name"] for row in tables]

    expected = [
        "applications",
        "audit_log",
        "budget_counters",
        "circuit_breakers",
        "companies",
        "dead_letter_queue",
        "job_details",
        "jobs",
        "system_config",
    ]
    for name in expected:
        assert name in names, f"Missing table: {name}"


def test_indexes_exist():
    conn = get_connection()
    indexes = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    ).fetchall()
    names = [row["name"] for row in indexes]

    expected_indexes = [
        "idx_jobs_state",
        "idx_jobs_domain",
        "idx_jobs_fit_score",
        "idx_companies_domain",
        "idx_audit_entity",
        "idx_dlq_job",
    ]
    for name in expected_indexes:
        assert name in names, f"Missing index: {name}"


def test_default_config_values():
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM system_config").fetchall()
    config = {row["key"]: row["value"] for row in rows}

    assert config.get("schema_version") == "1.0"
    assert config.get("min_fit_score") == "0.35"
    assert config.get("daily_app_cap") == "20"
    assert config.get("cl_cache_ttl_days") == "14"
