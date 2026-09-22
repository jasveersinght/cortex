"""Hashtag enrichment - the only text Hands ever *adds* to an approved post.

The approved body is frozen. Hands may only append hashtags, and those are:
  1. chosen by Gemini (or a deterministic heuristic if no key / no network),
  2. steered by hashtags that historically scored well for this brand + platform,
  3. screened against the prohibited-claims list, in five languages,
  4. trimmed to the platform's hashtag limit and character budget.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from .compliance_words import violations
from .config import Settings
from .learning import proven_hashtags
from .platform_rules import PlatformRule

BRAND_TAGS = {
    "jade": ["#JewellersBlock", "#JewelleryInsurance", "#JewelleryTrade"],
    "jaguar transit": ["#GoodsInTransit", "#CargoInsurance", "#SecureLogistics"],
    "doctorshield": ["#MedicalIndemnity", "#HealthcareProfessionals", "#ClinicPractice"],
}
GENERIC_TAGS = ["#InsurTech"]
REGION_TAGS = {
    "singapore": "#Singapore",
    "malaysia": "#Malaysia",
    "hong kong": "#HongKong",
    "indonesia": "#Indonesia",
    "thailand": "#Thailand",
}
_TAG_CLEAN = re.compile(r"[^\w]", re.UNICODE)


@dataclass
class Enrichment:
    hashtags: list[str] = field(default_factory=list)
    source: str = "none"              # gemini | heuristic | none
    dropped: list[str] = field(default_factory=list)  # removed by the claims screen


def sanitize_tag(raw: Any) -> str | None:
    text = _TAG_CLEAN.sub("", str(raw).strip().lstrip("#"))
    if not text or len(text) > 40 or text.isdigit():
        return None
    return "#" + text


def _clean_list(candidates: list[Any], limit: int) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        tag = sanitize_tag(raw)
        if not tag or tag.lower() in seen:
            continue
        seen.add(tag.lower())
        if violations(tag):
            dropped.append(tag)
            continue
        kept.append(tag)
        if len(kept) >= limit:
            break
    return kept, dropped


def heuristic_hashtags(brand: str | None, region: str | None, proven: list[str]) -> list[str]:
    tags = list(proven)
    tags += BRAND_TAGS.get((brand or "").strip().lower(), [])
    tags += GENERIC_TAGS
    tag = REGION_TAGS.get((region or "").strip().lower())
    if tag:
        tags.append(tag)
    return tags


def build_prompt(body: str, brand: str | None, platform: str, region: str | None, limit: int, proven: list[str]) -> str:
    preferred = ", ".join(proven) if proven else "(none yet)"
    return (
        "You choose hashtags for an already-approved social media post for JA Assure, a Singapore InsurTech "
        "(brands: Jade jewellers block, Jaguar Transit high-value goods transit, DoctorShield medical indemnity).\n"
        f"Brand: {brand or 'JA Assure'}\nPlatform: {platform}\nMarket: {region or 'Singapore'}\n"
        f'Approved post text (do NOT rewrite it):\n"""\n{body}\n"""\n\n'
        f'Return JSON only: {{"hashtags": ["#Tag1", "#Tag2"]}} with at most {limit} hashtags.\n'
        "Rules:\n"
        "- Write hashtags in the same language as the post.\n"
        "- Mix 1-2 niche industry tags with 1-2 broader tags. CamelCase, no spaces, no punctuation.\n"
        "- Professional insurance-industry tone. NO claims or promises: never use words like guaranteed, best, cheapest, "
        "100%, risk-free, always covered.\n"
        "- Do not invent product names, prices, partners or statistics.\n"
        f"- Prefer these hashtags if relevant (they performed well before): {preferred}\n"
    )


def _gemini_hashtags(prompt: str, settings: Settings) -> list[Any] | None:
    if settings.enrichment_mode == "off" or not settings.gemini_api_key:
        return None
    try:  # imported lazily so the package works without the SDK installed
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0.4},
        )
        data = json.loads((resp.text or "").strip().removeprefix("```json").removesuffix("```").strip())
        tags = data.get("hashtags") if isinstance(data, dict) else data
        return tags if isinstance(tags, list) else None
    except Exception:  # noqa: BLE001 - enrichment must never block publishing
        return None


def enrich(conn: sqlite3.Connection, asset: sqlite3.Row, platform: str, rule: PlatformRule, settings: Settings) -> Enrichment:
    if settings.enrichment_mode == "off":
        return Enrichment()
    brand, region = asset["brand"], asset["region"]
    proven = proven_hashtags(conn, brand, platform, 6)
    prompt = build_prompt(asset["body_text"] or "", brand, platform, region, rule.max_hashtags, proven)

    source = "heuristic"
    candidates = _gemini_hashtags(prompt, settings)
    if candidates:
        source = "gemini"
        candidates = list(candidates) + proven  # proven tags as backfill
    else:
        candidates = heuristic_hashtags(brand, region, proven)

    kept, dropped = _clean_list(candidates, rule.max_hashtags)
    return Enrichment(hashtags=kept, source=source, dropped=dropped)
