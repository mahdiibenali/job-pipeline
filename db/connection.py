import sqlite3
import threading
from pathlib import Path

_conns: threading.local = threading.local()
_db_path: Path | None = None


def configure(db_path: Path) -> None:
    global _db_path
    _db_path = db_path


def get_connection() -> sqlite3.Connection:
    if not _db_path:
        raise RuntimeError("DB not configured: call configure(db_path) first")

    conn: sqlite3.Connection | None = getattr(_conns, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(_db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _conns.conn = conn
    return conn


def close_all() -> None:
    conn: sqlite3.Connection | None = getattr(_conns, "conn", None)
    if conn:
        conn.close()
        _conns.conn = None
