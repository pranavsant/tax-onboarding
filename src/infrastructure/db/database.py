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

-- investor_profiles stores the comparison baseline used during tax
-- onboarding to detect stale forms, mismatches, or missing certifications.
--
-- Column reference
-- ----------------
-- profile_id            UUID surrogate key (TEXT, not NULL).
-- full_name             Legal name as shown on IRS documents (TEXT, not NULL).
-- address               Street / mailing address (TEXT, not NULL).
-- investor_type         'us_person' | 'foreign_person'  (TEXT, not NULL).
-- tax_status            'PENDING' | 'VERIFIED' | 'EXPIRED' | 'MISSING'
--                       (TEXT, not NULL).
-- country               Country of residence / citizenship.  Required for
--                       foreign investors; NULL for US investors who have
--                       not explicitly set it (TEXT, nullable).
-- last_form_on_file     Most-recently verified IRS form code:
--                       'W-9' | 'W-8BEN' | NULL if none on file (TEXT, nullable).
-- last_form_signed_date Date the last form was signed, stored as an ISO 8601
--                       string 'YYYY-MM-DD'. NULL when no form is on file
--                       (TEXT, nullable).
-- foreign_tin           Foreign taxpayer identification number — populated
--                       for W-8BEN filers only (TEXT, nullable).
-- treaty_country        Country invoked in a Part II treaty claim on the
--                       W-8BEN (TEXT, nullable).
-- created_at            Row-creation timestamp as an ISO 8601 string
--                       (TEXT, not NULL).
CREATE TABLE IF NOT EXISTS investor_profiles (
    profile_id            TEXT PRIMARY KEY,
    full_name             TEXT NOT NULL,
    address               TEXT NOT NULL,
    investor_type         TEXT NOT NULL,
    tax_status            TEXT NOT NULL,
    country               TEXT,
    last_form_on_file     TEXT,
    last_form_signed_date TEXT,
    foreign_tin           TEXT,
    treaty_country        TEXT,
    created_at            TEXT NOT NULL
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
        conn.executescript(_SCHEMA)
        conn.commit()
