"""
feedback_agent.py
Captures human review decisions (approve / edit / reject) and stores the reason
as a "lesson learned" so future content generation avoids repeating the same mistake.

Also provides analytics helpers to track whether the system is improving over time:
- rejection rate over time
- average confidence score over time
"""


def record_decision(conn, asset_id, decision, tag=None, note=None):
    """
    decision: "approved" | "edited" | "rejected"
    tag: short reason tag, e.g. "too salesy", "inaccurate claim", "off-brand tone", "wrong CTA"
    note: optional longer free-text explanation

    If decision is "edited" or "rejected", a tag is required to log a lesson.
    If decision is "approved", no lesson is logged.
    """
    cur = conn.cursor()

    if decision == "approved":
        cur.execute("UPDATE assets SET status = 'approved' WHERE id = ?", (asset_id,))
        conn.commit()
        return

    if decision in ("edited", "rejected"):
        if not tag:
            raise ValueError("A tag is required when logging an edit or rejection.")

        new_status = "rejected" if decision == "rejected" else "approved"
        cur.execute("UPDATE assets SET status = ? WHERE id = ?", (new_status, asset_id))

        cur.execute("""
            INSERT INTO lessons_learned (asset_id, tag, note)
            VALUES (?, ?, ?)
        """, (asset_id, tag, note or ""))

        conn.commit()
        return

    raise ValueError(f"Unknown decision type: {decision}")


def get_rejection_rate(conn, brand=None):
    """
    Returns rejection rate as a percentage: rejected assets / total reviewed assets.
    Reviewed = status in ('approved', 'rejected'), excludes still-pending assets.
    Optionally filter by brand.
    """
    cur = conn.cursor()

    if brand:
        cur.execute("""
            SELECT status FROM assets
            WHERE status IN ('approved', 'rejected') AND brand = ?
        """, (brand,))
    else:
        cur.execute("""
            SELECT status FROM assets
            WHERE status IN ('approved', 'rejected')
        """)

    rows = cur.fetchall()
    if not rows:
        return 0.0

    rejected = sum(1 for r in rows if r["status"] == "rejected")
    return round((rejected / len(rows)) * 100, 2)


def get_average_confidence_score(conn, brand=None):
    """Returns the average confidence_score across all scored assets, optionally by brand."""
    cur = conn.cursor()

    if brand:
        cur.execute("""
            SELECT confidence_score FROM assets
            WHERE confidence_score IS NOT NULL AND brand = ?
        """, (brand,))
    else:
        cur.execute("""
            SELECT confidence_score FROM assets
            WHERE confidence_score IS NOT NULL
        """)

    rows = cur.fetchall()
    if not rows:
        return 0.0

    scores = [r["confidence_score"] for r in rows]
    return round(sum(scores) / len(scores), 2)


def get_common_rejection_tags(conn, limit=5):
    """Returns the most frequent lesson tags, to show what the system struggles with most."""
    cur = conn.cursor()
    cur.execute("""
        SELECT tag, COUNT(*) as count
        FROM lessons_learned
        GROUP BY tag
        ORDER BY count DESC
        LIMIT ?
    """, (limit,))
    return [dict(row) for row in cur.fetchall()]