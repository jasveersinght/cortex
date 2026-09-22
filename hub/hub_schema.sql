-- Hub-owned local tables (in the shared SQLite file). Brain tables are never altered.

-- Writes to Supabase that could not be delivered yet (Supabase down / offline demo).
CREATE TABLE IF NOT EXISTS hub_outbox (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    target       TEXT NOT NULL,          -- content | compliance
    table_name   TEXT NOT NULL,
    on_conflict  TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT,
    created_at   TEXT NOT NULL
);

-- What has already been mirrored to Supabase, so sync is idempotent.
CREATE TABLE IF NOT EXISTS hub_mirror (
    kind         TEXT NOT NULL,          -- review | decision | lesson
    local_id     TEXT NOT NULL,
    fingerprint  TEXT NOT NULL,
    synced_at    TEXT NOT NULL,
    PRIMARY KEY (kind, local_id)
);

-- Links a content generation to the Brain asset rows created from it.
CREATE TABLE IF NOT EXISTS hub_links (
    generation_id TEXT NOT NULL,
    asset_id      TEXT NOT NULL,
    platform      TEXT,
    created_at    TEXT NOT NULL,
    PRIMARY KEY (generation_id, asset_id)
);
