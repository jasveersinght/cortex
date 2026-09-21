# JA Assure — Research / Discover Agent
### Implementation Source of Truth (v1.0)

> **Read this first.** This document specifies the Research / Discover Agent only. It is written to be handed to a coding agent (Antigravity) that will implement it **inside an existing codebase**. This is *not* a greenfield spec. Section 32 (Existing-Codebase Inspection) is a **mandatory gate** — no file may be created or modified before that inspection and gap analysis are complete.
>
> **Anything in this document describing the current repository is a hypothesis, not a fact.** Every such statement is marked `[VERIFY]`. Where this document's proposed naming, structure, or conventions conflict with what already exists in the repo, **the existing codebase wins** — adapt this spec to it, do not reshape the repo to match this spec.

---

## 1. Purpose

The Research / Discover Agent turns fresh external web information into **structured, evidence-backed intelligence** that a future Strategize Agent can act on.

For a given brand, market, and research type, it answers:

| Question | Captured as |
|---|---|
| WHO? | competitors, market players, organizations (`finding.entities`, `evidence.competitor`) |
| WHAT? | launches, campaigns, pricing, partnerships, technology, trends (`finding.finding_type`, `finding.title`) |
| WHEN? | `evidence.published_at`, `evidence.retrieved_at`, `finding.change_status` |
| WHERE? | `market` on both run and evidence |
| WHY? | `finding.why_it_matters` |
| OPPORTUNITY? | `finding.opportunity` |
| EVIDENCE? | `finding.supporting_evidence_ids` → `research_evidence` rows with real URLs |

The agent's contract with the rest of the system is simple: **it produces findings, and every finding is traceable to a real retrieved source.** It makes no strategy, no content, and no business decisions.

---

## 2. Current Scope

**In scope for this implementation:**

- One agent: Discover / Research.
- Four research types: `competitor_monitoring`, `market_research`, `trend_research`, `campaign_research`.
- Deterministic research planning in Python.
- Tavily as the sole external research engine (Search / Extract / Crawl / Map / Research).
- Deterministic evidence processing: normalization, hashing, dedup, date & relevance filtering, change detection.
- Groq as the sole reasoning layer, operating strictly over collected evidence.
- Cache-first execution with per-research-type TTLs.
- Supabase persistence of runs, evidence, findings, cache, competitors.
- FastAPI endpoints for triggering and reading research.
- Integration into the **existing** frontend's Discover fruit / workspace `[VERIFY]`.
- Tests for critical deterministic logic and failure paths.

**Explicitly out of scope:** Strategize, Create, Protect, Acquire, Learn. Only the *output contract* (§34) is designed for future consumption.

---

## 3. Non-Goals

The Research Agent must **not**:

- Generate marketing strategy, content, captions, or creative of any kind.
- Publish anything, schedule anything, or send outreach.
- Perform compliance approval or any approval gating.
- Make autonomous business decisions or rank business priorities as instructions.
- Invoke any other agent directly (including a future Strategize Agent).
- Introduce LangGraph, CrewAI, AutoGen, or any agent framework.
- Introduce a vector database or RAG.
- Use Playwright, Selenium, custom browser automation, or proxy infrastructure.
- Scrape Instagram/LinkedIn or any authenticated/ToS-restricted surface directly.
- Build microservices — this runs inside the existing FastAPI application.
- Use Groq to browse the web, or to perform any deterministic task (hashing, dedup, URL normalization, date filtering, cache checks, state transitions).
- Use Supabase MCP at runtime. MCP is a development/inspection tool for Antigravity only.

---

## 4. Existing System Assumptions

All of the following are **hypotheses to confirm during §32 inspection**. Do not code against any of them until verified.

| Assumption | Status |
|---|---|
| Backend is Python + FastAPI | `[VERIFY]` — stated in prompt, confirm app entrypoint, router registration pattern, settings/config module |
| Frontend is Vite + React, already built, with a tree UI and a Discover fruit | `[VERIFY]` — confirm routing, API client, state management, existing workspace components |
| Database is Supabase PostgreSQL | `[VERIFY]` — confirm client library in use (`supabase-py` vs. SQLAlchemy vs. asyncpg), existing schema, existing migration mechanism and directory |
| Env vars are loaded via an existing settings/config pattern | `[VERIFY]` — reuse it; do not introduce a second config mechanism |
| Some tables may already exist (e.g. `brands`, `markets`, `campaigns`, `agent_runs`) | `[VERIFY]` — if they exist, **reference them**, do not recreate |
| An existing logging setup exists | `[VERIFY]` — reuse it; do not introduce a parallel logger |
| An existing error-handling / exception-response convention exists | `[VERIFY]` — match it exactly for new endpoints |
| APScheduler may or may not already be wired in | `[VERIFY]` — scheduling is **optional** for this agent; only add if an existing scheduler is already present. Do not introduce scheduling infrastructure for v1. |

---

## 5. Architecture

```
                        JA ASSURE
                            │
                            ▼
                     DISCOVER AGENT
                            │
                            ▼
                   RESEARCH PLANNER
                       (Python)
                            │
                            ▼
                        TAVILY
               PRIMARY RESEARCH ENGINE
                            │
             ┌──────────────┼──────────────┐
             │              │              │
          SEARCH         EXTRACT      CRAWL / MAP
             │              │              │
             └──────────────┼──────────────┘
                            │
                            ▼
                      RAW EVIDENCE
                            │
                            ▼
                  PYTHON PROCESSING
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
        CLEAN             DEDUP              DIFF
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                     EVIDENCE CORPUS
                            │
                            ▼
                          GROQ
                 REASONING / SYNTHESIS
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
      SYNTHESIZE        CLASSIFY          EXPLAIN
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
                            ▼
                 STRUCTURED FINDINGS
                            │
                            ▼
                    CONFIDENCE SCORING
                         (Python)
                            │
                            ▼
                        SUPABASE
                            │
                            ▼
                      RESEARCH UI
                            │
                            ▼
              FUTURE STRATEGIZE HANDOFF
```

**Simplified routing:**

```
Research Request
      ↓
Research Planner (deterministic)
      ↓
Determine Complexity
      ↓
 ┌────────────────┐
 │                │
Simple          Complex
 │                │
 ↓                ↓
Tavily Search   Tavily Research
 │                │
 └───────┬────────┘
         ↓
 Optional Extract / Crawl (only when justified)
         ↓
      Evidence
         ↓
 Python Processing (clean → dedup → filter → diff)
         ↓
       Groq (single batched call)
         ↓
     Findings + Confidence
         ↓
     Supabase
```

**Core rule, non-negotiable:**

```
TAVILY   = FIND the information
PYTHON   = CONTROL and CLEAN the information
GROQ     = UNDERSTAND the information
SUPABASE = REMEMBER the information
```

---

## 6. Responsibility Split

| Stage | Owner | Never |
|---|---|---|
| PLAN | Python (deterministic templates) | Never Groq for trivial query construction |
| RESEARCH | Tavily | Never Groq browsing the web |
| COLLECT | Tavily | — |
| CLEAN | Python | Never Groq for normalization/hashing |
| COMPARE | Python (diff / change detection) | Never Groq to compare two hashes |
| UNDERSTAND | Groq | Never Python pretending to reason |
| REMEMBER | Supabase | Never in-memory-only state |

Groq is introduced **exactly once per run** (one batched call over the filtered evidence corpus), and only when there is evidence worth reasoning about (§16.1).

---

## 7. Research Types

Implement as a string enum, extensible without rewriting the agent. Each type maps to a **query template set**, a **TTL**, a **default complexity**, and a **default lookback**.

| Type | Query templates | TTL | Default complexity | Default lookback |
|---|---|---|---|---|
| `competitor_monitoring` | launches, pricing, campaigns, partnerships, product changes, market expansion, technology activity | 24h | medium | 30 days |
| `market_research` | market size/activity, new entrants, regulation, customer demand signals, distribution channels | 24h | medium | 90 days |
| `trend_research` | emerging topics, industry news, technology shifts, commentary | 6h | low | 14 days |
| `campaign_research` | competitor campaigns, messaging angles, creative themes, channel usage | 12h | medium | 60 days |

**Extensibility requirement:** research types live in a registry (a dict/module mapping type → `ResearchTypeConfig`). Adding a type must require only a new registry entry plus its query templates — no changes to `ResearchManager`, the Tavily adapter, the evidence processor, or the Groq analyst.

```python
@dataclass(frozen=True)
class ResearchTypeConfig:
    name: str
    query_templates: list[str]          # format strings, e.g. "{competitor} pricing {market}"
    ttl_hours: int
    default_complexity: Complexity      # LOW | MEDIUM | HIGH
    default_lookback_days: int
    requires_competitors: bool          # competitor_monitoring=True (discover if empty)
    finding_type_hints: list[str]       # guides Groq classification, does not constrain it
```

---

## 8. Request Contract

### 8.1 Model

```python
class ResearchRequest(BaseModel):
    brand: str                                   # required, 1..120 chars
    market: str                                  # required, enum-validated
    research_type: ResearchType                  # required, enum
    objective: str | None = None                 # optional, <= 500 chars, free text
    competitors: list[str] = []                  # optional, max 10, each 1..120 chars
    topics: list[str] = []                       # optional, max 10, each 1..120 chars
    lookback_days: int | None = None             # optional, 1..365, defaults per research type
    force_refresh: bool = False
    max_sources: int = 20                        # optional, 5..50, cost ceiling
```

### 8.2 Validation rules

| Field | Rule | On violation |
|---|---|---|
| `brand` | non-empty after strip; `[VERIFY]` whether an existing `brands` table should constrain this — if it exists, validate against it, else accept free text | 422 |
| `market` | must be one of the JA Assure markets: `Singapore`, `Malaysia`, `Hong Kong`, `Indonesia`, `Thailand`. `[VERIFY]` an existing `markets` table; prefer it as the source of truth | 422 |
| `research_type` | must exist in the research-type registry | 422 |
| `competitors` / `topics` | strip, drop empties, deduplicate case-insensitively, cap at 10 | silently normalized (log the normalization) |
| `lookback_days` | 1..365; if null, use the research type default | 422 if out of range |
| `max_sources` | 5..50; if out of range, clamp and log | clamped |
| `objective` | trimmed; if empty string, treated as null | — |

**Malformed input handling:** reject with HTTP 422 and a field-level error body matching the existing API error convention `[VERIFY]`. Never partially execute a run on an invalid request. Never coerce an unknown `research_type` or `market` into a default — fail loudly.

**Competitor discovery:** if `research_type == competitor_monitoring` and `competitors` is empty, the planner generates discovery queries (e.g. `"{brand} competitors {market}"`, `"top {industry-ish term} companies {market}"`) and treats entities surfaced in evidence as candidate competitors. Candidates are persisted to the `competitors` table with `discovered=true` and `confirmed=false`; they are **never** auto-promoted to confirmed.

---

## 9. Research Planner

**Pure deterministic Python. No LLM. No network calls.** This makes it trivially unit-testable and is a core cost-control mechanism.

### 9.1 Responsibility

Input: a validated `ResearchRequest`.
Output: a `ResearchPlan` — fully specified, inspectable, serializable, and persisted on the run row so the plan can be shown in the UI and audited later.

```python
@dataclass
class PlannedQuery:
    query: str
    operation: TavilyOperation          # SEARCH | EXTRACT | CRAWL | MAP | RESEARCH
    purpose: str                        # e.g. "competitor pricing"
    target_entity: str | None           # competitor/topic this query serves
    max_results: int
    time_range_days: int
    domains_include: list[str] = []     # optional narrowing
    domains_exclude: list[str] = []

@dataclass
class ResearchPlan:
    complexity: Complexity
    queries: list[PlannedQuery]
    extract_policy: ExtractPolicy       # see §10.3
    crawl_targets: list[str]            # usually empty
    rationale: str                      # human-readable, shown in UI ("why this plan")
    estimated_tavily_calls: int
```

### 9.2 Complexity determination (deterministic)

Score the request, then map score → complexity:

```
score = 0
score += 2 if research_type.default_complexity == HIGH else 1 if MEDIUM else 0
score += 1 if len(competitors) + len(topics) >= 4
score += 1 if lookback_days > 60
score += 1 if objective is not None and len(objective) > 120
score -= 1 if max_sources <= 10

complexity = LOW    if score <= 1
             MEDIUM if score in (2, 3)
             HIGH   if score >= 4
```

These thresholds are a starting policy, defined in one constants module so they can be tuned without touching logic. Log the score and the resulting complexity on every run.

### 9.3 Query generation

For each competitor (or topic), instantiate the research type's templates:

```
competitor_monitoring, competitors=["Competitor X"], market="Singapore"
→ "Competitor X new service launch Singapore"
→ "Competitor X pricing Singapore"
→ "Competitor X marketing campaign Singapore"
→ "Competitor X partnership Singapore"
→ "Competitor X product update"
→ "Competitor X market expansion Singapore"
```

**Query budget (hard cap, cost control):**

```
max_queries = min(
    len(entities) * len(templates),
    12 if complexity == HIGH else 8 if complexity == MEDIUM else 4
)
```

Prioritize templates by the research type's declared template order (most strategically valuable first) so truncation drops the least-valuable queries, not random ones.

### 9.4 Failure cases

| Case | Behavior |
|---|---|
| No entities and no topics and type requires them | Generate discovery queries from `brand` + `market` |
| Template instantiation produces an empty/duplicate query | Drop it, log, continue |
| Plan produces zero queries | Fail fast with a clear error before any Tavily call — never call Tavily with an empty plan |

---

## 10. Tavily Research Layer

### 10.1 Adapter contract

Business logic must never touch the Tavily SDK directly (§33).

```python
class TavilyResearchAdapter(Protocol):
    def search(self, q: PlannedQuery) -> list[RawSource]: ...
    def extract(self, urls: list[str]) -> list[RawSource]: ...
    def crawl(self, root_url: str, limit: int) -> list[RawSource]: ...
    def map_site(self, root_url: str) -> list[str]: ...
    def research(self, q: PlannedQuery) -> list[RawSource]: ...
```

`RawSource` is the adapter's normalized output — vendor response shapes never leak past this boundary:

```python
@dataclass
class RawSource:
    url: str
    title: str | None
    content: str | None
    published_at: datetime | None
    score: float | None            # Tavily relevance score if provided
    source_operation: TavilyOperation
    query: str
    raw: dict                      # vendor payload, stored for debugging only
```

### 10.2 Routing strategy

| Situation | Operation | Use when | Do NOT use when |
|---|---|---|---|
| LOW complexity | `search` only | Straightforward factual lookup, few entities, short lookback | — |
| MEDIUM complexity | `search` → `extract` on high-value URLs | Search snippets are too thin to support a finding | Snippets already contain the fact; extraction adds cost with no new information |
| Site-specific investigation | `map` → select pages → `extract` | A single competitor's own site is the subject (pricing page, product page) | You only need news *about* the company — search is cheaper and broader |
| HIGH complexity / multi-source | `research` | Broad question spanning many sources where planning the individual queries is itself the hard part | A handful of targeted searches would answer it — `research` is the most expensive call available |

**Hard rules:**
- Never call every capability "just in case."
- `crawl` is off by default. It requires an explicit justification recorded in `plan.rationale` and is capped at 10 pages.
- `research` is used at most **once per run**, and only at HIGH complexity.
- All operations respect `max_sources` as a global ceiling on retrieved sources per run.

### 10.3 Extract policy

```python
@dataclass
class ExtractPolicy:
    enabled: bool
    max_urls: int = 5
    min_search_score: float = 0.6      # only extract from confident search hits
    min_content_chars: int = 400       # only extract when the snippet is too short to stand alone
```

Selection is deterministic: sort candidate URLs by (source quality tier, search score, recency), take the top `max_urls` that fail the `min_content_chars` test. Extraction never runs on a URL whose snippet already exceeds the threshold.

### 10.4 Failure handling

| Failure | Behavior |
|---|---|
| Timeout (per call: 20s) | Retry twice, exponential backoff (1s, 3s) |
| Rate limit (429) | Retry twice with longer backoff (5s, 15s); if still limited, mark run `PARTIAL_FAILURE` and proceed with what was collected |
| Malformed response | Log the raw payload (never the key), skip that source, continue |
| All queries fail | Run status `FAILED`, `error_message` set, no fabricated evidence, cache not written |
| Some queries fail | Continue; record `sources_checked` honestly; status will be `PARTIAL_FAILURE` if any planned query failed |

Per-query failures must be isolated — one failing query never aborts the run.

---

## 11. Evidence Model

```python
@dataclass
class Evidence:
    id: str                          # "evidence_001"-style, stable within a run; DB PK is a UUID
    research_run_id: UUID
    source_type: SourceType          # web | news | company_site | regulator | industry | social | other
    source_name: str                 # derived from domain
    source_quality: int              # 1..6, see §15 (1 = best)
    title: str | None
    url: str                         # normalized (§12)
    content: str                     # normalized, truncated to a stored ceiling (e.g. 8000 chars)
    content_hash: str                # sha256 of normalized content
    url_hash: str                    # sha256 of normalized URL
    published_at: datetime | None
    retrieved_at: datetime
    market: str
    competitor: str | None
    topic: str | None
    query: str
    tavily_operation: str
    relevance: Relevance             # RELEVANT | UNCERTAIN | IRRELEVANT
    relevance_score: float           # 0..1, deterministic (§14)
    change_status: ChangeStatus      # NEW | CHANGED | UNCHANGED (evidence-level)
    metadata: dict
```

**Rule:** a finding may only reference evidence that exists as a persisted row from the same run (or, for `UNCHANGED`/carried-over items, a prior run explicitly linked via `metadata.carried_from_run_id`). Groq is given the `id` values and must use exactly those strings.

---

## 12. Evidence Processing

All deterministic Python. Ordered pipeline; each stage is a pure function over a list and is independently unit-tested.

### 12.1 URL normalization

```
1. Lowercase scheme and host.
2. Force https where the host also serves https (do not fetch to check — just canonicalize http→https for known-https domains list; otherwise preserve).
3. Strip default ports (:80, :443).
4. Strip tracking params: utm_*, gclid, fbclid, mc_cid, mc_eid, ref, source.
5. Sort remaining query params alphabetically.
6. Strip trailing slash (except root path).
7. Strip fragment (#...).
8. Strip "www." prefix from host for hashing purposes (keep original for display).
```

Store **both** the display URL and the normalized URL; hash the normalized one.

### 12.2 Content normalization

```
1. Strip HTML tags if any survived extraction.
2. Collapse all whitespace runs to single spaces; normalize newlines.
3. Strip boilerplate markers where trivially detectable (cookie notices, "Share this article", nav crumbs) via a small deterministic pattern list.
4. Unicode NFKC normalization.
5. Trim to a max stored length (8000 chars) — record `metadata.truncated = true` if trimmed.
```

### 12.3 Hashing

- `url_hash = sha256(normalized_url)`
- `content_hash = sha256(normalized_content[:4000])` — bounded prefix so that trivial tail differences (timestamps, "related articles") don't defeat dedup.

Both are hex digests, stored as text, indexed.

### 12.4 Date filtering

- If `published_at` is present and older than `now - lookback_days`, drop the source (log as `filtered:stale`).
- If `published_at` is **absent**, do **not** drop it. Mark `metadata.published_date_missing = true` and let relevance scoring apply a recency penalty (§20). Dropping undated sources silently loses real signal.
- Never call Groq to parse a date. Use `dateutil` on the string Tavily provides; on parse failure, treat as absent.

---

## 13. Deduplication

Applied in this order, keeping the **highest-quality** survivor (lowest `source_quality` number, then longest content, then most recent):

1. **Exact URL dedup** — identical `url_hash`.
2. **Exact content dedup** — identical `content_hash` across different URLs (syndicated articles).
3. **Source-level dedup** — same domain + same `published_at` date + title similarity above a threshold. Use deterministic token-set Jaccard similarity on normalized titles (≥ 0.85), **not** an LLM.

Every dropped item is logged with the reason and the surviving item's id, and the count is reported in the run metrics. Deduplication must be deterministic and order-independent: sort candidates by the survivor-preference key *before* the dedup pass so repeated runs on identical input produce identical output.

---

## 14. Relevance Filtering

Deterministic and bounded. Produces a score in `[0,1]` and a tri-state label.

```
relevance_score =
    0.30 * entity_match        # brand/competitor/topic token appears in title or first 1000 chars
  + 0.20 * market_match        # market name or a known market alias appears
  + 0.20 * objective_overlap   # token overlap with objective/topic keywords (Jaccard, capped)
  + 0.15 * source_quality_norm # (7 - source_quality) / 6
  + 0.15 * recency_norm        # linear decay over lookback window; 0.5 if date missing
```

Labeling:

| Score | Label | Handling |
|---|---|---|
| ≥ 0.60 | `RELEVANT` | Sent to Groq |
| 0.35 – 0.59 | `UNCERTAIN` | **Retained and persisted**, sent to Groq only if the relevant set is thin (< 5 items), always visible in the UI under "lower-confidence sources" |
| < 0.35 | `IRRELEVANT` | Persisted but excluded from Groq input; never silently deleted |

**Nothing is discarded.** Everything retrieved is stored with its label, so a user can always see what the system saw and chose not to use. This is an auditability requirement, not an optimization.

---

## 15. Source Quality

Deterministic classification by domain, in a maintainable mapping table.

| Tier | Type | Examples of classification rule |
|---|---|---|
| 1 | Official company source | Domain matches a known competitor's official domain (from `competitors.domain`) |
| 2 | Government / regulator | Known regulator domains per market (MAS, BNM, OJK, SFC, Thai OIC) + `.gov*` TLD patterns |
| 3 | Reputable news organization | Curated allowlist of major/regional outlets |
| 4 | Industry publication | Curated list of insurance/logistics/jewellery trade press |
| 5 | Public social source | Known social domains (only as they appear in search results — never scraped directly) |
| 6 | Secondary / unknown | Everything else (aggregators, blogs, unclassified) |

**Rule:** multiple tier-5/6 sources do **not** aggregate into strong evidence. Confidence scoring (§19) applies a diminishing-returns curve weighted by tier, so five unknown blogs never outscore one official company announcement.

The mapping lives in a config module (or a small `source_quality_rules` table `[VERIFY]` whether config-as-code fits existing conventions better). Unknown domains default to tier 6 and are logged so the list can be improved.

---

## 16. Change Detection

Deterministic diff against the most recent completed run with the same `(brand, market, research_type)`.

### 16.1 Evidence-level

| Condition | Status |
|---|---|
| `url_hash` not seen in prior run | `NEW` |
| `url_hash` seen, `content_hash` differs | `CHANGED` |
| `url_hash` seen, `content_hash` identical | `UNCHANGED` |
| Present in prior run, absent now | `REMOVED` (recorded on the run, not re-persisted as evidence) |

### 16.2 Finding-level

Findings get a `change_status` derived deterministically from their supporting evidence:

- Any supporting evidence is `NEW` → finding is `NEW`.
- Else any is `CHANGED` → finding is `CHANGED`.
- Else → `UNCHANGED`.

Additionally, compute a **finding identity key** = `sha256(finding_type + normalized(title) + primary_entity)` to match findings across runs, so an unchanged finding keeps a stable identity in the UI rather than appearing brand new each run.

### 16.3 Groq input optimization

If **all** filtered evidence is `UNCHANGED` and a prior completed run exists with findings, **skip the Groq call entirely**. Carry forward the prior run's findings with `change_status = UNCHANGED`, mark the run `COMPLETED`, record `groq_calls = 0`, and set `metadata.groq_skipped_reason = "no_changed_evidence"`. This is a major cost saving and is exactly the kind of decision that should be visible in the UI.

Never call Groq to determine whether two identical hashes are identical.

---

## 17. Groq Analysis Layer

### 17.1 When Groq runs

Exactly once per run, and only if **all** of:
- At least one evidence item is labeled `RELEVANT` (or `UNCERTAIN` when the relevant set is thin).
- Not all evidence is `UNCHANGED` (§16.3).
- Tavily retrieval did not fail completely.

Otherwise the run completes without a Groq call, with an explicit recorded reason.

### 17.2 Batching

**One call, all evidence.** Never one call per article. Construct the payload as a compact JSON array of evidence objects, each trimmed to the fields Groq actually needs:

```json
{
  "context": {
    "brand": "Jaguar Transit",
    "market": "Singapore",
    "research_type": "competitor_monitoring",
    "objective": "Identify recent competitor activity",
    "lookback_days": 30
  },
  "evidence": [
    {
      "id": "evidence_001",
      "source_name": "Example News",
      "source_quality_tier": 3,
      "title": "Competitor launches premium transit cover",
      "url": "https://example.com/article",
      "published_at": "2026-09-14",
      "content_excerpt": "…first 1500 chars of normalized content…",
      "change_status": "NEW"
    }
  ]
}
```

**Token budget:** cap total evidence excerpt payload at a configured ceiling (start at ~40 evidence items × 1500 chars). If exceeded, truncate by dropping lowest `relevance_score` items first and record `metadata.groq_input_truncated = true`. Never silently drop from the middle.

### 17.3 Adapter contract

```python
class GroqAnalysisAdapter(Protocol):
    def analyze(self, payload: AnalysisPayload) -> AnalysisResult: ...
```

`AnalysisResult` is the validated, parsed structure — the Groq SDK and raw response never leak past the adapter.

### 17.4 Strict structured output

Request JSON-schema-constrained / JSON-mode output. Required response shape:

```json
{
  "findings": [
    {
      "finding_type": "product_launch",
      "title": "string, <= 140 chars",
      "summary": "string, <= 600 chars",
      "why_it_matters": "string, <= 400 chars",
      "opportunity": "string or null, <= 400 chars",
      "entities": ["string"],
      "importance_score": 0,
      "ai_confidence": 0,
      "supporting_evidence_ids": ["evidence_001"],
      "conflicts": [
        {
          "description": "string",
          "evidence_ids": ["evidence_002", "evidence_007"]
        }
      ]
    }
  ],
  "insufficient_evidence": false,
  "notes": "string or null"
}
```

### 17.5 Output validation (mandatory, before any persistence)

Validate in this order; a failure at any step is treated as a Groq failure (retry once, then `PARTIAL_FAILURE`):

1. Response parses as JSON.
2. Conforms to the Pydantic model above.
3. **Every** `supporting_evidence_ids` entry exists in the evidence set that was sent. Findings referencing unknown ids are **dropped**, not repaired, and the drop is logged as a hallucination event.
4. Every finding has at least one valid supporting evidence id. Zero-evidence findings are dropped.
5. `finding_type` is in the allowed enum; unknown values are coerced to `other` and logged.
6. Scores are integers in `[0,100]`; out-of-range values are clamped and logged.
7. No URL appears in `summary`/`why_it_matters`/`opportunity` that isn't present in the supplied evidence set — if one does, drop the finding and log it as a fabricated-source event.

Track dropped-finding counts per run. A non-zero count is a signal worth surfacing in logs and worth showing in the UI as a transparency detail.

---

## 18. Hallucination Prevention

Layered, defense-in-depth:

| Layer | Mechanism |
|---|---|
| Prompt | Explicit constraints (§18.1) |
| Format | Strict JSON schema, no free-form output |
| Grounding | Evidence ids are the only permitted references |
| Post-validation | §17.5 — unknown ids, fabricated URLs, and zero-evidence findings are dropped |
| Escape hatch | `insufficient_evidence: true` is an accepted, first-class answer |
| Honesty | Dropped findings are counted and logged, never silently swallowed |

### 18.1 Groq system prompt (implementation-grade)

```
ROLE
You are a research intelligence analyst for JA Assure, a niche InsurTech operating in
Singapore, Malaysia, Hong Kong, Indonesia and Thailand.

INPUT
You will receive a research context and a list of evidence items that were collected by
an external research system. Each evidence item has a stable id.

TASK
Synthesize the supplied evidence into structured findings. Group related evidence into a
single finding rather than producing one finding per article. Classify each finding,
explain why it matters to the stated brand and market, and identify any opportunity
signal that the evidence genuinely supports.

ABSOLUTE CONSTRAINTS
- Use ONLY the supplied evidence. You have no other knowledge of these companies or events.
- Do NOT invent facts, sources, URLs, dates, statistics, companies, or events.
- Do NOT fill gaps with plausible guesses. Missing information stays missing.
- Every finding MUST list the evidence ids that support it. A finding with no supporting
  evidence id is invalid and must not be produced.
- Do NOT reference any URL that does not appear in the supplied evidence.
- Do NOT make business decisions, recommend budgets, or write marketing copy.

CONFLICT RULE
If two evidence items disagree, do NOT pick a winner and do NOT average them. Record the
disagreement in the finding's `conflicts` array, describe what differs, list the conflicting
evidence ids, and lower `ai_confidence` accordingly.

INSUFFICIENCY RULE
If the evidence does not support any meaningful finding, return an empty `findings` array
and set `insufficient_evidence` to true. This is a correct and valuable answer. Producing a
weak finding to avoid an empty result is a failure.

SCORING
- `importance_score` (0-100): how strategically significant this is for the stated brand and
  market. A competitor entering the brand's exact niche is high; a generic industry mention
  is low.
- `ai_confidence` (0-100): how strongly the SUPPLIED EVIDENCE supports the claim you are
  making. Single undated secondary source = low. Multiple independent sources including an
  official one = high. These two scores are independent; an important finding may have low
  confidence and you must report that honestly.

OUTPUT
Return ONLY valid JSON matching the provided schema. No prose, no markdown, no code fences.
```

---

## 19. Finding Model

```python
@dataclass
class Finding:
    id: UUID
    research_run_id: UUID
    identity_key: str                   # §16.2, for cross-run matching
    finding_type: FindingType
    title: str
    summary: str
    why_it_matters: str
    opportunity: str | None
    entities: list[str]
    importance_score: int               # 0..100, AI-assigned
    relevance_score: int                # 0..100, deterministic (derived from evidence)
    confidence_score: int               # 0..100, blended (§20)
    ai_confidence: int                  # 0..100, Groq's self-report (kept separately, never alone)
    change_status: ChangeStatus
    conflicts: list[Conflict]
    supporting_evidence_ids: list[str]
    created_at: datetime
```

`FindingType` enum: `product_launch`, `service_launch`, `campaign`, `partnership`, `pricing_change`, `market_entry`, `market_exit`, `technology_change`, `customer_signal`, `industry_trend`, `regulatory_change`, `social_signal`, `other`.

**Validation:** title 1..140 chars; summary 1..600; at least one supporting evidence id; all scores in `[0,100]`; `finding_type` in enum.

---

## 20. Importance vs Confidence, and Confidence Scoring

### 20.1 They are separate, always

- **Importance** = "how strategically significant is this?" — AI-assigned, because it requires judgment about the brand's position.
- **Confidence** = "how strongly does the evidence support this?" — **primarily deterministic**, because it's a function of source properties we can measure.

A competitor entering JA's exact niche, reported by one undated blog, is **high importance, low confidence** — and the system must be able to say that. Never blend them into a single "score."

### 20.2 Confidence model (transparent, no ML)

```
confidence_score = round(100 * (
    0.30 * source_quality_component     # DETERMINISTIC: best tier among supporting evidence, normalized
  + 0.25 * corroboration_component      # DETERMINISTIC: diminishing returns on independent sources
  + 0.15 * independence_component       # DETERMINISTIC: distinct registrable domains / total sources
  + 0.15 * recency_component            # DETERMINISTIC: decay over lookback window
  + 0.15 * ai_confidence_component      # AI-ASSISTED: Groq's ai_confidence / 100
))
```

Where:

```
source_quality_component = (7 - min(tier for supporting evidence)) / 6

corroboration_component  = min(1.0, log2(1 + n_independent_sources) / log2(5))
                           # 1 source ≈ 0.43, 2 ≈ 0.68, 4 ≈ 1.0 — diminishing, not linear

independence_component   = distinct_registrable_domains / total_supporting_sources

recency_component        = 1 - (days_since_newest_evidence / lookback_days), floored at 0
                           # if all supporting evidence lacks dates, use 0.5 and flag it
```

**Penalties applied after the blend:**
- `-15` if the finding has any entry in `conflicts`.
- `-10` if every supporting source is tier 5 or 6.
- `-10` if every supporting source lacks a `published_at`.
- Floor at 0, ceiling at 100.

**Explainability requirement:** persist the component breakdown in `finding.metadata.confidence_breakdown` so the UI can show *why* a confidence number is what it is. A confidence score with no breakdown is not acceptable — this is the difference between a trustworthy system and a number generator.

Note clearly in the UI and in code comments: **`ai_confidence` is a self-report and contributes only 15%.** It is a signal, not truth.

---

## 21. Cache Architecture

### 21.1 Keys

```python
request_hash = sha256(canonical_json({
    "brand": brand.strip().lower(),
    "market": market.strip().lower(),
    "research_type": research_type.value,
    "competitors": sorted(c.strip().lower() for c in competitors),
    "topics": sorted(t.strip().lower() for t in topics),
    "lookback_days": effective_lookback_days,
    "objective_normalized": normalize_objective(objective),   # lowercased, whitespace-collapsed, or "" if None
}))

cache_key = f"research:{research_type}:{request_hash[:16]}"
```

`max_sources` and `force_refresh` are deliberately **excluded** from the hash — they control execution, not the semantic identity of the question.

### 21.2 Flow

```
Request
 ↓
Validate
 ↓
Compute request_hash → cache_key
 ↓
force_refresh == true? ──yes──→ bypass cache, proceed to new run
 ↓ no
Look up research_cache by cache_key
 ↓
Row exists AND expires_at > now? 
 ├── YES → return cached research_run_id + its findings/evidence, mark response.cache_hit=true, groq_calls=0, tavily_calls=0
 └── NO  → proceed to new run
```

### 21.3 TTLs

| Research type | TTL | Reasoning |
|---|---|---|
| `competitor_monitoring` | 24h | Competitor sites and announcements don't change hourly |
| `market_research` | 24h | Market-level signals move slowly |
| `trend_research` | 6h | Trends and news move fastest |
| `campaign_research` | 12h | Campaigns change over days, not hours |

Store `ttl_hours` on the cache row so a TTL policy change doesn't retroactively reinterpret existing rows.

### 21.4 Invalidation, staleness, concurrency

- **Invalidation:** `force_refresh=true`; TTL expiry; explicit delete (admin/debug only).
- **Stale fallback:** if a fresh run *fails* and an expired cache row exists, return the stale result labeled `stale: true` with `stale_age_hours`, and set run status `PARTIAL_FAILURE`. The UI must display the age. Never present stale data as fresh.
- **Concurrency:** before starting a new run, check for an existing run with the same `request_hash` and status in (`PLANNING`, `RETRIEVING`, `NORMALIZING`, `FILTERING`, `DETECTING_CHANGES`, `ANALYZING`) started within the last 5 minutes. If found, return `202 Accepted` with that `research_run_id` instead of starting a duplicate. Enforce with a partial unique index on `(request_hash)` where status is in-flight `[VERIFY]` that this fits the existing schema conventions.

**Never call Tavily or Groq before the cache check.** This is the single highest-value cost control in the system.

---

## 22. Supabase Schema

> `[VERIFY]` existing tables first. If `brands`, `markets`, `campaigns`, `agent_runs`, or `audit_events` already exist, **reference them via FK** and do not recreate. Match existing naming conventions (snake_case vs. plural, `id` vs. `uuid`, timestamp column naming) even where they differ from what's written below.

### `competitors`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | default gen_random_uuid() |
| `name` | text NOT NULL | |
| `brand` | text NOT NULL | which JA brand this competitor is relevant to |
| `market` | text NOT NULL | |
| `domain` | text NULL | used for tier-1 source classification |
| `discovered` | boolean NOT NULL DEFAULT false | found by the planner rather than user-supplied |
| `confirmed` | boolean NOT NULL DEFAULT false | never auto-set to true |
| `created_at` / `updated_at` | timestamptz | |

Unique: `(lower(name), brand, market)`. Index: `(brand, market)`.

### `research_runs`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `brand`, `market`, `research_type`, `objective` | text | `objective` nullable |
| `status` | text NOT NULL | §24 enum, CHECK constraint |
| `request_hash` | text NOT NULL | indexed |
| `plan` | jsonb | the full `ResearchPlan`, for auditability |
| `lookback_days` | int NOT NULL | |
| `started_at`, `completed_at` | timestamptz | `completed_at` nullable |
| `sources_checked`, `unique_sources`, `relevant_sources` | int DEFAULT 0 | derived metrics |
| `new_findings`, `changed_findings`, `unchanged_findings` | int DEFAULT 0 | derived metrics |
| `tavily_calls`, `groq_calls` | int DEFAULT 0 | cost metrics |
| `dropped_findings` | int DEFAULT 0 | hallucination-validation drops |
| `confidence_score` | int NULL | run-level average of finding confidences |
| `cache_hit` | boolean DEFAULT false | |
| `error_message` | text NULL | |
| `metadata` | jsonb | groq_skipped_reason, truncation flags, etc. |
| `created_at` | timestamptz | |

Indexes: `(brand, market, research_type, completed_at DESC)` — this is the change-detection lookup path and must be fast. Plus `(request_hash)`, `(status)`.

**Immutable once `completed_at` is set:** all metric columns and `status` (except a manual admin correction). Enforce in application code; a DB trigger is optional `[VERIFY]` against existing conventions.

### `research_evidence`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `research_run_id` | uuid FK → research_runs(id) ON DELETE CASCADE | |
| `evidence_ref` | text NOT NULL | the `"evidence_001"` id used in Groq payload/findings |
| `source_type`, `source_name` | text | |
| `source_quality` | int NOT NULL | 1..6, CHECK |
| `title` | text NULL | |
| `url` | text NOT NULL | display URL |
| `normalized_url` | text NOT NULL | |
| `url_hash`, `content_hash` | text NOT NULL | both indexed |
| `content` | text | truncated per §12.2 |
| `published_at` | timestamptz NULL | |
| `retrieved_at` | timestamptz NOT NULL | |
| `market`, `competitor`, `topic`, `query`, `tavily_operation` | text | nullable where applicable |
| `relevance` | text NOT NULL | RELEVANT / UNCERTAIN / IRRELEVANT, CHECK |
| `relevance_score` | numeric(4,3) | |
| `change_status` | text NOT NULL | |
| `metadata` | jsonb | |
| `created_at` | timestamptz | |

Unique: `(research_run_id, evidence_ref)` and `(research_run_id, url_hash)`.
Indexes: `(research_run_id)`, `(url_hash)`, `(content_hash)`.

### `research_findings`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `research_run_id` | uuid FK → research_runs(id) ON DELETE CASCADE | |
| `identity_key` | text NOT NULL | cross-run matching, indexed |
| `finding_type` | text NOT NULL | CHECK against enum |
| `title`, `summary`, `why_it_matters` | text NOT NULL | |
| `opportunity` | text NULL | |
| `entities` | jsonb | array of strings |
| `importance_score`, `relevance_score`, `confidence_score`, `ai_confidence` | int | CHECK 0..100 |
| `change_status` | text NOT NULL | |
| `conflicts` | jsonb DEFAULT '[]' | |
| `supporting_evidence_ids` | jsonb NOT NULL | array of `evidence_ref` strings |
| `metadata` | jsonb | includes `confidence_breakdown` |
| `created_at` | timestamptz | |

Indexes: `(research_run_id)`, `(identity_key)`, `(finding_type)`.

**Referential integrity note:** `supporting_evidence_ids` is jsonb rather than a join table for simplicity, but the application **must** validate every id against `research_evidence` for that run before insert (§17.5). If the existing codebase favors normalized joins, a `finding_evidence` join table is the better choice — `[VERIFY]` and follow existing convention.

### `research_cache`
| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `cache_key` | text NOT NULL UNIQUE | |
| `request_hash` | text NOT NULL | |
| `research_run_id` | uuid FK → research_runs(id) | the run whose results this caches |
| `research_type` | text NOT NULL | |
| `ttl_hours` | int NOT NULL | |
| `expires_at` | timestamptz NOT NULL | indexed |
| `created_at` | timestamptz | |

Index: `(cache_key)`, `(expires_at)`.

---

## 23. API Contracts

All endpoints live under the existing router registration pattern `[VERIFY]`. Error bodies must match the existing API error convention `[VERIFY]` — the shapes below are a fallback if none exists.

### `POST /discover/run`
**Purpose:** start (or serve from cache) a research run.
**Request:** `ResearchRequest` (§8).
**Responses:**
- `200` — cache hit. Body: `{ research_run_id, cache_hit: true, status: "COMPLETED", stale: false, findings_count, ... }`
- `201` — new run completed synchronously (expected for v1; runs are short). Body: full run summary.
- `202` — an identical run is already in flight. Body: `{ research_run_id, status }`.
- `422` — validation failure, field-level errors.
- `502` — Tavily unavailable and no stale cache to fall back on.
- `500` — unexpected.

**Idempotency:** same request + valid cache = cached result (no new run). Same request + expired cache = new run. `force_refresh=true` = always new run. Duplicate concurrent request = `202` with the in-flight id.

> **Execution mode decision:** run synchronously for v1. A full run (cache miss, ~8 Tavily calls + 1 Groq call) should complete in roughly 15–40s. Chosen over a background-job queue because it removes polling complexity, keeps the demo deterministic, and there is no scheduling requirement in scope. If measured p95 exceeds ~60s during implementation, switch to `202 + poll GET /discover/{id}` — the response models above already accommodate this.

### `GET /discover/{research_run_id}`
Returns the run record with derived metrics, status, plan rationale, and counts. `404` if unknown.

### `GET /discover/{research_run_id}/findings`
Returns findings ordered by `importance_score DESC, confidence_score DESC`. Supports `?change_status=NEW|CHANGED|UNCHANGED` and `?min_confidence=`. Each finding embeds a compact evidence summary (ref, title, url, source_name, source_quality) so the UI can render without a second call.

### `GET /discover/{research_run_id}/evidence`
Returns all evidence for the run, including `IRRELEVANT` items (they're persisted for auditability). Supports `?relevance=`. Paginated if count is large.

### `GET /discover/status`
Lightweight: most recent run per `(brand, market, research_type)` with status, `completed_at`, cache freshness, and whether a cached result is currently valid. This is what the Tree's Discover fruit badge reads.

### `GET /health`
`[VERIFY]` — if a health endpoint already exists, **extend it**, do not add a second one. Add Tavily/Groq/Supabase reachability as sub-checks (cheap, non-billing calls only; never a real search).

---

## 24. Error Handling

### 24.1 Run states

```
IDLE → CHECKING_CACHE → PLANNING → RETRIEVING → NORMALIZING → FILTERING
     → DETECTING_CHANGES → ANALYZING → COMPLETED
```

Terminal alternatives: `SKIPPED` (cache hit — no work performed), `PARTIAL_FAILURE`, `FAILED`.

### 24.2 Failure matrix

| Scenario | Status | Behavior |
|---|---|---|
| Cache hit | `SKIPPED` | Return cached run; `tavily_calls=0`, `groq_calls=0` |
| Tavily fully unavailable, no cache | `FAILED` | `error_message` set; no evidence, no findings, **no cache write** |
| Tavily fully unavailable, expired cache exists | `PARTIAL_FAILURE` | Return stale result labeled `stale: true` with age |
| Some Tavily queries fail | `PARTIAL_FAILURE` | Proceed with collected evidence; record which queries failed in `metadata` |
| Tavily OK, Groq fails after retry | `PARTIAL_FAILURE` | **Persist all evidence.** `findings = []`. `error_message` explains Groq failed. Evidence is still valuable and must not be discarded. |
| Groq returns malformed JSON twice | `PARTIAL_FAILURE` | Same as above; log the raw response (never the key) |
| Groq returns `insufficient_evidence: true` | `COMPLETED` | Empty findings, clear explanation in `metadata`, no fabrication |
| Zero evidence after filtering | `COMPLETED` | Empty findings, explanation `"no relevant sources found in lookback window"`, no Groq call |
| Supabase write fails | `FAILED` | Surface honestly; do not return an in-memory-only result as if persisted |
| All evidence `UNCHANGED` | `COMPLETED` | Carry forward prior findings, `groq_calls=0` (§16.3) |

**Cardinal rule: never fake success.** A run that produced nothing says so. A run that used stale data says how stale. A run where the reasoning layer died returns the evidence it collected and admits the analysis is missing.

### 24.3 Transaction boundaries

- Persist evidence and findings for a run in a **single transaction** with the terminal run-status update, so a run is never `COMPLETED` with partially-written children.
- Write the cache row **only after** that transaction commits successfully, and only for `COMPLETED` runs. Never cache a `FAILED` or `PARTIAL_FAILURE` result.
- Run-status transitions during execution (PLANNING → RETRIEVING → …) are committed individually so progress is observable, but they are *state*, not results.

### 24.4 Retries and timeouts

| Operation | Timeout | Retries | Backoff |
|---|---|---|---|
| Tavily search/extract | 20s | 2 | 1s, 3s |
| Tavily research (deep) | 60s | 1 | 3s |
| Tavily 429 | — | 2 | 5s, 15s |
| Groq analyze | 30s | 1 | 2s |
| Supabase write | 10s | 2 | 0.5s, 2s |

Retries must be idempotent — never double-count `tavily_calls`/`groq_calls` on a retried attempt; count attempts separately from successes if both matter.

---

## 25. Idempotency

| Situation | Behavior |
|---|---|
| Same request, valid cache | Return cached result, `200`, `cache_hit=true`, no new run row |
| Same request, expired cache | New run |
| Same request, `force_refresh=true` | New run, cache bypassed and then overwritten on success |
| Same request while one is in flight | `202` with the existing `research_run_id` — never a duplicate run |
| Client retries a `POST` after a timeout | Concurrency check (§21.4) catches it and returns the in-flight run |

The `request_hash` is the idempotency key throughout. It is computed once, stored on the run, and used for cache lookup, concurrency detection, and change-detection lineage.

---

## 26. Logging / Observability

Structured events, emitted through the **existing logger** `[VERIFY]`. Every event carries `research_run_id`, `request_hash`, `brand`, `market`, `research_type`.

```
research.requested            {request summary, no secrets}
research.validation_failed    {field errors}
research.cache_checked        {cache_key}
research.cache_hit            {cached_run_id, age_hours}
research.cache_miss           {reason: "expired" | "absent" | "force_refresh"}
research.planned              {complexity, query_count, estimated_tavily_calls, rationale}
research.tavily_started       {operation, query}
research.tavily_completed     {operation, results_count, duration_ms}
research.tavily_failed        {operation, error_class, attempt}
research.normalized           {input_count, output_count}
research.deduplicated         {removed_count, by_url, by_content, by_source}
research.filtered             {relevant, uncertain, irrelevant}
research.change_detected      {new, changed, unchanged, removed}
research.groq_started         {evidence_count, payload_chars}
research.groq_completed       {findings_returned, duration_ms}
research.groq_skipped         {reason}
research.groq_validation      {dropped_findings, reasons[]}
research.groq_failed          {error_class, attempt}
research.findings_generated   {count, avg_confidence}
research.persisted            {evidence_rows, finding_rows}
research.completed            {status, duration_ms, tavily_calls, groq_calls}
research.failed               {status, error_class, stage}
```

These must be sufficient to debug: Tavily failures, Groq failures, Supabase failures, malformed requests, duplicate processing, unexpectedly empty results, and slow stages.

**Never log:** `TAVILY_API_KEY`, `GROQ_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, full auth headers, or complete raw vendor payloads containing credentials. Raw response bodies may be logged at DEBUG level only, with a redaction pass applied first.

---

## 27. Security

**Environment variables (backend only):**
```
TAVILY_API_KEY
GROQ_API_KEY
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

`[VERIFY]` the existing config/settings mechanism and add these to it — do not introduce a second one. Add all four to `.env.example` with placeholder values.

**Hard rules:**
- Keys live in environment variables only. Never hardcoded, never committed, never logged, never in an API response, never sent to the frontend.
- The frontend calls only the JA Assure backend. It never holds a Tavily, Groq, or Supabase service-role credential.
- The service-role key is backend-only by definition — if the frontend needs any direct Supabase access, that is an anon-key + RLS question and is **out of scope** for this agent `[VERIFY]` how the existing app handles it.
- Add a startup check that fails fast with a clear message if a required key is missing, rather than failing mid-run on the first API call.
- Include a security test asserting that no endpoint response body contains any configured secret value (§30).

---

## 28. Cost Control

Ranked by impact:

1. **Cache first, always.** No Tavily or Groq call happens before the cache check. A cache hit costs zero external calls.
2. **Skip Groq when nothing changed** (§16.3). Repeated runs over a stable news cycle cost zero Groq calls.
3. **Deterministic planning.** Query construction, complexity scoring, and routing use zero LLM calls.
4. **Deterministic processing.** Normalization, hashing, dedup, date filtering, relevance scoring, change detection, and most of confidence scoring are pure Python — zero AI calls.
5. **One batched Groq call per run**, never per article. A 40-source run costs one Groq call, not forty.
6. **Query budget caps** (§9.3) bound the maximum Tavily spend per run regardless of input size.
7. **Extract only when snippets are insufficient** (§10.3), never by default.
8. **`research` (deep) at most once per run, HIGH complexity only.** `crawl` off by default.
9. **`max_sources` ceiling** enforced at the adapter boundary.
10. **In-flight deduplication** (§21.4) prevents double-spend from double-clicks and client retries.

**Report cost honestly.** Persist `tavily_calls` and `groq_calls` per run, and surface "calls avoided" in the UI as a count (cache hits, Groq skips). Do **not** display monetary savings unless real configured pricing is used in the calculation — an invented dollar figure undermines everything else.

---

## 29. Adapter Architecture

Business logic must not depend on vendor SDK details.

| Component | Responsibility |
|---|---|
| `ResearchPlanner` | Request → `ResearchPlan`. Pure, deterministic, no I/O. |
| `TavilyResearchAdapter` | `PlannedQuery` → `list[RawSource]`. Owns SDK, retries, timeouts, vendor error translation. |
| `EvidenceProcessor` | `list[RawSource]` → `list[Evidence]`. Normalize, hash, dedup, filter, classify quality/relevance. Pure. |
| `ChangeDetector` | Current evidence + prior run → change statuses + identity keys. Pure. |
| `GroqAnalysisAdapter` | `AnalysisPayload` → validated `AnalysisResult`. Owns SDK, prompt, schema, parsing, retries. |
| `ResearchAnalyzer` | Decides *whether* to call Groq, builds the payload, applies §17.5 validation. |
| `ConfidenceScorer` | Findings + evidence → confidence scores + breakdowns. Pure, deterministic except the 15% AI component. |
| `CacheManager` | Hash, key, lookup, write, expiry, in-flight detection. |
| `ResearchRepository` | All Supabase reads/writes. The only module that knows the DB. |
| `ResearchManager` | Orchestration (§30). Calls everything above; contains no vendor code and no SQL. |

**Testability consequence:** `ResearchPlanner`, `EvidenceProcessor`, `ChangeDetector`, and `ConfidenceScorer` are pure functions with no I/O and are unit-testable without any network or database. That's deliberate — it's where most of the system's actual logic lives.

`[VERIFY]` existing module/class naming conventions and adapt these names. The names are negotiable; the boundaries are not.

---

## 30. Research Manager (orchestration)

```python
def run(request: ResearchRequest) -> ResearchResult:
    # 1. Validate (Pydantic + business rules). Fail → 422, no run row.
    validated = validate(request)

    # 2. Hash + cache key
    request_hash = compute_hash(validated)
    cache_key = build_cache_key(validated.research_type, request_hash)

    # 3. In-flight duplicate check → return 202 with existing run id
    if inflight := repo.find_inflight(request_hash):
        return ResearchResult.in_flight(inflight)

    # 4. Cache check (unless force_refresh)
    if not validated.force_refresh:
        if cached := cache.get_valid(cache_key):
            return repo.load_result(cached.research_run_id, cache_hit=True)

    # 5. Create run row, status=PLANNING
    run = repo.create_run(validated, request_hash, status=PLANNING)

    try:
        # 6-7. Plan (deterministic) + persist plan for auditability
        plan = planner.plan(validated)
        repo.attach_plan(run.id, plan)

        # 8-9. Execute Tavily per plan; per-query failures isolated
        repo.set_status(run.id, RETRIEVING)
        raw_sources, tavily_calls, failed_queries = tavily.execute(plan, max_sources=validated.max_sources)

        if not raw_sources and failed_queries:
            return finalize_failure(run, "All research queries failed", stale_fallback=cache.get_stale(cache_key))

        # 10-12. Deterministic processing
        repo.set_status(run.id, NORMALIZING)
        evidence = processor.normalize(raw_sources, validated)
        evidence = processor.deduplicate(evidence)
        repo.set_status(run.id, FILTERING)
        evidence = processor.filter_by_date(evidence, validated.lookback_days)
        evidence = processor.score_relevance(evidence, validated)

        # 13. Change detection against most recent completed run
        repo.set_status(run.id, DETECTING_CHANGES)
        prior = repo.find_prior_completed_run(validated.brand, validated.market, validated.research_type)
        evidence, change_summary = detector.detect(evidence, prior)

        # 14. Decide whether Groq is necessary
        repo.set_status(run.id, ANALYZING)
        decision = analyzer.should_analyze(evidence, change_summary, prior)
        if not decision.should_call:
            findings = analyzer.carry_forward(prior) if decision.carry_forward else []
            groq_calls = 0
        else:
            # 15-16. Single batched Groq call + strict validation
            result = groq.analyze(analyzer.build_payload(evidence, validated))
            findings, dropped = analyzer.validate_and_filter(result, evidence)
            groq_calls = 1

        # 17. Deterministic confidence scoring
        findings = scorer.score(findings, evidence)

        # 18-20. Persist evidence + findings + terminal run state in ONE transaction
        status = PARTIAL_FAILURE if failed_queries else COMPLETED
        repo.persist_run_results(run.id, evidence, findings, metrics, status)

        # 21. Cache only on clean COMPLETED
        if status == COMPLETED:
            cache.write(cache_key, request_hash, run.id, ttl_for(validated.research_type))

        # 22. Return
        return repo.load_result(run.id, cache_hit=False)

    except GroqError as e:
        # Evidence is still valuable — persist it, report the analysis gap honestly
        repo.persist_run_results(run.id, evidence, [], metrics, PARTIAL_FAILURE, error=str(e))
        return repo.load_result(run.id)
    except Exception as e:
        repo.set_failed(run.id, error=classify(e))
        raise
```

---

## 31. Data Flow

```
POST /discover/run
        ↓
Request validation (Pydantic + business rules)
        ↓
request_hash → cache_key
        ↓
In-flight check ──→ 202 if duplicate
        ↓
Cache check ──────→ 200 cached result if fresh
        ↓ miss
Create research_run (PLANNING)
        ↓
Research Planner (deterministic) → ResearchPlan (persisted)
        ↓
Tavily: search / extract / crawl / research per plan
        ↓
Raw sources
        ↓
Normalization (URL, content, dates)
        ↓
Hashing (url_hash, content_hash)
        ↓
Deduplication (url → content → source)
        ↓
Date filtering (lookback window)
        ↓
Source quality classification
        ↓
Relevance scoring → RELEVANT / UNCERTAIN / IRRELEVANT
        ↓
Change detection vs prior run → NEW / CHANGED / UNCHANGED
        ↓
Evidence corpus
        ↓
Should-analyze decision ──→ skip Groq if all UNCHANGED
        ↓
Groq (single batched call, strict JSON schema)
        ↓
Output validation (evidence ids, URLs, enums, ranges)
        ↓
Confidence scoring (deterministic + 15% AI component)
        ↓
Supabase (single transaction: evidence + findings + run status)
        ↓
Cache write (only on COMPLETED)
        ↓
API response
        ↓
Frontend: findings → evidence → source URL
```

---

## 32. Existing-Codebase Inspection (MANDATORY GATE)

**The implementing agent must complete this before creating or modifying any file.** No exceptions. Blind file creation against an existing repo is the primary failure mode this section exists to prevent.

### 32.1 Inspect

1. Frontend structure — routing, pages, component organization.
2. Backend structure — app entrypoint, router registration, service/module layout.
3. Package dependencies — `requirements.txt` / `pyproject.toml` / `package.json`. Is `tavily-python` or `groq` already present? Is `supabase-py` or SQLAlchemy in use?
4. Environment configuration — how settings are loaded and validated.
5. Existing API routes — naming conventions, prefixes, response envelope shape.
6. Existing services — is there already an HTTP client wrapper, retry helper, or cache utility to reuse?
7. Existing database schema — every table currently present.
8. Existing Supabase migrations — location, naming convention, tooling.
9. Existing authentication, if any.
10. Existing UI components — cards, badges, status indicators, loading states.
11. Existing tree/fruit interaction — how a fruit click currently routes and what state it reads.
12. Existing API client — fetch wrapper, error handling, typing.
13. Existing error handling — exception classes, HTTP error mapping.
14. Existing logging — logger setup, format, levels.
15. Existing deployment configuration.

### 32.2 Produce a gap analysis

Before writing code, output a table:

| Item | EXISTING | MISSING | NEEDS MODIFICATION | CAN BE REUSED | SHOULD NOT BE TOUCHED |
|---|---|---|---|---|---|

Cover at minimum: config/settings, logger, HTTP/retry utilities, DB client, migration tooling, router registration, error convention, API client, tree component, Discover workspace component, status/badge components, and every table in §22.

### 32.3 Rules

- **If it exists, reuse it.** Never create a second config loader, second logger, second DB client, or second API error shape.
- **If naming conflicts**, follow the repo's convention, not this document's.
- **If a table already exists**, reference it; do not recreate or alter it beyond what the Research Agent genuinely needs.
- **If something is ambiguous**, state the ambiguity in the gap analysis and pick the option most consistent with existing code — then note the choice.
- **Do not refactor unrelated code.** Scope creep in someone else's codebase is a defect, not initiative.

---

## 33. Database Migration Strategy

1. **Inspect the existing schema first** (via Supabase MCP in development, or by reading existing migration files).
2. **Create minimal, additive migrations only.** New tables and new indexes. No destructive statements.
3. **Never** `DROP`, never recreate an existing table, never alter a column another feature depends on.
4. **Do not modify unrelated tables.**
5. **Preserve existing naming conventions** — if existing tables use `created_at`/`updated_at` with a specific trigger pattern, match it.
6. **Add indexes only where §22 justifies them** — specifically the change-detection lookup path and the hash lookups.
7. **Test migration safety:** apply to a development database, verify existing data is untouched, verify the rollback path exists.
8. **Supabase MCP is development-time only.** Runtime code uses the normal Supabase/Postgres client. No runtime dependency on MCP, ever.
9. If a table in §22 already exists under a different name with compatible semantics, **use it** and document the mapping rather than adding a near-duplicate.

---

## 34. Future Strategize Handoff

The Research Agent produces `ResearchFinding[]` and nothing more. It **must not** invoke, import, or know about a Strategize Agent.

**Output contract (stable, versioned):**

```json
{
  "research_run_id": "uuid",
  "brand": "Jaguar Transit",
  "market": "Singapore",
  "research_type": "competitor_monitoring",
  "completed_at": "2026-09-16T09:45:00Z",
  "findings": [
    {
      "finding_type": "product_launch",
      "title": "...",
      "summary": "...",
      "why_it_matters": "...",
      "opportunity": "...",
      "importance_score": 87,
      "relevance_score": 91,
      "confidence_score": 74,
      "change_status": "NEW",
      "conflicts": [],
      "supporting_evidence_ids": ["evidence_001", "evidence_004"]
    }
  ]
}
```

A future central orchestrator will coordinate `Research → (approval/orchestration) → Strategize`. That orchestration is **out of scope**. The only requirement on this implementation is that the findings are complete, structured, and evidence-linked enough to be consumed later without modification.

---

## 35. Testing Strategy

### Unit (no network, no DB — these cover most of the real logic)
- Request validation: required fields, enum rejection, range clamping, list normalization/dedup/caps.
- `request_hash`: stability across key ordering and whitespace; sensitivity to semantic changes; insensitivity to `max_sources`/`force_refresh`.
- Cache key generation.
- URL normalization: each rule in §12.1, plus idempotency (normalizing twice = normalizing once).
- Content normalization and truncation flagging.
- Content hashing: stability, prefix-bounding behavior.
- Deduplication: by URL, by content, by source; survivor-preference correctness; **order independence**.
- Date filtering: inside/outside window, missing dates retained not dropped.
- Source quality classification: each tier, unknown-domain default.
- Relevance scoring: component weights, boundary labels at 0.35 and 0.60.
- Change detection: all four states; identity-key stability across runs.
- Confidence scoring: each component, all four penalties, floor/ceiling, breakdown presence.
- Planner: complexity thresholds, query budget truncation, empty-plan guard, discovery-query generation.

### Integration (mocked vendors)
- `TavilyResearchAdapter` against recorded/fixture responses for each operation.
- `GroqAnalysisAdapter` against fixture responses including valid, malformed, and hallucinated outputs.
- `ResearchRepository` against a test database.
- `ResearchManager` full happy path, cache-hit path, and Groq-skip path.

### Failure tests (these matter most for the demo)
- Tavily unavailable → `FAILED` with no fabricated evidence.
- Tavily unavailable + expired cache → `PARTIAL_FAILURE` with stale result correctly labeled.
- Partial Tavily failure → `PARTIAL_FAILURE`, evidence retained.
- Groq unavailable → `PARTIAL_FAILURE`, **evidence persisted**, findings empty.
- Malformed Tavily response → skipped source, run continues.
- Malformed Groq JSON → retry then `PARTIAL_FAILURE`.
- **Groq references a nonexistent evidence id** → finding dropped, counted, logged.
- **Groq invents a URL not in the evidence set** → finding dropped, counted, logged.
- Empty evidence → `COMPLETED`, empty findings, explanation, no Groq call.
- Conflicting evidence → conflict preserved, confidence penalized.
- All-unchanged evidence → Groq skipped, findings carried forward.
- Duplicate concurrent request → `202`, single run.
- Supabase write failure → `FAILED`, honest reporting.

### Security
- No endpoint response body contains any configured secret value.
- No log line at any level contains a configured secret value (assert against a redaction helper).
- Startup fails clearly when a required env var is absent.

---

## 36. Implementation Phases

Each phase ends with its tests passing before the next begins.

| Phase | Deliverable | Depends on |
|---|---|---|
| **0** | **§32 codebase inspection + gap analysis.** No code. | — |
| 1 | Foundation: Pydantic schemas, enums, research-type registry, config additions, exception classes, logging events | 0 |
| 2 | `ResearchManager` skeleton + run-state machine + repository interface (stubs) | 1 |
| 3 | `CacheManager`: hashing, keys, TTLs, lookup, in-flight detection | 1 |
| 4 | `ResearchPlanner` (fully deterministic, fully unit-tested) | 1 |
| 5 | `TavilyResearchAdapter`: search first, then extract; crawl/map/research last | 1 |
| 6 | `EvidenceProcessor`: normalize, hash, dedup, date filter, quality, relevance | 1 |
| 7 | `ChangeDetector` + identity keys | 6 |
| 8 | `GroqAnalysisAdapter` + prompt + strict schema + §17.5 validation | 6 |
| 9 | `ConfidenceScorer` + breakdown persistence | 7, 8 |
| 10 | `ResearchRepository` + migrations (§33) + transactional persistence | 0, 2 |
| 11 | FastAPI endpoints (§23), wired into existing router conventions | 10 |
| 12 | Frontend integration into the existing Discover workspace | 11 |
| 13 | Failure tests, security tests, demo hardening, seeded demo data | all |

**Ordering rationale:** planner and evidence processing (4, 6) come before Groq (8) so that by the time the LLM is introduced, everything feeding it is deterministic and tested. This makes Groq failures easy to isolate, and it means a demo can show real evidence collection even if the reasoning layer is misbehaving.

---

## 37. Frontend Integration

**Do not redesign the frontend.** Extend the existing Discover fruit / workspace `[VERIFY]`.

**Flow:**
```
Tree → Discover fruit → Research configuration
  (brand, market, research_type, objective, competitors, topics, lookback_days, force_refresh)
  → [Run Research]
  → Progress / activity (run status)
  → Results: findings list
  → Finding detail → supporting evidence → source URL
```

**Must display:**
- Run status, including `SKIPPED` (cache hit) and `PARTIAL_FAILURE` — with the reason, not a generic spinner-to-error.
- Cache state: hit/miss, age, "fresh until". A cache hit should be visibly *good news*, not a hidden optimization.
- Counts: sources checked, unique, relevant.
- Per finding: type, title, summary, why it matters, opportunity, importance, confidence (with breakdown on hover/expand), change status badge.
- Per evidence: source name, quality tier, URL (clickable), published date, retrieved date, relevance label.
- Conflicts, where present, shown as a first-class element of the finding — not hidden.
- Cost transparency: `tavily_calls`, `groq_calls`, and calls avoided.
- Stale-data banner with exact age when `stale: true`.

**Must not:** hold or receive any API key; call Tavily, Groq, or Supabase service endpoints directly.

**Reuse existing components** for cards, badges, status pills, loading and error states `[VERIFY]`. Add new components only where nothing suitable exists.

---

## 38. Architectural Principles (enforced throughout)

1. Evidence before conclusions.
2. Tavily researches; Groq reasons.
3. Deterministic logic before AI.
4. Cache before API calls.
5. Every finding traceable to evidence.
6. AI cannot invent facts.
7. Importance and confidence are separate.
8. Preserve conflicting evidence.
9. Fail honestly.
10. Vendor SDKs stay behind adapters.
11. Research stays isolated from future agents.
12. Reuse the existing codebase.
13. Prefer simple architecture over unnecessary abstraction.
14. Optimize for reliability and demoability.
15. Minimize API cost.
16. Never expose secrets.

---

## 39. Demo Scenario

**Brand:** Jaguar Transit · **Market:** Singapore · **Type:** `competitor_monitoring` · **Objective:** "Identify recent competitor activity"

**Sequence:**
1. User opens the Tree, clicks the Discover fruit.
2. Enters brand `Jaguar Transit`, market `Singapore`, type `competitor_monitoring`, objective as above.
3. Clicks **Run Research**.
4. System checks cache → miss → shown explicitly in the activity panel.
5. Planner generates the plan; the UI shows complexity, query count, and rationale **before** any external call.
6. Tavily executes; the activity panel shows each query completing.
7. Evidence is collected; counts appear (checked → unique → relevant).
8. Python dedups and filters; the UI shows how many were removed and why.
9. Change detection labels items NEW / CHANGED / UNCHANGED.
10. Groq is called **once**; the UI shows "1 reasoning call over N evidence items."
11. Findings render, ranked by importance, each with confidence and a change badge.
12. User expands a finding → sees the supporting evidence → clicks through to the real source URL.
13. Run a **second identical request** → cache hit → `SKIPPED`, 0 Tavily calls, 0 Groq calls, result served instantly.

Step 13 is the one worth rehearsing: it demonstrates the cache-first architecture in about eight seconds, and it's real behavior, not a staged effect.

**Demo data note:** seed one prior completed run for the same `(brand, market, research_type)` so change detection has something to diff against and `NEW`/`UNCHANGED` badges are meaningful rather than uniformly `NEW`.

---

## 40. Definition of Done

The Research Agent is complete when **all** of the following hold:

- [ ] §32 inspection and gap analysis completed and documented before any code was written.
- [ ] User can initiate research from the existing Discover UI.
- [ ] Backend validates the request and rejects malformed input with field-level errors.
- [ ] Cache is checked before any external call; a repeat request returns a cache hit with 0 Tavily and 0 Groq calls.
- [ ] Planner produces a deterministic, persisted, inspectable plan; plan rationale is visible in the UI.
- [ ] Tavily performs the external research; operation routing follows §10.2.
- [ ] Evidence is collected, normalized, hashed, deduplicated, date-filtered, quality-classified, and relevance-labeled.
- [ ] Nothing retrieved is silently discarded; `IRRELEVANT` items are persisted and viewable.
- [ ] Change detection produces NEW / CHANGED / UNCHANGED against the prior run.
- [ ] Groq is called at most once per run, over batched evidence, and is skipped when nothing changed.
- [ ] Groq output is strictly schema-validated; findings referencing unknown evidence ids or fabricated URLs are dropped and counted.
- [ ] Every persisted finding references at least one real evidence id from the same run.
- [ ] Confidence is computed deterministically with a persisted, displayable breakdown; importance and confidence are separate fields.
- [ ] Conflicting evidence is preserved and penalizes confidence rather than being resolved away.
- [ ] Runs, evidence, findings, and cache rows persist to Supabase; results and status are written in one transaction.
- [ ] Frontend displays findings, confidence, change status, and clickable source evidence.
- [ ] Failures report honestly: `FAILED`, `PARTIAL_FAILURE`, stale-data labeling, and empty-result explanations all behave per §24.2.
- [ ] Groq failure preserves collected evidence rather than discarding the run.
- [ ] API keys are backend-only; no secret appears in any response or log; startup fails fast when one is missing.
- [ ] Unit tests cover all pure logic in §35; failure and security tests pass.
- [ ] No other agent (Strategize, Create, Protect, Acquire, Learn) has been implemented.
- [ ] No LangGraph, CrewAI, vector DB, RAG, Playwright, proxy infrastructure, or microservice was introduced.
- [ ] No existing table was dropped, recreated, or modified beyond additive necessity.

---

*End of research_agents.md — v1.0*