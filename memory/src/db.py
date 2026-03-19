"""Database connection management and utility helpers."""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory.db")


def get_connection(db_path=None):
    """Get a SQLite connection with row factory enabled."""
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_session(db_path=None):
    """Context manager for database operations with auto-commit/rollback."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dictionary."""
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows):
    """Convert a list of sqlite3.Row objects to list of dicts."""
    return [dict(r) for r in rows]


def execute_query(query, params=(), db_path=None):
    """Execute a query and return all results as dicts."""
    with db_session(db_path) as conn:
        cursor = conn.execute(query, params)
        return rows_to_dicts(cursor.fetchall())


def execute_insert(query, params=(), db_path=None):
    """Execute an insert and return the last row id."""
    with db_session(db_path) as conn:
        cursor = conn.execute(query, params)
        return cursor.lastrowid
