"""
content_agent.py
Generates a draft marketing asset for a given brand/platform/topic.
Injects past "lessons learned" (rejection reasons) as few-shot guidance
so it avoids repeating known mistakes.

Uses the Grok API (x.ai) via the OpenAI-compatible client.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("GROK_API_KEY"),
    base_url=os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")
)
MODEL = os.getenv("GROK_MODEL", "grok-2-latest")

BRAND_VOICE = {
    "Jade": "premium, trust-forward, understated luxury tone. No slang.",
    "Jaguar Transit": "confident, operational, logistics-savvy tone for B2B operators.",
    "DoctorShield": "professional, reassuring, precise tone for doctors. Never casual."
}


def get_recent_lessons(conn, brand, limit=5):
    """Pull recent rejection/edit reasons for this brand to feed as few-shot guidance."""
    cur = conn.cursor()
    cur.execute("""
        SELECT ll.tag, ll.note
        FROM lessons_learned ll
        JOIN assets a ON ll.asset_id = a.id
        WHERE a.brand = ?
        ORDER BY ll.created_at DESC
        LIMIT ?
    """, (brand, limit))
    rows = cur.fetchall()
    if not rows:
        return "No past feedback yet."
    return "\n".join([f"- Avoid: {r['tag']} ({r['note']})" for r in rows])


def generate_draft(conn, brand, platform, content_type, topic, region="SG"):
    """Generate a draft asset using Grok, returns the raw text."""
    voice = BRAND_VOICE.get(brand, "professional and clear")
    lessons = get_recent_lessons(conn, brand)

    prompt = f"""You are writing a {content_type} for {brand}, an insurance brand, to be posted on {platform}.
Brand voice: {voice}
Topic: {topic}
Target region: {region}

Past feedback to avoid repeating:
{lessons}

Rules:
- Do NOT guarantee payouts or claim approvals.
- Do NOT say "always covered" or imply zero exclusions.
- Keep claims accurate and non-absolute.
- Match the brand voice exactly.

Write only the post content, no explanation."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


def save_draft(conn, brand, platform, content_type, body_text, region="SG"):
    """Insert the generated draft into the assets table as 'pending'."""
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO assets (brand, platform, content_type, body_text, region, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
    """, (brand, platform, content_type, body_text, region))
    conn.commit()
    return cur.lastrowid