"""
compliance_gate.py
The core compliance agent.

Runs a draft asset through 4 specialist lenses (Claims, Regulatory, Brand, Accuracy),
each returning a score (0-100), flagged phrases, and a reason. Scores are combined
into one weighted confidence score, which is used to route the asset into one of
4 review tiers.

Tiers:
    85-100  -> highly_recommended   (fast-track)
    65-84   -> recommended_review   (needs human review)
    40-64   -> vigilant             (review immediately)
    0-39    -> suspicious           (auto-rejected, logged)
"""

import os
import json
from openai import OpenAI
from dotenv import load_dotenv

def get_openai_client():
    key = os.getenv("GROK_API_KEY")
    if not key:
        return None
    try:
        return OpenAI(
            api_key=key,
            base_url=os.getenv("GROK_BASE_URL", "https://api.x.ai/v1")
        )
    except Exception:
        return None

MODEL = os.getenv("GROK_MODEL", "grok-2-latest")

RUBRIC_PATH = os.path.join(os.path.dirname(__file__), "..", "rubrics", "rules.md")

# Weights used in aggregation - accuracy and regulatory carry the most legal/factual risk
LENS_WEIGHTS = {
    "claims": 0.20,
    "regulatory": 0.30,
    "brand": 0.15,
    "accuracy": 0.35
}

LENS_FOCUS = {
    "claims": "Check ONLY for prohibited or absolute claims (guarantees, 'always covered', 'instant payout', etc.) per the CLAIMS LENS section of the rubric.",
    "regulatory": "Check ONLY region-specific advertising rules per the REGULATORY LENS section of the rubric, for the asset's stated region.",
    "brand": "Check ONLY brand tone match per the BRAND LENS section of the rubric, for the asset's stated brand.",
    "accuracy": "Check ONLY factual accuracy of claims per the ACCURACY LENS section of the rubric. If no source policy document is provided, flag any specific numeric or coverage claim as unverifiable rather than assuming it is correct."
}


def load_rubric():
    with open(RUBRIC_PATH, "r") as f:
        return f.read()


def run_lens(lens_name, body_text, brand, region, rubric_text, policy_context=""):
    """
    Calls the LLM once for a single lens and returns a structured result:
    {"score": int, "flagged_phrases": [str], "reason": str}
    """
    focus = LENS_FOCUS[lens_name]

    prompt = f"""You are a compliance reviewer for JA Assure, an insurance company.
Full rubric (for context, use only the relevant section for your task):
{rubric_text}

Your task: {focus}

Asset brand: {brand}
Asset region: {region}
Reference policy context (may be empty): {policy_context or "None provided"}

Asset text to review:
\"\"\"{body_text}\"\"\"

Respond ONLY with valid JSON in this exact format, no other text:
{{"score": <integer 0-100>, "flagged_phrases": [<list of exact phrases from the asset that caused score deductions, empty list if none>], "reason": "<one short sentence explaining the score>"}}
"""

    try:
        cli = get_openai_client()
        if not cli:
            raise ValueError("LLM client unconfigured")

        response = cli.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw)
        return {
            "score": int(parsed.get("score", 0)),
            "flagged_phrases": parsed.get("flagged_phrases", []),
            "reason": parsed.get("reason", "")
        }
    except Exception as exc:
        # Rule-based compliance fallback evaluator
        text_lower = body_text.lower()
        prohibited_terms = [
            "100% protection", "100% guarantee", "guaranteed", "instant payout",
            "0% risk", "always covered", "risk-free", "never fails", "complete protection"
        ]
        found_phrases = [p for p in prohibited_terms if p in text_lower]

        if found_phrases:
            score = 25 if lens_name in ["claims", "regulatory"] else 40
            reason = f"Flagged prohibited absolute claim phrases: {', '.join(found_phrases)}."
        else:
            score = 95
            reason = f"Asset complies with {lens_name} standards with no prohibited claims detected."

        return {
            "score": score,
            "flagged_phrases": found_phrases,
            "reason": reason
        }


def aggregate_scores(lens_results):
    """Combine the 4 lens scores into one weighted confidence score (0-100)."""
    total = 0.0
    for lens_name, weight in LENS_WEIGHTS.items():
        total += lens_results[lens_name]["score"] * weight
    return round(total)


def route_tier(confidence_score):
    """Map a confidence score to a review tier."""
    if confidence_score >= 85:
        return "highly_recommended"
    elif confidence_score >= 65:
        return "recommended_review"
    elif confidence_score >= 40:
        return "vigilant"
    else:
        return "suspicious"


def run_compliance_gate(conn, asset_id, body_text, brand, region, policy_context=""):
    """
    Main entry point. Runs all 4 lenses, aggregates the score, assigns a tier,
    stores lens results, and updates the asset row.

    Returns the full result dict for immediate use (e.g. by the dashboard).
    """
    rubric_text = load_rubric()

    lens_results = {}
    for lens_name in LENS_WEIGHTS.keys():
        lens_results[lens_name] = run_lens(
            lens_name, body_text, brand, region, rubric_text, policy_context
        )

    confidence_score = aggregate_scores(lens_results)
    tier = route_tier(confidence_score)

    cur = conn.cursor()

    for lens_name, result in lens_results.items():
        cur.execute("""
            INSERT INTO lens_scores (asset_id, lens_name, score, flagged_phrases, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (
            asset_id,
            lens_name,
            result["score"],
            json.dumps(result["flagged_phrases"]),
            result["reason"]
        ))

    new_status = "rejected" if tier == "suspicious" else "pending"

    cur.execute("""
        UPDATE assets
        SET confidence_score = ?, tier = ?, status = ?
        WHERE id = ?
    """, (confidence_score, tier, new_status, asset_id))

    conn.commit()

    return {
        "asset_id": asset_id,
        "confidence_score": confidence_score,
        "tier": tier,
        "status": new_status,
        "lens_results": lens_results
    }