"""
main.py
Entry point that runs the pipeline end to end:

  1. Ensure database tables exist.
  2. Content Agent generates a draft asset.
  3. Compliance Gate scores it across 4 lenses and assigns a tier.
  4. Result is printed and left in the database as 'pending' for human review
     (except 'suspicious' tier assets, which are auto-rejected).
  5. Run dashboard/review.py separately to perform human review.

Usage:
    python main.py
"""

from db import get_connection, init_db
from agents.content_agent import generate_draft, save_draft
from agents.compliance_gate import run_compliance_gate


def run_pipeline(brand, platform, content_type, topic, region="SG", policy_context=""):
    init_db()
    conn = get_connection()

    print(f"Generating draft for {brand} / {platform} / {content_type}...")
    body_text = generate_draft(conn, brand, platform, content_type, topic, region)
    asset_id = save_draft(conn, brand, platform, content_type, body_text, region)
    print(f"Draft saved as asset ID {asset_id}.\n")
    print(body_text)
    print()

    print("Running compliance gate...")
    result = run_compliance_gate(conn, asset_id, body_text, brand, region, policy_context)

    print(f"\nConfidence score: {result['confidence_score']}")
    print(f"Tier: {result['tier']}")
    print(f"Status: {result['status']}")
    print("\nLens breakdown:")
    for lens_name, lens_result in result["lens_results"].items():
        print(f"  {lens_name:<12} score={lens_result['score']:<4} reason={lens_result['reason']}")

    conn.close()
    return result


if __name__ == "__main__":
    # Example call - replace brand/platform/topic with real inputs as needed.
    run_pipeline(
        brand="DoctorShield",
        platform="LinkedIn",
        content_type="caption",
        topic="why medical indemnity insurance matters for new clinicians",
        region="SG"
    )