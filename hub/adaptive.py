"""Call a function we have never seen, by reading its signature.

The Brain's compliance_agent.py / feedback_agent.py are not modified and their exact
parameters are not known in advance. This maps our canonical values onto whatever
parameter names the function declares, and reports clearly if something cannot be filled.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

ALIASES: dict[str, list[str]] = {
    "asset_id": ["asset_id", "id", "assetid"],
    "brand": ["brand", "brand_name"],
    "platform": ["platform", "channel"],
    "content_type": ["content_type", "type", "asset_type", "format"],
    "region": ["region", "market", "country"],
    "body_text": ["body_text", "text", "content", "body", "copy", "asset_text", "caption", "generated_text"],
    "asset": ["asset", "asset_row", "record"],
    "decision": ["decision", "status", "action", "outcome", "verdict"],
    "tag": ["tag", "reason_tag", "reason", "tags"],
    "note": ["note", "notes", "comment", "details", "explanation"],
    "reviewer": ["reviewer", "reviewed_by", "user", "approved_by", "author"],
    "edited_text": ["edited_text", "new_text", "edited_body", "revised_text"],
    "conn": ["conn", "connection", "db", "database"],
}
_LOOKUP = {alias: canon for canon, names in ALIASES.items() for alias in names}


class AdaptiveCallError(Exception):
    pass


def has_param(func: Callable[..., Any], canonical: str) -> bool:
    return any(_LOOKUP.get(p.name.lower()) == canonical for p in inspect.signature(func).parameters.values())


def build_kwargs(func: Callable[..., Any], values: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    kwargs: dict[str, Any] = {}
    missing: list[str] = []
    for p in inspect.signature(func).parameters.values():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        canon = _LOOKUP.get(p.name.lower())
        value = values.get(canon) if canon else None
        if value is not None:
            kwargs[p.name] = value
        elif p.default is p.empty:
            missing.append(p.name)
    return kwargs, missing


def call_adaptive(func: Callable[..., Any], values: dict[str, Any]) -> Any:
    kwargs, missing = build_kwargs(func, values)
    if missing:
        raise AdaptiveCallError(
            f"cannot call {getattr(func, '__module__', '?')}.{getattr(func, '__name__', '?')}{inspect.signature(func)}: "
            f"no value available for {missing}. Tell the Hub how to fill them (see hub/adaptive.py ALIASES)."
        )
    result = func(**kwargs)
    if inspect.iscoroutine(result):
        import asyncio

        result = asyncio.run(result)
    return result
