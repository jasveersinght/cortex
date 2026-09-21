"""Seed demo data for the JA Assure Discover Agent.

Creates a synthetic historical research run for:
  Brand: Jaguar Transit
  Market: Singapore
  Type: competitor_monitoring

This allows change detection to demonstrate NEW/CHANGED/UNCHANGED badges.
All seeded data is clearly marked as synthetic/demo.

Usage:
    python scripts/seed_demo_data.py

Requires: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env
"""

import sys
import os
from datetime import datetime, timezone, timedelta
from uuid import uuid4

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.research.repositories.cache import compute_request_hash, build_cache_key


def seed():
    """Seed a prior completed research run for demo purposes."""
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
        sys.exit(1)

    client = create_client(url, key)
    now = datetime.now(timezone.utc)
    run_id = str(uuid4())

    print(f"Seeding demo data...")
    print(f"  Run ID: {run_id}")
    print(f"  Brand: Jaguar Transit")
    print(f"  Market: Singapore")
    print(f"  Type: competitor_monitoring")

    # 1. Create the research run
    request_hash = compute_request_hash(
        "Jaguar Transit", "Singapore", "competitor_monitoring",
        [], [], 30, "identify recent competitor activity",
    )

    run_data = {
        "id": run_id,
        "brand": "Jaguar Transit",
        "market": "Singapore",
        "research_type": "competitor_monitoring",
        "objective": "Identify recent competitor activity",
        "status": "COMPLETED",
        "request_hash": request_hash,
        "lookback_days": 30,
        "started_at": (now - timedelta(hours=2)).isoformat(),
        "completed_at": (now - timedelta(hours=2, minutes=-5)).isoformat(),
        "sources_checked": 12,
        "unique_sources": 8,
        "relevant_sources": 6,
        "new_findings": 3,
        "changed_findings": 0,
        "unchanged_findings": 0,
        "tavily_calls": 6,
        "groq_calls": 1,
        "dropped_findings": 0,
        "confidence_score": 72,
        "cache_hit": False,
        "plan": {
            "complexity": "MEDIUM",
            "rationale": "[DEMO SEED] Synthetic historical run for change detection testing",
            "queries": [
                {"query": "Jaguar Transit competitors Singapore", "operation": "search"},
            ],
        },
        "metadata": {"demo_seed": True, "seed_timestamp": now.isoformat()},
    }

    try:
        client.table("research_runs").upsert(run_data).execute()
        print("  [OK] Research run created")
    except Exception as e:
        print(f"  [FAIL] Failed to create run: {e}")
        return

    # 2. Seed evidence
    evidence_rows = [
        {
            "research_run_id": run_id,
            "evidence_ref": "evidence_001",
            "source_type": "news",
            "source_name": "straitstimes.com",
            "source_quality": 3,
            "title": "[DEMO] TransitCover launches premium service in Singapore",
            "url": "https://straitstimes.com/demo/transitcover-launch",
            "normalized_url": "https://straitstimes.com/demo/transitcover-launch",
            "url_hash": "demo_url_hash_001",
            "content_hash": "demo_content_hash_001",
            "content": "[SYNTHETIC DEMO DATA] TransitCover announced the launch of a new premium transit insurance service targeting corporate clients in Singapore. The service offers comprehensive coverage for high-value shipments across Southeast Asia.",
            "published_at": (now - timedelta(days=5)).isoformat(),
            "retrieved_at": (now - timedelta(hours=2)).isoformat(),
            "market": "Singapore",
            "competitor": "TransitCover",
            "relevance": "RELEVANT",
            "relevance_score": 0.82,
            "change_status": "NEW",
            "metadata": {"demo_seed": True},
        },
        {
            "research_run_id": run_id,
            "evidence_ref": "evidence_002",
            "source_type": "news",
            "source_name": "channelnewsasia.com",
            "source_quality": 3,
            "title": "[DEMO] ShieldLogistics partners with DBS for embedded insurance",
            "url": "https://channelnewsasia.com/demo/shieldlogistics-dbs",
            "normalized_url": "https://channelnewsasia.com/demo/shieldlogistics-dbs",
            "url_hash": "demo_url_hash_002",
            "content_hash": "demo_content_hash_002",
            "content": "[SYNTHETIC DEMO DATA] ShieldLogistics has entered a strategic partnership with DBS Bank to offer embedded insurance solutions for logistics companies operating in the Singapore market.",
            "published_at": (now - timedelta(days=10)).isoformat(),
            "retrieved_at": (now - timedelta(hours=2)).isoformat(),
            "market": "Singapore",
            "competitor": "ShieldLogistics",
            "relevance": "RELEVANT",
            "relevance_score": 0.78,
            "change_status": "NEW",
            "metadata": {"demo_seed": True},
        },
        {
            "research_run_id": run_id,
            "evidence_ref": "evidence_003",
            "source_type": "industry",
            "source_name": "insuranceasiafinews.com",
            "source_quality": 4,
            "title": "[DEMO] InsurTech funding trends in Southeast Asia Q3 2026",
            "url": "https://insuranceasiafinews.com/demo/insurtech-q3",
            "normalized_url": "https://insuranceasiafinews.com/demo/insurtech-q3",
            "url_hash": "demo_url_hash_003",
            "content_hash": "demo_content_hash_003",
            "content": "[SYNTHETIC DEMO DATA] Southeast Asian InsurTech companies raised significant funding in Q3 2026, with Singapore-based startups leading the region. Transit and logistics insurance emerged as a high-growth segment.",
            "published_at": (now - timedelta(days=3)).isoformat(),
            "retrieved_at": (now - timedelta(hours=2)).isoformat(),
            "market": "Singapore",
            "relevance": "RELEVANT",
            "relevance_score": 0.65,
            "change_status": "NEW",
            "metadata": {"demo_seed": True},
        },
    ]

    try:
        client.table("research_evidence").upsert(evidence_rows).execute()
        print(f"  [OK] {len(evidence_rows)} evidence rows created")
    except Exception as e:
        print(f"  [FAIL] Failed to create evidence: {e}")
        return

    # 3. Seed findings
    finding_rows = [
        {
            "id": str(uuid4()),
            "research_run_id": run_id,
            "identity_key": "demo_ik_001",
            "finding_type": "service_launch",
            "title": "[DEMO] TransitCover launches premium corporate transit insurance",
            "summary": "[SYNTHETIC] TransitCover has launched a premium transit insurance service targeting corporate clients in Singapore, offering comprehensive coverage for high-value shipments across Southeast Asia.",
            "why_it_matters": "[SYNTHETIC] A direct competitor is expanding into the premium segment of Jaguar Transit's core market, potentially capturing high-value corporate clients.",
            "opportunity": "[SYNTHETIC] Jaguar Transit could differentiate by emphasizing its existing relationships and faster claims processing.",
            "entities": ["TransitCover"],
            "importance_score": 85,
            "relevance_score": 82,
            "confidence_score": 75,
            "ai_confidence": 70,
            "change_status": "NEW",
            "conflicts": [],
            "supporting_evidence_ids": ["evidence_001"],
            "metadata": {"demo_seed": True, "confidence_breakdown": {"source_quality": 0.667, "corroboration": 0.431, "independence": 1.0, "recency": 0.833, "ai_confidence": 0.7, "penalties": [], "raw_score": 0.65, "final_score": 75}},
        },
        {
            "id": str(uuid4()),
            "research_run_id": run_id,
            "identity_key": "demo_ik_002",
            "finding_type": "partnership",
            "title": "[DEMO] ShieldLogistics-DBS embedded insurance partnership",
            "summary": "[SYNTHETIC] ShieldLogistics has partnered with DBS Bank to offer embedded insurance for logistics companies in Singapore, potentially disrupting the traditional insurance distribution model.",
            "why_it_matters": "[SYNTHETIC] The embedded insurance model through banking partnerships could reduce Jaguar Transit's direct-to-client advantage.",
            "opportunity": "[SYNTHETIC] Jaguar Transit could explore similar banking partnerships or API-first distribution strategies.",
            "entities": ["ShieldLogistics", "DBS"],
            "importance_score": 78,
            "relevance_score": 78,
            "confidence_score": 70,
            "ai_confidence": 65,
            "change_status": "NEW",
            "conflicts": [],
            "supporting_evidence_ids": ["evidence_002"],
            "metadata": {"demo_seed": True},
        },
        {
            "id": str(uuid4()),
            "research_run_id": run_id,
            "identity_key": "demo_ik_003",
            "finding_type": "industry_trend",
            "title": "[DEMO] Transit InsurTech funding surge in Southeast Asia",
            "summary": "[SYNTHETIC] InsurTech funding in Southeast Asia grew significantly in Q3 2026, with transit and logistics insurance identified as a high-growth segment.",
            "why_it_matters": "[SYNTHETIC] Increased funding means more competitors are entering the transit insurance space, intensifying competition.",
            "opportunity": None,
            "entities": [],
            "importance_score": 55,
            "relevance_score": 65,
            "confidence_score": 60,
            "ai_confidence": 55,
            "change_status": "NEW",
            "conflicts": [],
            "supporting_evidence_ids": ["evidence_003"],
            "metadata": {"demo_seed": True},
        },
    ]

    try:
        client.table("research_findings").upsert(finding_rows).execute()
        print(f"  [OK] {len(finding_rows)} findings created")
    except Exception as e:
        print(f"  [FAIL] Failed to create findings: {e}")
        return

    # 4. Seed competitors
    competitor_rows = [
        {"name": "TransitCover", "brand": "Jaguar Transit", "market": "Singapore", "discovered": True, "confirmed": False, "domain": "transitcover.com"},
        {"name": "ShieldLogistics", "brand": "Jaguar Transit", "market": "Singapore", "discovered": True, "confirmed": False, "domain": "shieldlogistics.com"},
    ]

    try:
        for comp in competitor_rows:
            client.table("competitors").upsert(comp, on_conflict="name,brand,market").execute()
        print(f"  [OK] {len(competitor_rows)} competitors created")
    except Exception as e:
        print(f"  [FAIL] Failed to create competitors: {e}")

    print(f"\n[OK] Demo seed complete!")
    print(f"  Run a new research request to see change detection in action.")
    print(f"  The seeded evidence has url_hash values 'demo_url_hash_XXX'")
    print(f"  so new real research will show NEW evidence alongside this baseline.\n")


if __name__ == "__main__":
    seed()
