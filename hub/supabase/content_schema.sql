-- Supabase store 1: content agent output.
-- Run in the Supabase SQL editor of the project you put in SUPABASE_CONTENT_URL.

create table if not exists content_generations (
  id                    uuid primary key,
  brand                 text not null,
  region                text not null,
  request_json          jsonb not null,
  response_json         jsonb not null,
  latency_ms            integer,
  parent_generation_id  uuid,
  source_url            text,
  created_at            timestamptz not null default now()
);
create index if not exists idx_content_generations_brand on content_generations (brand, created_at desc);

create table if not exists content_items (
  generation_id   uuid not null references content_generations (id) on delete cascade,
  platform        text not null,
  body_text       text not null,
  body_hash       text not null,
  brand           text not null,
  region          text not null,
  brain_asset_id  text,
  media_url       text,
  created_at      timestamptz not null default now(),
  primary key (generation_id, platform)
);
create index if not exists idx_content_items_brand_platform on content_items (brand, platform, created_at desc);

alter table content_generations enable row level security;
alter table content_items enable row level security;
-- No policies are created on purpose: only the service_role key (used by the Hub) can read or write.
-- If you later want a read-only dashboard with the anon key, add a SELECT policy explicitly.
