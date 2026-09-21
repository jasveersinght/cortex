"""Research Planner — pure deterministic Python.

No LLM. No network calls. Trivially unit-testable.
Turns a validated ResearchRequest into a ResearchPlan.
"""

from __future__ import annotations

import logging

from app.research.enums import Complexity, ResearchType, TavilyOperation
from app.research.models import (
    ExtractPolicyConfig,
    PlannedQuery,
    ResearchPlan,
)
from app.research.registry import get_research_config

logger = logging.getLogger("ja_assure")


# ── Complexity thresholds (tunable constants) ─────────────────────

COMPLEXITY_THRESHOLD_LOW = 0
COMPLEXITY_THRESHOLD_HIGH = 4

# Query budget caps per complexity
QUERY_BUDGET = {
    Complexity.LOW: 4,
    Complexity.MEDIUM: 8,
    Complexity.HIGH: 12,
}


def compute_complexity(
    research_type: ResearchType,
    competitors: list[str],
    topics: list[str],
    lookback_days: int,
    objective: str | None,
    max_sources: int,
) -> tuple[Complexity, int]:
    """Compute research complexity deterministically.

    Returns (complexity, score).
    """
    config = get_research_config(research_type)
    score = 0

    # Base from research type default
    if config.default_complexity == Complexity.HIGH:
        score += 2
    elif config.default_complexity == Complexity.MEDIUM:
        score += 1

    # Entity count
    if len(competitors) + len(topics) >= 4:
        score += 1

    # Long lookback
    if lookback_days > 60:
        score += 1

    # Detailed objective
    if objective and len(objective) > 120:
        score += 1

    # Small scope reduces
    if max_sources <= 10:
        score -= 1

    # Map score to complexity
    if score <= COMPLEXITY_THRESHOLD_LOW:
        complexity = Complexity.LOW
    elif score >= COMPLEXITY_THRESHOLD_HIGH:
        complexity = Complexity.HIGH
    else:
        complexity = Complexity.MEDIUM

    logger.info(f"Complexity score={score} -> {complexity.value}")
    return complexity, score


def generate_queries(
    research_type: ResearchType,
    brand: str,
    market: str,
    competitors: list[str],
    topics: list[str],
    complexity: Complexity,
    lookback_days: int,
) -> list[PlannedQuery]:
    """Generate planned queries from research type templates.

    Templates are instantiated for each entity (competitor/topic).
    Budget caps limit the total number of queries.
    """
    config = get_research_config(research_type)
    templates = config.query_templates
    budget = QUERY_BUDGET[complexity]

    # Determine entities to iterate over
    entities: list[tuple[str, str | None]] = []  # (entity_name, entity_type_key)

    if config.requires_competitors and competitors:
        for c in competitors:
            entities.append((c, c))
    elif config.requires_competitors and not competitors:
        # Discovery mode: use brand as the entity for discovery queries
        entities.append((brand, None))
        # Add discovery-specific queries
        discovery_queries = [
            PlannedQuery(
                query=f"{brand} competitors {market}",
                operation=TavilyOperation.SEARCH,
                purpose="competitor_discovery",
                target_entity=None,
                max_results=10,
                time_range_days=lookback_days,
            ),
            PlannedQuery(
                query=f"top companies {market} similar to {brand}",
                operation=TavilyOperation.SEARCH,
                purpose="competitor_discovery",
                target_entity=None,
                max_results=10,
                time_range_days=lookback_days,
            ),
        ]
        # These count toward budget
        remaining = budget - len(discovery_queries)
        if remaining <= 0:
            return discovery_queries[:budget]
        queries = list(discovery_queries)
        # Still instantiate templates with brand
        for template in templates[:remaining]:
            q = template.format(competitor=brand, brand=brand, market=market, industry=brand)
            queries.append(PlannedQuery(
                query=q,
                operation=_select_operation(complexity),
                purpose=template.split("{")[0].strip(),
                target_entity=brand,
                max_results=10,
                time_range_days=lookback_days,
            ))
        return queries[:budget]

    # For non-competitor types, use topics or brand
    if not entities:
        if topics:
            for t in topics:
                entities.append((t, t))
        else:
            entities.append((brand, None))

    queries: list[PlannedQuery] = []
    seen_queries: set[str] = set()

    for entity_name, target in entities:
        for template in templates:
            q = template.format(
                competitor=entity_name,
                brand=brand,
                market=market,
                industry=brand,
            )
            q = q.strip()

            # Skip empty/duplicate
            q_lower = q.lower()
            if not q or q_lower in seen_queries:
                logger.debug(f"Planner: skipping duplicate/empty query: '{q}'")
                continue
            seen_queries.add(q_lower)

            queries.append(PlannedQuery(
                query=q,
                operation=_select_operation(complexity),
                purpose=template.split("{")[0].strip() or "research",
                target_entity=target,
                max_results=10,
                time_range_days=lookback_days,
            ))

            if len(queries) >= budget:
                break
        if len(queries) >= budget:
            break

    return queries[:budget]


def _select_operation(complexity: Complexity) -> TavilyOperation:
    """Select the Tavily operation based on complexity."""
    if complexity == Complexity.HIGH:
        return TavilyOperation.SEARCH  # research op used separately
    return TavilyOperation.SEARCH


def plan(
    brand: str,
    market: str,
    research_type: ResearchType,
    competitors: list[str],
    topics: list[str],
    objective: str | None,
    lookback_days: int,
    max_sources: int,
) -> ResearchPlan:
    """Create a full research plan from a validated request.

    This is the main entry point for the planner.
    Raises ValueError if the plan produces zero queries.
    """
    config = get_research_config(research_type)

    # Use type default lookback if not specified
    effective_lookback = lookback_days or config.default_lookback_days

    complexity, score = compute_complexity(
        research_type, competitors, topics,
        effective_lookback, objective, max_sources,
    )

    queries = generate_queries(
        research_type, brand, market, competitors,
        topics, complexity, effective_lookback,
    )

    if not queries:
        raise ValueError(
            f"Research planner produced zero queries for "
            f"brand={brand}, market={market}, type={research_type.value}. "
            f"Cannot proceed."
        )

    # Extract policy
    extract_policy = ExtractPolicyConfig(
        enabled=complexity in (Complexity.MEDIUM, Complexity.HIGH),
        max_urls=5 if complexity == Complexity.HIGH else 3,
    )

    # Build rationale
    rationale_parts = [
        f"Research type: {config.name}",
        f"Complexity: {complexity.value} (score={score})",
        f"Queries planned: {len(queries)}",
        f"Lookback: {effective_lookback} days",
        f"Max sources: {max_sources}",
    ]
    if competitors:
        rationale_parts.append(f"Competitors: {', '.join(competitors)}")
    if topics:
        rationale_parts.append(f"Topics: {', '.join(topics)}")
    if objective:
        rationale_parts.append(f"Objective: {objective}")

    rationale = ". ".join(rationale_parts)

    plan = ResearchPlan(
        complexity=complexity,
        queries=queries,
        extract_policy=extract_policy,
        rationale=rationale,
        estimated_tavily_calls=len(queries) + (extract_policy.max_urls if extract_policy.enabled else 0),
    )

    logger.info(
        f"Research plan created: complexity={complexity.value}, "
        f"queries={len(queries)}, estimated_calls={plan.estimated_tavily_calls}"
    )

    return plan
