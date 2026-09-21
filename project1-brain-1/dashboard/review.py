"""
review.py
A simple command-line review dashboard for human approval.

Lists pending assets grouped by tier (highly_recommended first, suspicious last
since those are already auto-rejected but shown for transparency), and lets a
human approve, edit, or reject each one with a reason.
"""

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from db import get_connection
from agents.feedback_agent import record_decision, get_rejection_rate, get_average_confidence_score

TIER_ORDER = ["highly_recommended", "recommended_review", "vigilant", "suspicious"]

TIER_LABELS = {
    "highly_recommended": "HIGHLY RECOMMENDED",
    "recommended_review": "RECOMMENDED - REVIEW NEEDED",
    "vigilant": "VIGILANT - REVIEW IMMEDIATELY",
    "suspicious": "SUSPICIOUS - AUTO-REJECTED"
}

COMMON_TAGS = ["too salesy", "inaccurate claim", "off-brand tone", "wrong CTA", "regulatory risk"]


def fetch_pending_by_tier(conn, tier):
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM assets
        WHERE tier = ? AND status = 'pending'
        ORDER BY created_at ASC
    """, (tier,))
    return cur.fetchall()


def fetch_lens_results(conn, asset_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT lens_name, score, flagged_phrases, reason
        FROM lens_scores
        WHERE asset_id = ?
    """, (asset_id,))
    return cur.fetchall()


def print_asset(conn, asset):
    print("-" * 60)
    print(f"Asset ID: {asset['id']}  |  Brand: {asset['brand']}  |  Platform: {asset['platform']}")
    print(f"Region: {asset['region']}  |  Confidence Score: {asset['confidence_score']}")
    print("-" * 60)
    print(asset["body_text"])
    print("-" * 60)
    print("Lens breakdown:")
    for lens in fetch_lens_results(conn, asset["id"]):
        print(f"  {lens['lens_name']:<12} score={lens['score']:<4} reason={lens['reason']}")
    print("-" * 60)


def prompt_decision():
    print("Decision: [a] approve  [e] edit-and-approve  [r] reject")
    choice = input("> ").strip().lower()
    if choice == "a":
        return "approved"
    elif choice == "e":
        return "edited"
    elif choice == "r":
        return "rejected"
    else:
        print("Invalid input, skipping this asset.")
        return None


def prompt_tag():
    print("Select a reason tag:")
    for i, tag in enumerate(COMMON_TAGS, 1):
        print(f"  {i}. {tag}")
    print(f"  {len(COMMON_TAGS) + 1}. other (type your own)")
    choice = input("> ").strip()
    try:
        idx = int(choice)
        if 1 <= idx <= len(COMMON_TAGS):
            return COMMON_TAGS[idx - 1]
    except ValueError:
        pass
    return input("Enter custom tag: ").strip()


def run_dashboard():
    conn = get_connection()

    for tier in TIER_ORDER:
        assets = fetch_pending_by_tier(conn, tier)
        if not assets:
            continue

        print("\n" + "=" * 60)
        print(f"TIER: {TIER_LABELS[tier]}  ({len(assets)} asset(s))")
        print("=" * 60)

        for asset in assets:
            print_asset(conn, asset)
            decision = prompt_decision()
            if decision is None:
                continue

            if decision == "approved":
                record_decision(conn, asset["id"], "approved")
                print("Approved.\n")
            else:
                tag = prompt_tag()
                note = input("Optional note (press enter to skip): ").strip()
                record_decision(conn, asset["id"], decision, tag=tag, note=note)
                print(f"Recorded as {decision} with tag '{tag}'.\n")

    print("\n" + "=" * 60)
    print("REVIEW SESSION SUMMARY")
    print("=" * 60)
    print(f"Overall rejection rate: {get_rejection_rate(conn)}%")
    print(f"Average confidence score: {get_average_confidence_score(conn)}")
    conn.close()


if __name__ == "__main__":
    run_dashboard()