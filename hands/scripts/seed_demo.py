"""Create demo assets that exercise every gate.  Used by demo_end_to_end.py and handy for the live demo."""
from __future__ import annotations

import sqlite3

from ..approvals import record_approval
from ..bridge.brain_stub import ensure_brain_tables
from ..db import insert_dynamic
from ..media import set_media

VIDEO = "https://cdn.example.com/demo/reel.mp4"
IMAGE = "https://cdn.example.com/demo/vault.png"


def seed(conn: sqlite3.Connection) -> dict[str, int]:
    """Returns {label: asset_id}. The labels say what each asset is meant to demonstrate."""
    ensure_brain_tables(conn)
    ids: dict[str, int] = {}

    def add(label, *, brand, platform, region, body, status="approved", tier="highly_recommended", approve=True, media=None):
        aid = insert_dynamic(conn, "assets", {"brand": brand, "platform": platform, "content_type": "caption", "region": region,
                                              "body_text": body, "status": status, "tier": tier, "confidence_score": 88})
        if approve:
            record_approval(conn, aid, "Aisha Rahman (reviewer)")
        if media:
            set_media(conn, aid, media[0], media[1], ai_generated=True, source="content-agent")
        ids[label] = aid

    add("jade_linkedin", brand="Jade", platform="LinkedIn", region="Singapore",
        body="A jeweller's stock is only as safe as its weakest handover. Here is how leading Singapore jewellers map every step "
             "from vault to showroom, and where cover should follow the goods. Cover terms and exclusions apply.")
    add("jaguar_x_and_linkedin", brand="Jaguar Transit", platform="X, LinkedIn", region="Malaysia",
        body="High-value cargo changes hands many times before it arrives. Do you know where your cover starts and stops?")
    add("doctor_instagram_reel", brand="DoctorShield", platform="Instagram", region="Singapore",
        body="Three questions every clinic should ask about medical indemnity, in 30 seconds.", media=(VIDEO, "video"))
    add("jade_tiktok", brand="Jade", platform="TikTok", region="Thailand",
        body="A day in the life of a jewellers block policy.", media=(VIDEO, "video"))
    add("jaguar_instagram_image", brand="Jaguar Transit", platform="Instagram", region="Indonesia",
        body="Transit risk, explained with one picture.", media=(IMAGE, "image"))

    # ---- assets that the Hands must STOP ----
    add("no_receipt", brand="Jade", platform="LinkedIn", region="Singapore",
        body="Status says approved, but no human ever signed it off.", approve=False)
    add("tampered", brand="DoctorShield", platform="LinkedIn", region="Malaysia",
        body="Original, reviewed wording about clinic indemnity cover.")
    conn.execute("UPDATE assets SET body_text=? WHERE id=?", ("Edited AFTER approval: guaranteed payout, always covered!", ids["tampered"]))
    add("too_long_for_x", brand="Jaguar Transit", platform="X", region="Hong Kong", body="Long thought about transit cover. " * 12)
    add("instagram_no_media", brand="Jade", platform="Instagram", region="Singapore", body="An Instagram post that forgot its picture.")
    add("suspicious", brand="DoctorShield", platform="LinkedIn", region="Singapore",
        body="Auto-rejected by compliance but someone flipped the status.", tier="suspicious")
    add("still_pending", brand="Jade", platform="LinkedIn", region="Singapore",
        body="Waiting for a human. The Hands must not touch this.", status="pending", tier="recommended_review", approve=False)
    return ids
