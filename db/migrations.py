import logging

from db.connection import get_connection

log = logging.getLogger(__name__)

_MIGRATIONS: list[tuple[str, str]] = [
    ("1.0", """
        CREATE TABLE IF NOT EXISTS companies (
            company_id      TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            domain          TEXT UNIQUE NOT NULL,
            ats_type        TEXT,
            ats_slug        TEXT,
            robots_allowed  INTEGER DEFAULT 1,
            robots_cached_at TEXT,
            size_estimate   TEXT,
            country         TEXT,
            gdpr_region     INTEGER DEFAULT 0,
            last_visited_at TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jobs (
            job_id          TEXT PRIMARY KEY,
            fingerprint     TEXT UNIQUE NOT NULL,
            title           TEXT NOT NULL,
            company         TEXT NOT NULL,
            domain          TEXT NOT NULL,
            url             TEXT NOT NULL,
            source          TEXT NOT NULL,
            region          TEXT,
            country         TEXT,
            state           TEXT NOT NULL DEFAULT 'PENDING',
            discovery_score REAL DEFAULT 0.0,
            fit_score       REAL,
            visa_signal     TEXT,
            retry_count     INTEGER DEFAULT 0,
            lease_expires_at TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS job_details (
            job_id              TEXT PRIMARY KEY REFERENCES jobs(job_id),
            description         TEXT,
            skills              TEXT,
            experience_level    TEXT,
            tech_stack          TEXT,
            implicit_reqs       TEXT,
            red_flags           TEXT,
            ats_type            TEXT,
            extraction_method   TEXT,
            extracted_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS applications (
            app_id          TEXT PRIMARY KEY,
            job_id          TEXT NOT NULL REFERENCES jobs(job_id),
            cv_path         TEXT,
            cl_path         TEXT,
            cv_hash         TEXT,
            skill_gaps      TEXT,
            state           TEXT DEFAULT 'PENDING_REVIEW',
            human_approved  INTEGER,
            approved_at     TEXT,
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS system_config (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id   TEXT NOT NULL,
            action      TEXT NOT NULL,
            actor       TEXT NOT NULL,
            payload     TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS dead_letter_queue (
            dlq_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id      TEXT NOT NULL,
            category    TEXT NOT NULL,
            error_trace TEXT,
            agent       TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS circuit_breakers (
            source          TEXT PRIMARY KEY,
            state           TEXT DEFAULT 'CLOSED',
            failures        INTEGER DEFAULT 0,
            cooldown_until  REAL DEFAULT 0,
            last_updated    REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS budget_counters (
            budget_date TEXT NOT NULL,
            resource    TEXT NOT NULL,
            used        INTEGER DEFAULT 0,
            PRIMARY KEY (budget_date, resource)
        );
    """),
]


def _get_current_version() -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM system_config WHERE key='schema_version'").fetchone()
    return row["value"] if row else "0.0"


def _set_version(version: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO system_config (key, value) VALUES ('schema_version', ?)",
        (version,),
    )


_INDEXES_SQL = """
    CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
    CREATE INDEX IF NOT EXISTS idx_jobs_domain ON jobs(domain);
    CREATE INDEX IF NOT EXISTS idx_jobs_fit_score ON jobs(fit_score);
    CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
    CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_dlq_job ON dead_letter_queue(job_id);
"""


def migrate() -> None:
    conn = get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS system_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    current = _get_current_version()

    for version, sql in _MIGRATIONS:
        if version > current:
            log.info("[Migrate] Applying schema version %s", version)
            conn.executescript(sql)
            _set_version(version)
            log.info("[Migrate] Schema at version %s", version)

    conn.executescript(_INDEXES_SQL)

    conn.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)",
        ("prompt_template_version", "1.0"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)",
        ("min_fit_score", "0.35"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)",
        ("daily_app_cap", "20"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO system_config (key, value) VALUES (?, ?)",
        ("cl_cache_ttl_days", "14"),
    )
    conn.commit()
