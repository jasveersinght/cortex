-- Supabase store 2: compliance feedback, for the checking agent.
-- Run in the Supabase SQL editor of the project you put in SUPABASE_COMPLIANCE_URL
-- (this can be the SAME Supabase project as content_schema.sql, just different tables).

create table if not exists compliance_reviews (
  brain_asset_id    text primary key,
  brand             text,
  platform          text,
  region            text,
  content_type      text,
  body_text         text,
  body_hash         text,
  status            text,          -- pending | approved | rejected
  tier              text,          -- highly_recommended | recommended_review | vigilant | suspicious
  confidence_score  numeric,
  lens_scores       jsonb,         -- {"claims": {"score":.., "reason":..}, "regulatory": {...}, "brand": {...}, "accuracy": {...}}
  approved_by       text,
  approved_at       timestamptz,
  synced_at         timestamptz not null default now()
);
create index if not exists idx_compliance_reviews_brand_tier on compliance_reviews (brand, tier);

-- One row per human decision, per performance lesson, and per re-check the checking agent asks for.
create table if not exists review_feedback (
  source_key      text primary key,     -- 'decision:<asset_id>:<status>' | 'lesson:<id>' | 'recheck:<id>'
  brain_asset_id  text,
  brand           text,
  platform        text,
  region          text,
  feedback_type   text not null,        -- decision | human_lesson | performance | recheck
  decision        text,                 -- approved | rejected (feedback_type='decision' only)
  reviewer        text,
  reason_tag      text,                 -- e.g. "too salesy", "inaccurate claim", or "perf:top_performer"
  note            text,
  body_excerpt    text,
  created_at      timestamptz not null default now()
);
create index if not exists idx_review_feedback_brand_type on review_feedback (brand, feedback_type, created_at desc);
create index if not exists idx_review_feedback_tag on review_feedback (reason_tag);

-- A simple rolling rejection rate per brand, for the checking agent to watch over time.
create or replace view rejection_rate_by_brand as
select
  brand,
  count(*) filter (where decision = 'rejected')::numeric
    / nullif(count(*) filter (where decision is not null), 0) as rejection_rate,
  count(*) filter (where decision = 'approved') as approved_count,
  count(*) filter (where decision = 'rejected') as rejected_count
from review_feedback
where feedback_type = 'decision'
group by brand;

alter table compliance_reviews enable row level security;
alter table review_feedback enable row level security;
-- No policies created: only the service_role key can read or write these tables.
