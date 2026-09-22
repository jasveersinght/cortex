-- Hands-owned tables. Safe to run repeatedly (IF NOT EXISTS).
-- The Brain's tables (assets, lens_scores, lessons_learned) are NEVER altered:
-- Hands only reads assets, and appends rows to lessons_learned.

-- The human approval receipt. body_hash freezes exactly what the human approved.
CREATE TABLE IF NOT EXISTS approval_records (
    asset_id     TEXT PRIMARY KEY,
    approved_by  TEXT NOT NULL,
    approved_at  TEXT NOT NULL,
    body_hash    TEXT NOT NULL,
    note         TEXT,
    source       TEXT NOT NULL DEFAULT 'reviewer'
);

-- Media (image / video) attached to an asset, with a public URL for the provider.
CREATE TABLE IF NOT EXISTS asset_media (
    asset_id      TEXT PRIMARY KEY,
    media_url     TEXT NOT NULL,
    media_type    TEXT NOT NULL,             -- image | video
    ai_generated  INTEGER NOT NULL DEFAULT 0,
    source        TEXT,
    created_at    TEXT NOT NULL
);

-- One row per (asset, platform). This is the publishing queue.
CREATE TABLE IF NOT EXISTS publish_jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id         TEXT NOT NULL,
    platform         TEXT NOT NULL,
    brand            TEXT,
    region           TEXT,
    status           TEXT NOT NULL DEFAULT 'queued',
      -- queued | publishing | scheduled | published | retry | failed | blocked | needs_review | cancelled
    block_code       TEXT,                   -- approval | integrity | platform_fit | safety (why it was blocked)
    scheduled_for    TEXT,
    provider         TEXT,
    external_post_id TEXT,
    external_url     TEXT,
    attempts         INTEGER NOT NULL DEFAULT 0,
    max_attempts     INTEGER NOT NULL DEFAULT 4,
    next_attempt_at  TEXT,
    submitted_at     TEXT,                   -- set just BEFORE the provider call (crash-safety marker)
    last_error       TEXT,
    hashtags_json    TEXT,
    body_hash        TEXT,
    final_text       TEXT,
    first_comment    TEXT,
    slot_reason      TEXT,
    preflight_json   TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    published_at     TEXT,
    UNIQUE (asset_id, platform)
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON publish_jobs (status, next_attempt_at);
CREATE INDEX IF NOT EXISTS idx_jobs_platform ON publish_jobs (platform, scheduled_for);

-- Engagement snapshots (never overwritten, so trends can be analysed).
CREATE TABLE IF NOT EXISTS post_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL,
    fetched_at      TEXT NOT NULL,
    impressions     REAL,
    reach           REAL,
    views           REAL,
    likes           REAL,
    comments        REAL,
    shares          REAL,
    saves           REAL,
    clicks          REAL,
    engagement_rate REAL,
    raw_json        TEXT
);
CREATE INDEX IF NOT EXISTS idx_metrics_job ON post_metrics (job_id, fetched_at);

-- The 4 performance lenses per published post.
CREATE TABLE IF NOT EXISTS performance_scores (
    job_id           INTEGER PRIMARY KEY,
    engagement_score REAL,
    reach_score      REAL,
    conversion_score REAL,
    timing_score     REAL,
    total_score      REAL NOT NULL,
    tier             TEXT NOT NULL,          -- top_performer | solid | weak | underperforming
    explain_json     TEXT,
    metrics_id       INTEGER,
    computed_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    actor    TEXT NOT NULL,
    event    TEXT NOT NULL,
    job_id   INTEGER,
    asset_id TEXT,
    detail   TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log (ts);

CREATE TABLE IF NOT EXISTS system_flags (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
