"""SQLite connection management and schema initialization."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from src.infrastructure.config import get_settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    tax_id TEXT NOT NULL,
    tax_id_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    submitted_documents TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def closing_connection() -> Iterator[sqlite3.Connection]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Create the database schema if it does not already exist."""
    with closing_connection() as conn:
        conn.execute(_SCHEMA)
        conn.commit()
