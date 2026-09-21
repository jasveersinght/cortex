"""
CORTEX Backend Gateway
JA Assure AI Intelligence Ecosystem

Unified FastAPI server that:
1. Wraps the Compliance Agent (project1-brain-1) with HTTP endpoints
2. Proxies Research Agent requests to Ja_assure_vertex (or runs inline if same process)
3. Serves activity/history endpoints for the frontend dashboard
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── Path setup so we can import from project1-brain-1 ────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "project1-brain-1"))
sys.path.insert(0, BRAIN_DIR)

from dotenv import load_dotenv

# Load CORTEX env first, then fall back to project1-brain-1 env
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(BRAIN_DIR, ".env"), override=False)

# Research Agent base URL (can be overridden via env)
RESEARCH_API_URL = os.getenv("RESEARCH_API_URL", "http://localhost:8000")

# Content Agent base URL (can be overridden via env)
CONTENT_API_URL = os.getenv("CONTENT_API_URL", "http://localhost:8002")

# ── Database (Compliance / SQLite) ────────────────────────────────────────────

DB_PATH = os.getenv("DB_PATH", os.path.join(BRAIN_DIR, "ja_assure.db"))


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_tables():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            platform TEXT NOT NULL,
            content_type TEXT NOT NULL,
            body_text TEXT NOT NULL,
            region TEXT DEFAULT 'SG',
            status TEXT DEFAULT 'pending',
            tier TEXT,
            confidence_score INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lens_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            lens_name TEXT NOT NULL,
            score INTEGER NOT NULL,
            flagged_phrases TEXT,
            reason TEXT,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons_learned (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER,
            tag TEXT NOT NULL,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)
    conn.commit()
    conn.close()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_tables()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="CORTEX — JA Assure Intelligence Gateway",
    description="Unified gateway for Research and Compliance agents.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ───────────────────────────────────────────────────────────

class ComplianceRequest(BaseModel):
    body_text: str
    brand: str = "JA Assure"
    region: str = "SG"
    content_type: str = "social_post"
    platform: str = "LinkedIn"
    policy_context: str = ""


class ReviewDecision(BaseModel):
    decision: str  # "approved" | "rejected" | "needs_revision"
    tag: Optional[str] = None
    note: Optional[str] = None


# ── Compliance Endpoints ──────────────────────────────────────────────────────

@app.post("/compliance/check")
async def compliance_check(req: ComplianceRequest):
    """Run the compliance gate on submitted content."""
    try:
        from agents.compliance_gate import run_compliance_gate

        conn = get_db()

        # Save the draft first
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO assets (brand, platform, content_type, body_text, region, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (req.brand, req.platform, req.content_type, req.body_text, req.region))
        conn.commit()
        asset_id = cur.lastrowid

        result = run_compliance_gate(
            conn, asset_id, req.body_text, req.brand, req.region, req.policy_context
        )

        # Fetch full lens data
        cur.execute("""
            SELECT lens_name, score, flagged_phrases, reason
            FROM lens_scores WHERE asset_id = ?
        """, (asset_id,))
        lens_rows = cur.fetchall()

        lens_results = {}
        for row in lens_rows:
            phrases = []
            try:
                phrases = json.loads(row["flagged_phrases"] or "[]")
            except Exception:
                pass
            lens_results[row["lens_name"]] = {
                "score": row["score"],
                "flagged_phrases": phrases,
                "reason": row["reason"],
            }

        conn.close()

        tier_labels = {
            "highly_recommended": "Highly Recommended",
            "recommended_review": "Recommended — Review Needed",
            "vigilant": "Vigilant — Review Immediately",
            "suspicious": "Suspicious — Auto-Rejected",
        }

        tier_colors = {
            "highly_recommended": "green",
            "recommended_review": "amber",
            "vigilant": "orange",
            "suspicious": "red",
        }

        return {
            "asset_id": asset_id,
            "confidence_score": result["confidence_score"],
            "tier": result["tier"],
            "tier_label": tier_labels.get(result["tier"], result["tier"]),
            "tier_color": tier_colors.get(result["tier"], "gray"),
            "status": result["status"],
            "lens_results": lens_results,
            "checked_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compliance check failed: {str(e)}")


@app.get("/compliance/history")
async def compliance_history(limit: int = 20):
    """Return recent compliance checks from SQLite."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.id, a.brand, a.platform, a.content_type, a.region,
                   a.status, a.tier, a.confidence_score, a.created_at,
                   substr(a.body_text, 1, 200) as preview
            FROM assets a
            ORDER BY a.created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()

        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/compliance/asset/{asset_id}")
async def get_asset(asset_id: int):
    """Get full asset with lens scores."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        asset = cur.fetchone()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        cur.execute("""
            SELECT lens_name, score, flagged_phrases, reason
            FROM lens_scores WHERE asset_id = ?
        """, (asset_id,))
        lenses = cur.fetchall()

        lens_results = {}
        for row in lenses:
            phrases = []
            try:
                phrases = json.loads(row["flagged_phrases"] or "[]")
            except Exception:
                pass
            lens_results[row["lens_name"]] = {
                "score": row["score"],
                "flagged_phrases": phrases,
                "reason": row["reason"],
            }

        conn.close()
        result = dict(asset)
        result["lens_results"] = lens_results
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compliance/review/{asset_id}")
async def review_asset(asset_id: int, body: ReviewDecision):
    """Human review decision for an asset."""
    try:
        from agents.feedback_agent import record_decision

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM assets WHERE id = ?", (asset_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Asset not found")

        # Map frontend decisions to feedback_agent decisions
        decision_map = {
            "approved": "approved",
            "rejected": "rejected",
            "needs_revision": "edited",
        }
        mapped = decision_map.get(body.decision, body.decision)

        record_decision(conn, asset_id, mapped, tag=body.tag, note=body.note)
        conn.close()

        return {"success": True, "asset_id": asset_id, "decision": body.decision}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Activity Feed ─────────────────────────────────────────────────────────────

@app.get("/activity")
async def get_activity(limit: int = 30):
    """Unified activity feed from compliance (SQLite) and optionally research."""
    activities = []

    # Compliance activities from SQLite
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, brand, platform, content_type, status, tier,
                   confidence_score, created_at
            FROM assets
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()

        tier_emoji = {
            "highly_recommended": "✅",
            "recommended_review": "🔍",
            "vigilant": "⚠️",
            "suspicious": "🚫",
        }

        for row in rows:
            r = dict(row)
            emoji = tier_emoji.get(r.get("tier", ""), "📋")
            activities.append({
                "agent": "Compliance Agent",
                "agent_type": "compliance",
                "action": f"{emoji} Checked {r['content_type']} for {r['brand']} — {r.get('tier', 'pending')}",
                "detail": f"Confidence: {r.get('confidence_score', 'N/A')} | Status: {r.get('status', 'pending')}",
                "timestamp": r.get("created_at"),
                "status": r.get("status"),
                "asset_id": r.get("id"),
            })
    except Exception:
        pass

    # Try to also pull research activity via HTTP
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{RESEARCH_API_URL}/discover/status")
            if resp.status_code == 200:
                statuses = resp.json()
                for s in statuses[:10]:
                    activities.append({
                        "agent": "Research Agent",
                        "agent_type": "research",
                        "action": f"🔬 Research run: {s.get('research_type', '')} for {s.get('brand', '')}",
                        "detail": f"Market: {s.get('market', '')} | Status: {s.get('status', '')} | Findings: {s.get('findings_count', 0)}",
                        "timestamp": s.get("completed_at"),
                        "status": s.get("status"),
                    })
    except Exception:
        pass

    # Sort by timestamp desc
    activities.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return activities[:limit]


# ── Research Proxy ─────────────────────────────────────────────────────────────

@app.api_route("/research/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def research_proxy(path: str, request: Request):
    """Transparent proxy to the Research Agent at RESEARCH_API_URL."""
    url = f"{RESEARCH_API_URL}/discover/{path}"
    body = await request.body()
    params = dict(request.query_params)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                params=params,
                headers={"Content-Type": "application/json"},
            )
            return JSONResponse(
                content=resp.json() if resp.content else {},
                status_code=resp.status_code,
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Research Agent is not available. Please start the Research Agent server on port 8000.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Content Agent Proxy ──────────────────────────────────────────────────────

@app.api_route("/content/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def content_proxy(path: str, request: Request):
    """Transparent proxy to the Content Agent at CONTENT_API_URL."""
    url = f"{CONTENT_API_URL}/api/content/{path}"
    body = await request.body()
    params = dict(request.query_params)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method=request.method,
                url=url,
                content=body,
                params=params,
                headers={"Content-Type": "application/json"},
            )
            return JSONResponse(
                content=resp.json() if resp.content else {},
                status_code=resp.status_code,
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Content Agent is not available. Please start the Content Agent server on port 8002.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    research_ok = False
    content_ok = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{RESEARCH_API_URL}/health")
            research_ok = r.status_code == 200
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{CONTENT_API_URL}/health")
            content_ok = r.status_code == 200
    except Exception:
        pass

    compliance_ok = os.path.exists(DB_PATH)

    return {
        "cortex": "ok",
        "research_agent": "ok" if research_ok else "offline",
        "compliance_agent": "ok" if compliance_ok else "db_missing",
        "content_agent": "ok" if content_ok else "offline",
    }
