"""SQLite access. Hands shares the Brain's database file (DB_PATH)."""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings
from .utils import to_iso, utcnow

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or get_settings().db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")  # lets the API and worker share the file
    except sqlite3.DatabaseError:  # pragma: no cover
        pass
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Explicit write transaction (the connection is in autocommit mode)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> dict[str, dict[str, Any]]:
    return {
        r["name"]: {"type": (r["type"] or "").upper(), "pk": bool(r["pk"]), "notnull": bool(r["notnull"])}
        for r in conn.execute(f"PRAGMA table_info({table})")
    }


def insert_dynamic(conn: sqlite3.Connection, table: str, data: dict[str, Any]) -> Any:
    """Insert into a table whose exact columns we do not control (the Brain's tables).

    - keeps only columns that really exist,
    - fills created_at if the table has it,
    - if `id` is not an INTEGER PRIMARY KEY (auto-increment), generates a UUID.
    Returns the new row id.
    """
    cols = table_columns(conn, table)
    row = {k: v for k, v in data.items() if k in cols}
    if "created_at" in cols and "created_at" not in row:
        row["created_at"] = to_iso(utcnow())
    if "id" in cols and "id" not in row:
        id_col = cols["id"]
        if not (id_col["pk"] and id_col["type"] == "INTEGER"):
            row["id"] = uuid.uuid4().hex
    names = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    cur = conn.execute(f"INSERT INTO {table} ({names}) VALUES ({marks})", tuple(row.values()))
    return row.get("id", cur.lastrowid)


def get_flag(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM system_flags WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_flag(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO system_flags (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, to_iso(utcnow())),
    )


def get_asset(conn: sqlite3.Connection, asset_id: Any) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM assets WHERE CAST(id AS TEXT) = ?", (str(asset_id),)).fetchone()
