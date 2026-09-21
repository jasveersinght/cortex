-- ============================================================
-- JA Assure Discover Agent — Baseline Migration
-- Creates all tables required by the Research Agent.
-- Safe to apply to a fresh Supabase PostgreSQL database.
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ──────────────────────────────────────────────────────────────
-- 1. competitors
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS competitors (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    brand         TEXT NOT NULL,
    market        TEXT NOT NULL,
    domain        TEXT,
    discovered    BOOLEAN NOT NULL DEFAULT false,
    confirmed     BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_competitors_name_brand_market_key UNIQUE (name, brand, market)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_competitors_name_brand_market
    ON competitors (lower(name), brand, market);
CREATE INDEX IF NOT EXISTS idx_competitors_brand_market
    ON competitors (brand, market);

-- ──────────────────────────────────────────────────────────────
-- 2. research_runs
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_runs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand               TEXT NOT NULL,
    market              TEXT NOT NULL,
    research_type       TEXT NOT NULL,
    objective           TEXT,
    status              TEXT NOT NULL DEFAULT 'IDLE'
                        CHECK (status IN (
                            'IDLE','CHECKING_CACHE','PLANNING','RETRIEVING',
                            'NORMALIZING','FILTERING','DETECTING_CHANGES',
                            'ANALYZING','COMPLETED','SKIPPED',
                            'PARTIAL_FAILURE','FAILED'
                        )),
    request_hash        TEXT NOT NULL,
    plan                JSONB,
    lookback_days       INT NOT NULL DEFAULT 30,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,

    -- Derived metrics
    sources_checked     INT NOT NULL DEFAULT 0,
    unique_sources      INT NOT NULL DEFAULT 0,
    relevant_sources    INT NOT NULL DEFAULT 0,
    new_findings        INT NOT NULL DEFAULT 0,
    changed_findings    INT NOT NULL DEFAULT 0,
    unchanged_findings  INT NOT NULL DEFAULT 0,
    tavily_calls        INT NOT NULL DEFAULT 0,
    groq_calls          INT NOT NULL DEFAULT 0,
    dropped_findings    INT NOT NULL DEFAULT 0,
    confidence_score    INT,
    cache_hit           BOOLEAN NOT NULL DEFAULT false,
    error_message       TEXT,
    metadata            JSONB DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_runs_brand_market_type_completed
    ON research_runs (brand, market, research_type, completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_runs_request_hash
    ON research_runs (request_hash);
CREATE INDEX IF NOT EXISTS idx_runs_status
    ON research_runs (status);

-- ──────────────────────────────────────────────────────────────
-- 3. research_evidence
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_evidence (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id   UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    evidence_ref      TEXT NOT NULL,               -- "evidence_001"
    source_type       TEXT,
    source_name       TEXT,
    source_quality    INT NOT NULL CHECK (source_quality BETWEEN 1 AND 6),
    title             TEXT,
    url               TEXT NOT NULL,                -- display URL
    normalized_url    TEXT NOT NULL,
    url_hash          TEXT NOT NULL,
    content_hash      TEXT NOT NULL,
    content           TEXT,
    published_at      TIMESTAMPTZ,
    retrieved_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    market            TEXT,
    competitor        TEXT,
    topic             TEXT,
    query             TEXT,
    tavily_operation  TEXT,
    relevance         TEXT NOT NULL CHECK (relevance IN ('RELEVANT','UNCERTAIN','IRRELEVANT')),
    relevance_score   NUMERIC(4,3) DEFAULT 0.000,
    change_status     TEXT NOT NULL DEFAULT 'NEW',
    metadata          JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_run_ref
    ON research_evidence (research_run_id, evidence_ref);
CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_run_url_hash
    ON research_evidence (research_run_id, url_hash);
CREATE INDEX IF NOT EXISTS idx_evidence_run_id
    ON research_evidence (research_run_id);
CREATE INDEX IF NOT EXISTS idx_evidence_url_hash
    ON research_evidence (url_hash);
CREATE INDEX IF NOT EXISTS idx_evidence_content_hash
    ON research_evidence (content_hash);

-- ──────────────────────────────────────────────────────────────
-- 4. research_findings
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_findings (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id          UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    identity_key             TEXT NOT NULL,
    finding_type             TEXT NOT NULL
                             CHECK (finding_type IN (
                                 'product_launch','service_launch','campaign',
                                 'partnership','pricing_change','market_entry',
                                 'market_exit','technology_change','customer_signal',
                                 'industry_trend','regulatory_change','social_signal',
                                 'other'
                             )),
    title                    TEXT NOT NULL,
    summary                  TEXT NOT NULL,
    why_it_matters           TEXT NOT NULL,
    opportunity              TEXT,
    entities                 JSONB DEFAULT '[]',
    importance_score         INT CHECK (importance_score BETWEEN 0 AND 100),
    relevance_score          INT CHECK (relevance_score BETWEEN 0 AND 100),
    confidence_score         INT CHECK (confidence_score BETWEEN 0 AND 100),
    ai_confidence            INT CHECK (ai_confidence BETWEEN 0 AND 100),
    change_status            TEXT NOT NULL DEFAULT 'NEW',
    conflicts                JSONB DEFAULT '[]',
    supporting_evidence_ids  JSONB NOT NULL DEFAULT '[]',
    metadata                 JSONB DEFAULT '{}',
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_findings_run_id
    ON research_findings (research_run_id);
CREATE INDEX IF NOT EXISTS idx_findings_identity_key
    ON research_findings (identity_key);
CREATE INDEX IF NOT EXISTS idx_findings_type
    ON research_findings (finding_type);

-- ──────────────────────────────────────────────────────────────
-- 5. research_cache
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_cache (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key        TEXT NOT NULL UNIQUE,
    request_hash     TEXT NOT NULL,
    research_run_id  UUID REFERENCES research_runs(id),
    research_type    TEXT NOT NULL,
    ttl_hours        INT NOT NULL,
    expires_at       TIMESTAMPTZ NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cache_key
    ON research_cache (cache_key);
CREATE INDEX IF NOT EXISTS idx_cache_expires
    ON research_cache (expires_at);
