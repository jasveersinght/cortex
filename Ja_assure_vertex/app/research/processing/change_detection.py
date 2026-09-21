"""Change detection against prior research runs.

Deterministic diff using url_hash and content_hash.
"""

from __future__ import annotations

import hashlib
import logging

from app.research.enums import ChangeStatus
from app.research.models import Evidence, Finding

logger = logging.getLogger("ja_assure")


def detect_evidence_changes(
    current_evidence: list[Evidence],
    prior_evidence: list[Evidence] | None,
) -> tuple[list[Evidence], dict]:
    """Detect changes in evidence compared to the prior run.

    Returns (updated_evidence, change_summary).
    change_summary: {"new": int, "changed": int, "unchanged": int, "removed": int}
    """
    summary = {"new": 0, "changed": 0, "unchanged": 0, "removed": 0}

    if not prior_evidence:
        # No prior run — everything is NEW
        for e in current_evidence:
            e.change_status = ChangeStatus.NEW
            summary["new"] += 1
        return current_evidence, summary

    # Build lookup maps from prior evidence
    prior_by_url_hash: dict[str, Evidence] = {}
    prior_url_hashes: set[str] = set()
    for pe in prior_evidence:
        prior_by_url_hash[pe.url_hash] = pe
        prior_url_hashes.add(pe.url_hash)

    current_url_hashes: set[str] = set()

    for e in current_evidence:
        current_url_hashes.add(e.url_hash)

        if e.url_hash not in prior_by_url_hash:
            e.change_status = ChangeStatus.NEW
            summary["new"] += 1
        elif e.content_hash != prior_by_url_hash[e.url_hash].content_hash:
            e.change_status = ChangeStatus.CHANGED
            summary["changed"] += 1
        else:
            e.change_status = ChangeStatus.UNCHANGED
            summary["unchanged"] += 1

    # Count removed (in prior but not in current)
    removed_hashes = prior_url_hashes - current_url_hashes
    summary["removed"] = len(removed_hashes)

    return current_evidence, summary


def compute_finding_identity_key(
    finding_type: str,
    title: str,
    primary_entity: str | None,
) -> str:
    """Compute a stable identity key for a finding across runs.

    identity_key = sha256(finding_type + normalized(title) + primary_entity)
    """
    normalized_title = title.strip().lower()
    entity = (primary_entity or "").strip().lower()
    raw = f"{finding_type}:{normalized_title}:{entity}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def derive_finding_change_status(
    supporting_evidence: list[Evidence],
) -> ChangeStatus:
    """Derive finding-level change status from its supporting evidence.

    - Any evidence is NEW → finding is NEW
    - Else any is CHANGED → finding is CHANGED
    - Else → UNCHANGED
    """
    statuses = {e.change_status for e in supporting_evidence}

    if ChangeStatus.NEW in statuses:
        return ChangeStatus.NEW
    elif ChangeStatus.CHANGED in statuses:
        return ChangeStatus.CHANGED
    else:
        return ChangeStatus.UNCHANGED


def all_evidence_unchanged(evidence: list[Evidence]) -> bool:
    """Check if all evidence is UNCHANGED (used to decide Groq skip)."""
    if not evidence:
        return False
    return all(e.change_status == ChangeStatus.UNCHANGED for e in evidence)
