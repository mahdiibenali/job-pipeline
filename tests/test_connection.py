import pytest

from db.connection import close_all, get_connection


def test_get_connection_returns_same_in_thread():
    conn1 = get_connection()
    conn2 = get_connection()
    assert conn1 is conn2


def test_connection_has_wal():
    conn = get_connection()
    row = conn.execute("PRAGMA journal_mode").fetchone()
    assert row[0].upper() == "WAL"


def test_connection_has_foreign_keys():
    conn = get_connection()
    row = conn.execute("PRAGMA foreign_keys").fetchone()
    assert row[0] == 1


def test_close_all_reconnects():
    conn = get_connection()
    assert conn is not None
    close_all()
    conn2 = get_connection()
    assert conn2 is not None
    assert conn2 is not conn
