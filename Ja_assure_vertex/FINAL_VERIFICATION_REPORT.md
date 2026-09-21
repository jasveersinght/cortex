# JA Assure Research / Discover Agent
# Final Verification Report

## 1. Verification Date

- **Date:** 2026-09-16
- **Auditor:** Antigravity AI Senior Backend Engineer & Auditor
- **Repository:** `JA_ASSURE_VERTEX`
- **Scope:** Research / Discover Agent backend only

---

## 2. Repository State

- **Branch / Status:** Clean workspace, not a git repository (`.git` absent).
- **Python Environment:** Python 3.11.9 running in local virtual environment `venv/`.
- **Dependencies (`requirements.txt`):**
  - `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`, `python-dateutil`, `httpx`, `tavily-python`, `groq`, `supabase`, `python-dotenv`, `pytest`.
  - All dependencies installed and functional.
- **Module Count:** 22 core Python modules + 7 test modules + 2 scripts + 1 SQL migration.
- **Syntactic Integrity:** All Python files compiled with zero errors (`py_compile`). All 22 application modules imported cleanly with zero circular dependencies or missing symbols.

---

## 3. Previous Audit Status

The previous audit (`AUDIT_REPORT.md`) recorded:
- 122/122 unit/integration tests passed.
- FastAPI booted successfully.
- Supabase connectivity established.
- Tavily and Groq real-provider integrations tested.
- End-to-end Jaguar Transit + Singapore research run completed.
- Cache hit verified (200 on repeat).
- Four non-critical remaining items identified:
  - **R1 (LOW):** Finding `created_at` set to `null` on live runs.
  - **R2 (INFO):** Confidence scores low (29–41) due to source quality and undated penalties (expected behavior).
  - **R3 (INFO):** `lookback_days` returned as `null` in `POST /discover/run` response.
  - **R4 (INFO):** Third-party deprecation warnings from Starlette/Supabase.

---

## 4. Issues Rechecked

### R1 — Finding created_at
- **Previous State:** Live research runs returned `"created_at": null` inside finding objects in `POST /discover/run`, `GET /discover/{id}`, and `GET /discover/{id}/findings`.
- **Root Cause:** In `app/research/manager.py`, `_load_result` constructed `Finding` dataclasses from database rows without passing `created_at`. Similarly, in `app/research/repositories/supabase.py`, `save_findings` did not include `created_at` in the inserted dictionary. In `app/api/routes/discover.py`, `get_research_run` and `get_findings` omitted `created_at` when constructing `FindingResponse`.
- **Fix:**
  1. Updated `save_findings` in `app/research/repositories/supabase.py` to persist `f.created_at.isoformat()`.
  2. Updated `_load_result` and `_carry_forward_findings` in `app/research/manager.py` to parse and populate `created_at` with UTC awareness.
  3. Updated `get_research_run` and `get_findings` in `app/api/routes/discover.py` to map `created_at=row.get("created_at")` into `FindingResponse`.
  4. Added regression tests in `tests/test_api_endpoints.py` and `tests/test_manager_pipeline.py`.
- **Verification:** Live E2E test confirmed all findings across `POST /discover/run`, `GET /discover/{id}`, and `GET /discover/{id}/findings` now return ISO-8601 UTC timestamps (e.g., `'2026-09-16T06:04:37.667455Z'`). Zero null values.

### R2 — Confidence scores
- **Verification:** Inspected `app/research/processing/confidence.py`. Verified that importance (strategic AI significance) and confidence (evidence strength) remain completely separate. The 5 components:
  - 0.30 * Source Quality (Tier 1..6)
  - 0.25 * Corroboration (independent sources logarithmic scale)
  - 0.15 * Independence (distinct domains / total sources)
  - 0.15 * Recency (decay over lookback window)
  - 0.15 * AI Confidence self-report
  - Penalties: -15 for conflicts, -10 for all low-quality, -10 for all undated. Clamped to [0, 100].
- **Conclusion:** Expected and correct behavior. The lower scores observed in demo runs (29–41) were verified to be mathematically accurate consequences of social/aggregator domain tiers (Tier 5–6) and missing publish dates. The logic was left completely unchanged without artificial inflation.

### R3 — lookback_days
- **Previous State:** `POST /discover/run` response returned `"lookback_days": null` even when submitted as `30` in the request, while `GET /discover/{id}` returned `30`.
- **Root Cause:** `ResearchResult` domain model in `app/research/models.py` lacked `lookback_days` and `objective` fields. Consequently, `_result_to_response` in `app/api/routes/discover.py` could not map `lookback_days` to `ResearchRunResponse`.
- **Fix:**
  1. Added `lookback_days: int | None = None` and `objective: str | None = None` to `ResearchResult` in `app/research/models.py`.
  2. Updated `_load_result` in `app/research/manager.py` to populate `lookback_days=run_data.get("lookback_days")` and `objective=run_data.get("objective")`.
  3. Updated `_result_to_response` in `app/api/routes/discover.py` to map `lookback_days=result.lookback_days` and `objective=result.objective`.
  4. Added regression tests asserting `data["lookback_days"] == 30` and `data["objective"] == "Identify recent competitor activity"`.
- **Verification:** Live E2E test confirmed `POST /discover/run` returns `lookback_days: 30` matching request.

### R4 — Third-party warnings
- **Verification:** Ran pytest and analyzed all 6 emitted warnings:
  - `StarletteDeprecationWarning`: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead. (FastAPI testclient internal)
  - `DeprecationWarning`: The `anyio.abc.BlockingPortal` alias is deprecated. (AnyIO/Starlette internal)
  - `DeprecationWarning`: The `'timeout'` and `'verify'` parameters are deprecated in `SyncPostgrestClient`. (Supabase Python SDK internal)
- **Conclusion:** All warnings originate from third-party vendor libraries (`fastapi`, `starlette`, `supabase-py`). None originate from JA Assure application code. Upgrading major packages risks breaking working functionality right before hackathon submission. Documented as non-actionable; runtime behavior is completely unaffected. Additionally, fixed a Windows cp1252 console logging issue by replacing unicode arrow `\u2192` with ASCII `->` in `planner.py`.

---

## 5. Final Architecture

```
Research Request (POST /discover/run)
       ↓
Request Validation (Pydantic schemas)
       ↓
Deterministic Planning (Research Planner)
       ↓
External Web Retrieval (Tavily Adapter)
       ↓
Traceable Evidence Corpus
       ↓
Pure Python Processing Pipeline
  ├── Normalization (URL canonicalization, content sanitization, hashing)
  ├── Deduplication (URL, Content SHA-256, Source-level)
  ├── Date Filtering & Source Quality Scoring (Tier 1–6)
  └── Change Detection (NEW, CHANGED, UNCHANGED, REMOVED)
       ↓
Reasoning & Synthesis (Groq Compound Model — 1 batched call)
       ↓
Hallucination Validation & Clamping (ID matching, URL cross-check)
       ↓
Transparent Confidence Scoring (5 components + penalties)
       ↓
Supabase Database (5 relational tables) + Cache Persistence
       ↓
FastAPI Response (Clean JSON contract for Frontend Team)
```

---

## 6. Runtime Flow

1. **Request Intake:** `POST /discover/run` validates `brand`, `market`, `research_type`, `lookback_days`, `max_sources`.
2. **Deterministic Hashing:** Request parameters are canonicalized and hashed to generate a unique `cache_key`.
3. **In-Flight Protection:** Checks Supabase for any active in-flight run with the same hash (returns HTTP 202 if in-flight).
4. **Cache Check:** Unless `force_refresh=true`, queries `research_cache`. On hit, loads data and returns HTTP 200 in ~1s with zero API calls.
5. **Run Initialization:** Inserts new run in `research_runs` with status `PLANNING`.
6. **Query Planning:** Deterministic Python query builder instantiates templates based on complexity and entity counts.
7. **Tavily Execution:** Searches web, isolates errors, bounds queries to `max_sources` (20), returns `RawSource` instances.
8. **Python Processing:**
   - Normalizes URLs and content; computes SHA-256 hashes.
   - Deduplicates across 3 tiers (URL, content hash, source domain).
   - Filters by date window and classifies source quality (Tiers 1 to 6).
   - Compares against prior run to classify evidence as `NEW`, `CHANGED`, or `UNCHANGED`.
9. **Conditional Groq Reasoning:**
   - If all evidence is unchanged, Groq is skipped and prior findings carried forward.
   - If new/changed evidence exists, builds single structured payload and calls Groq.
10. **Hallucination Protection:**
    - Verifies all `supporting_evidence_ids` match collected evidence.
    - Drops findings with fabricated URLs or unknown evidence references.
11. **Explainable Confidence Scoring:** Computes 0–100 score and breakdown metadata.
12. **Supabase Persistence:** Persists evidence to `research_evidence`, findings to `research_findings`, updates `research_runs` to `COMPLETED`, writes `research_cache`.
13. **API Response:** Returns HTTP 201 with populated `ResearchRunResponse`.

---

## 7. Test Results

- **Command Executed:** `pytest tests/ -v`
- **Total Tests:** 125
- **Passed:** 125
- **Failed:** 0
- **Skipped:** 0
- **Warnings:** 6 (upstream third-party Starlette/AnyIO/Supabase deprecations)
- **Execution Time:** 2.52 seconds

### Test Breakdown by Module:
- `tests/test_api_endpoints.py`: 14 tests (endpoints, validation, error codes, secrets, regressions)
- `tests/test_groq_validation.py`: 8 tests (hallucination defense, clamping, drop rules)
- `tests/test_manager_pipeline.py`: 10 tests (end-to-end orchestration, mocks, failure modes)
- `tests/test_normalization.py`: 18 tests (URL cleaning, content hashing, domain extraction)
- `tests/test_planner.py`: 13 tests (complexity scoring, query generation, budget caps)
- `tests/test_processing.py`: 37 tests (dedup, source quality, relevance, date filter, change detection, confidence)
- `tests/test_validation.py`: 25 tests (Pydantic schema constraints, hash stability)

---

## 8. API Verification

| Endpoint | Method | Expected Status | Actual Status | Verification Details |
|---|---|---|---|---|
| `/health` | GET | 200 OK | 200 OK | Verified `supabase: ok`, `tavily: configured`, `groq: configured` |
| `/docs` | GET | 200 OK | 200 OK | Swagger UI loaded with all 6 endpoints documented |
| `/discover/status` | GET | 200 OK | 200 OK | Returns summary list with latest runs, counts, status |
| `/discover/run` (invalid) | POST | 422 Unprocessable | 422 Unprocessable | Returned `INVALID_RESEARCH_REQUEST` with validation error details |
| `/discover/{missing_id}` | GET | 404 Not Found | 404 Not Found | Returned `RESEARCH_RUN_NOT_FOUND` |
| `/discover/run` (live) | POST | 201 Created | 201 Created | Live pipeline executed, populated findings with `created_at` and `lookback_days` |
| `/discover/run` (cached) | POST | 200 OK | 200 OK | Cache hit, response time ~1.07s, zero external provider calls |
| `/discover/{id}` | GET | 200 OK | 200 OK | Full run details, lookback_days, findings with `created_at` |
| `/discover/{id}/findings` | GET | 200 OK | 200 OK | Filterable list of findings with compact supporting evidence |
| `/discover/{id}/evidence` | GET | 200 OK | 200 OK | Audit trail of all 15 collected evidence rows |

---

## 9. Cache Verification

- **Cache Miss:** When a request is first run or `force_refresh=true`, cache miss is logged (`research.cache_miss: reason=force_refresh`), full Tavily and Groq pipelines execute, and cache is written with 24-hour TTL.
- **Cache Hit:** Repeating the exact same request hits cache (`research.cache_hit: run_id=...`). Returns HTTP 200 in 1.07 seconds. Tavily calls: 0, Groq calls: 0.
- **Force Refresh:** Sending `"force_refresh": true` bypasses cache, runs live external research, creates a new run ID, and refreshes the cache entry.
- **In-Flight Concurrency:** Tested via `TestDiscoverRunEndpoint.test_run_inflight_returns_202`; returns HTTP 202 with `status: IN_FLIGHT` to avoid duplicate provider spend.

---

## 10. Tavily Verification

- **Verification Mode:** **TESTED AGAINST REAL PROVIDER** (Live during this audit session).
- **Execution Log:**
  - `Tavily search: query='Jaguar Transit competitors Singapore', max_results=10` -> 10 results
  - `Tavily search: query='top companies Singapore similar to Jaguar Transit', max_results=10` -> 10 results
  - `Max sources (20) reached, stopping queries`
  - `research.tavily_completed: sources=20, calls=2, failed=0`
- **Isolation:** Tavily independently manages all web retrieval. No Groq web searching occurs.

---

## 11. Groq Verification

- **Verification Mode:** **TESTED AGAINST REAL PROVIDER** (Live during this audit session).
- **Execution Log:**
  - `research.groq_started: evidence_count=9`
  - `Groq analyze: 9 evidence items, payload_chars=14774, model=groq/compound`
  - `research.groq_completed: findings_returned=3, insufficient=False`
  - Findings:
    1. "Jaguar Transit recognized as leader in ASEAN transit insurance" (Type: `industry_trend`)
    2. "Jaguar Transit plans entry into Turkey, Dubai and Brazil" (Type: `market_entry`)
    3. "Jaguar Transit forms distribution partnership with AgaDigital in Turkey" (Type: `partnership`)
  - Dropped findings: 0 (100% compliant with schema and evidence IDs).

---

## 12. Supabase Verification

- **Migration Status:** Baseline schema (`migrations/001_baseline.sql`) fully deployed.
- **Tables Active:** `competitors`, `research_runs`, `research_evidence`, `research_findings`, `research_cache`.
- **Live Persistence Verified:**
  - Run `225fa7ef-de58-4f84-bd49-d2b01f401ffc` created and marked `COMPLETED`.
  - 15 evidence rows inserted into `research_evidence`.
  - 3 finding rows inserted into `research_findings` with valid `created_at` timestamps.
  - Cache row inserted into `research_cache` with 24-hour expiration.

---

## 13. Hallucination Protection

Adversarial unit tests in `tests/test_groq_validation.py` verified:
1. **Nonexistent Evidence ID:** Dropped immediately.
2. **Fabricated URL:** Dropped immediately.
3. **Invalid Finding Type:** Coerced safely to `"other"`.
4. **Out-of-Range Scores:** Clamped to `[0, 100]`.
5. **Partially Valid Evidence IDs:** Invalid removed; finding retained only if at least one genuine ID remains.
6. **Empty Findings / Insufficient Evidence:** Handled gracefully without fabrication.
7. **Title Length:** Truncated cleanly to 140 characters.

---

## 14. Change Detection

- **Verified Statuses:**
  - `NEW`: Evidence with new URL hash.
  - `CHANGED`: Evidence with same URL but updated content hash.
  - `UNCHANGED`: Evidence with identical URL and content hash.
  - `REMOVED`: Evidence present in prior run but absent in current run.
- **Live Run Metric:**
  `research.change_detected: {'new': 6, 'changed': 5, 'unchanged': 4, 'removed': 10}`
- **Optimization:** If all evidence is unchanged, Groq analysis is skipped completely, saving 100% of LLM cost.

---

## 15. Failure Handling

- **Groq Failure:** Unit tested (`test_groq_failure_persists_evidence_partial_failure`). Run marked `PARTIAL_FAILURE`. All collected Tavily evidence remains safely stored in database. Cache is not updated.
- **Partial Tavily Failure:** If one query fails but others succeed, remaining evidence is processed and run completes with `PARTIAL_FAILURE`.
- **Complete Tavily Failure:** If all queries fail and no cache exists, run marked `FAILED`. If stale cache exists, gracefully falls back to stale cache with `stale=true`.
- **Malformed Groq Response:** Output validation drops invalid findings rather than corrupting the database.

---

## 16. Security

- **Secrets Audit:** Automated scan of entire repository for configured secrets from `.env` (`TAVILY_API_KEY`, `GROQ_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`) returned **Zero Leaks**.
- **Source Control:** `.env` is ignored in `.gitignore`. `.env.example` contains only template placeholders.
- **API Responses:** Integration tests explicitly assert that no secret keys appear in headers or JSON bodies of any endpoint.
- **CORS:** Configured with `CORSMiddleware` to allow frontend connection.

---

## 17. Cost Controls

1. **Cache First:** Every request checks `research_cache` before calling Tavily or Groq.
2. **Deterministic Processing in Python:** Hashing, dedup, filtering, change detection, and scoring happen in Python with zero LLM tokens.
3. **Single Batched Groq Call:** Evidence is bundled into a single structured prompt (never called per source).
4. **Source Limit Capping:** Tavily searches halt once `max_sources` (default 20) is reached.
5. **Relevance Filtering:** Irrelevant and low-relevance sources are excluded from the Groq prompt.

---

## 18. Changes Made

1. **`app/research/models.py`**: Added `lookback_days: int | None = None` and `objective: str | None = None` to `ResearchResult`.
2. **`app/research/manager.py`**:
   - In `_load_result`: Populated `lookback_days` and `objective` on `ResearchResult`.
   - In `_load_result`: Parsed and populated `created_at` on loaded `Finding` instances.
   - In `_carry_forward_findings`: Populated `created_at` on carried-forward `Finding` instances.
3. **`app/research/repositories/supabase.py`**:
   - In `save_findings`: Included `"created_at"` in inserted row dictionaries.
4. **`app/api/routes/discover.py`**:
   - In `_result_to_response`: Mapped `lookback_days` and `objective` from `ResearchResult` to `ResearchRunResponse`.
   - In `get_research_run`: Passed `created_at` to `FindingResponse`.
   - In `get_findings`: Passed `created_at` to `FindingResponse`.
5. **`app/research/planner.py`**:
   - Changed log message from `→` to `->` to eliminate `UnicodeEncodeError` in Windows cp1252 consoles.
6. **`tests/test_api_endpoints.py`**:
   - Added regression tests `test_regression_r1_finding_created_at_in_post_run`, `test_regression_r1_finding_created_at_in_get_findings`, and `test_regression_r3_lookback_days_in_post_run`.
   - Updated existing test cases to assert `lookback_days` and non-null `created_at`.
7. **`tests/test_manager_pipeline.py`**:
   - Updated `MockRepo.get_findings_for_run` to include `created_at`.
   - Added assertions for `result.lookback_days == 30` and `result.findings[0].created_at is not None`.
8. **`README.md`**: Updated response description to explicitly mention `lookback_days`, `objective`, and UTC `created_at` timestamps.

---

## 19. Remaining Issues

- **None (Critical / High / Medium / Low):** 0 issues remain.
- **Upstream Third-Party Deprecations (INFO):** Starlette/AnyIO/Supabase internal deprecations are harmless and non-actionable without risky dependency upgrades.

---

## 20. Environment Requirements

The following environment variables in `.env` are required for live provider execution:
```bash
TAVILY_API_KEY=tvly-...
GROQ_API_KEY=gsk_...
GROQ_MODEL=groq/compound
SUPABASE_URL=https://...supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

For test suite execution (`pytest tests/ -v`), **no external credentials are required** (runs 100% offline with mocks in ~2.5 seconds).

---

## 21. Final Readiness

### **READY**

The JA Assure Research / Discover Agent backend has undergone a comprehensive inspection, fix, test, and live verification pass. All 125 automated tests pass with 0 failures, FastAPI boots cleanly, all 6 API endpoints match their OpenAPI contract, live Tavily and Groq provider integrations succeed end-to-end, Supabase persistence and cache hit/miss behavior are verified live, and issues R1 (`created_at`) and R3 (`lookback_days`) are fully resolved. The backend is 100% ready for the frontend team to integrate.
