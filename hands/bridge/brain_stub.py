"""Minimal copy of the Brain's tables, as documented in the project-1-brain README.

Used ONLY by the demo and the tests, and only when the real tables are missing
(CREATE TABLE IF NOT EXISTS never touches your real Brain database).
"""
from __future__ import annotations

import sqlite3

BRAIN_STUB_SQL = """
CREATE TABLE IF NOT EXISTS assets (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    brand            TEXT NOT NULL,
    platform         TEXT,
    content_type     TEXT,
    region           TEXT,
    body_text        TEXT NOT NULL,
    status           TEXT DEFAULT 'pending',
    tier             TEXT,
    confidence_score REAL,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS lens_scores (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER,
    lens_name TEXT,
    score    REAL,
    reason   TEXT
);
CREATE TABLE IF NOT EXISTS lessons_learned (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id   INTEGER,
    tag        TEXT,
    note       TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def ensure_brain_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(BRAIN_STUB_SQL)
