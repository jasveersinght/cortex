"""
db.py
SQLite database setup and connection helper for the JA Assure compliance pipeline.

Tables:
  assets           -> every generated piece of content + its final tier/score
  lens_scores      -> the 4 individual compliance lens results per asset
  lessons_learned  -> reasons captured when a human edits/rejects an asset
"""

import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "ja_assure.db")


def get_connection():
    """Return a sqlite3 connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't already exist. Safe to call every run."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,              -- 'Jade', 'Jaguar Transit', 'DoctorShield'
            platform TEXT NOT NULL,           -- 'LinkedIn', 'Instagram', 'X'
            content_type TEXT NOT NULL,       -- 'caption', 'carousel', 'script', etc.
            body_text TEXT NOT NULL,
            region TEXT DEFAULT 'SG',         -- SG, MY, HK, ID, TH
            status TEXT DEFAULT 'pending',    -- pending | approved | rejected | scheduled
            tier TEXT,                        -- highly_recommended | recommended_review | vigilant | suspicious
            confidence_score INTEGER,         -- 0-100 aggregated score
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lens_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            lens_name TEXT NOT NULL,          -- claims | regulatory | brand | accuracy
            score INTEGER NOT NULL,           -- 0-100
            flagged_phrases TEXT,             -- comma-separated or JSON string
            reason TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons_learned (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER,
            tag TEXT NOT NULL,                -- 'too salesy', 'inaccurate claim', 'off-brand tone', etc.
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database ready at {DB_PATH}")


if __name__ == "__main__":
    init_db()