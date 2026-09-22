"""Talks to project-1-brain by IMPORTING it. None of its files are edited."""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
from typing import Any, Callable

from hands import audit
from hands.approvals import record_approval
from hands.db import get_asset, insert_dynamic, table_exists

from .adaptive import AdaptiveCallError, call_adaptive, has_param
from .config import HubSettings


class AdapterError(Exception):
    pass


def load_callable(spec: str, brain_path: str) -> Callable[..., Any]:
    if not spec or ":" not in spec:
        raise AdapterError(f"function not configured; expected 'module:function', got '{spec}'. "
                           "Run `python -m hub.scripts.inspect_brain` to see what exists.")
    if brain_path:
        path = os.path.abspath(brain_path)
        if path not in sys.path:
            sys.path.insert(0, path)
    module_name, _, func_name = spec.partition(":")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise AdapterError(f"could not import '{module_name}' (BRAIN_PATH={brain_path!r}): {exc}") from exc
    func = getattr(module, func_name, None)
    if not callable(func):
        raise AdapterError(f"'{module_name}' has no function '{func_name}'")
    return func


def read_result(conn: sqlite3.Connection, asset_id: Any) -> dict[str, Any]:
    asset = get_asset(conn, asset_id)
    if asset is None:
        return {}
    lenses: dict[str, Any] = {}
    if table_exists(conn, "lens_scores"):
        for r in conn.execute("SELECT * FROM lens_scores WHERE CAST(asset_id AS TEXT)=?", (str(asset["id"]),)):
            d = dict(r)
            name = d.get("lens_name") or d.get("lens") or d.get("name")
            lenses[str(name)] = {"score": d.get("score"), "reason": d.get("reason")}
    return {"asset_id": str(asset["id"]), "status": asset["status"], "tier": asset["tier"],
            "confidence_score": asset["confidence_score"], "lens_scores": lenses}


class BrainAdapter:
    def __init__(self, settings: HubSettings):
        self.settings = settings

    # ---- compliance ------------------------------------------------------
    def run_compliance(self, conn: sqlite3.Connection, asset_id: Any) -> dict[str, Any]:
        func = load_callable(self.settings.brain_compliance_func, self.settings.brain_path)
        asset = get_asset(conn, asset_id)
        if asset is None:
            raise AdapterError(f"asset {asset_id} not found")
        values = {
            "asset_id": asset["id"], "brand": asset["brand"], "platform": asset["platform"],
            "content_type": asset["content_type"] or "caption", "region": asset["region"],
            "body_text": asset["body_text"], "asset": dict(asset), "conn": conn,
        }
        before = {str(r["id"]) for r in conn.execute("SELECT id FROM assets")}
        try:
            returned = call_adaptive(func, values)
        except AdaptiveCallError as exc:
            raise AdapterError(str(exc)) from exc

        final_id = str(asset["id"])
        if not has_param(func, "asset_id"):
            # The function takes raw content and creates its own asset row; adopt that row and drop our placeholder.
            fresh = [r["id"] for r in conn.execute("SELECT id FROM assets WHERE body_text=? AND brand=?", (asset["body_text"], asset["brand"]))
                     if str(r["id"]) not in before]
            if fresh:
                final_id = str(fresh[-1])
                conn.execute("DELETE FROM assets WHERE CAST(id AS TEXT)=? AND tier IS NULL", (str(asset["id"]),))
                conn.execute("UPDATE hub_links SET asset_id=? WHERE asset_id=?", (final_id, str(asset["id"])))
                audit.log(conn, "hub_adopted_brain_asset", asset_id=final_id, detail={"replaced": str(asset["id"])})
        result = read_result(conn, final_id)
        result["function"] = self.settings.brain_compliance_func
        result["returned_type"] = type(returned).__name__
        if result.get("tier") is None:
            result["warning"] = "the function ran but no tier was written to the asset; check its signature/behaviour"
        audit.log(conn, "hub_compliance_run", asset_id=final_id, detail={"tier": result.get("tier")})
        return result

    # ---- human decision ---------------------------------------------------
    def record_decision(self, conn: sqlite3.Connection, asset_id: Any, decision: str, reviewer: str,
                        tag: str | None = None, note: str | None = None, edited_text: str | None = None) -> dict[str, Any]:
        decision = decision.strip().lower()
        if decision not in {"approved", "rejected", "edited"}:
            raise AdapterError("decision must be approved, rejected or edited")
        if not reviewer or not reviewer.strip():
            raise AdapterError("reviewer is required: decisions must be attributable to a person")
        if decision in {"rejected", "edited"} and not tag:
            raise AdapterError("a reason tag is required for rejected/edited (e.g. 'too salesy')")
        if decision == "edited" and not edited_text:
            raise AdapterError("edited_text is required when decision is 'edited'")
        if get_asset(conn, asset_id) is None:
            raise AdapterError(f"asset {asset_id} not found")

        used = "fallback"
        if self.settings.brain_decision_func:
            func = load_callable(self.settings.brain_decision_func, self.settings.brain_path)
            try:
                call_adaptive(func, {"asset_id": asset_id, "decision": decision, "tag": tag, "note": note,
                                     "reviewer": reviewer, "edited_text": edited_text, "conn": conn})
            except AdaptiveCallError as exc:
                raise AdapterError(str(exc)) from exc
            used = self.settings.brain_decision_func
        else:  # documented schema only: status column + lessons_learned row
            new_status = "rejected" if decision == "rejected" else "approved"
            if decision == "edited":
                conn.execute("UPDATE assets SET body_text=?, status=? WHERE CAST(id AS TEXT)=?", (edited_text, new_status, str(asset_id)))
            else:
                conn.execute("UPDATE assets SET status=? WHERE CAST(id AS TEXT)=?", (new_status, str(asset_id)))
            if tag and table_exists(conn, "lessons_learned"):
                insert_dynamic(conn, "lessons_learned", {"asset_id": asset_id, "tag": tag, "note": note})

        receipt = None
        if decision in {"approved", "edited"}:  # the Hands' approval receipt (who, when, hash of the final text)
            receipt = record_approval(conn, asset_id, reviewer, note=note, source="hub")
        audit.log(conn, "hub_decision", actor=reviewer, asset_id=asset_id, detail={"decision": decision, "tag": tag, "via": used})
        return {"asset_id": str(asset_id), "decision": decision, "via": used, "approval_receipt": bool(receipt),
                "asset": read_result(conn, asset_id)}
