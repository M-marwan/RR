"""Morning brief route — reads from materialised briefing tables (Phase 1A.2).

Replaces the prior _seed_briefing() hardcoded JSON. Now serves real,
deterministically-aggregated data from `briefing_synthesis`, `open_loops`,
`capital_position`, and `watchlist`.

If today's brief hasn't been generated yet, the route generates it on-demand
(idempotent — multiple parallel calls will all upsert the same row).

Workspace filtering
-------------------
- No `workspace_id` query param → cross-portfolio aggregate (workspace_id IS NULL).
- `workspace_id=...` → that workspace's brief.

Source citations (rule 5.1) flow through unchanged from the underlying rows.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.api.schemas import BriefingOut
from app.db.session import get_db
from app.workers import briefing_generate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["briefing"])


def _serialise_briefing(db, briefing_row: dict, workspace_id: Optional[str]) -> dict:
    """Build the payload the frontend renders.

    Reads the latest open_loops + capital_position + watchlist for the same scope
    and joins them into one BriefingOut envelope.
    """
    # Three Moves come straight off briefing_synthesis (already JSONB, source-cited).
    three_moves = briefing_row["three_moves"] or []

    # Open loops
    loops = db.execute(text("""
        SELECT id, thread_id, person_name, days_waiting, status
        FROM open_loops
        WHERE workspace_id IS NOT DISTINCT FROM :wid AND status = 'open'
        ORDER BY days_waiting DESC
        LIMIT 10
    """), {"wid": workspace_id}).mappings().all()
    open_loops = [
        {
            "person": r["person_name"],
            "person_name": r["person_name"],
            "days": r["days_waiting"],
            "days_waiting": r["days_waiting"],
            "thread_id": str(r["thread_id"]) if r["thread_id"] else None,
        }
        for r in loops
    ]

    # Watchlist (today's items, source-cited)
    watch = db.execute(text("""
        SELECT rank, item, source_refs
        FROM watchlist
        WHERE workspace_id IS NOT DISTINCT FROM :wid
          AND brief_date = (NOW() AT TIME ZONE 'Asia/Dubai')::date
        ORDER BY rank ASC
    """), {"wid": workspace_id}).mappings().all()
    watchlist = [
        {"rank": r["rank"], "item": r["item"], "source_refs": r["source_refs"] or []}
        for r in watch
    ]

    # Capital position (most recent for this workspace)
    capital = None
    cap_row = db.execute(text("""
        SELECT deployable_usd_low, deployable_usd_high, committed_usd, pipeline_summary
        FROM capital_position
        WHERE workspace_id IS NOT DISTINCT FROM :wid
        ORDER BY recorded_for DESC LIMIT 1
    """), {"wid": workspace_id}).mappings().first()
    if cap_row:
        # Render the legacy "deployable_usd" string for backward-compat with the UI.
        low = cap_row["deployable_usd_low"]
        high = cap_row["deployable_usd_high"]
        if low is not None and high is not None:
            display_range = f"{low}-{high}"
        elif low is not None:
            display_range = f"{low}+"
        else:
            display_range = None
        capital = {
            "deployable_usd": display_range,
            "deployable_usd_low": low,
            "deployable_usd_high": high,
            "committed": cap_row["committed_usd"] or 0,
            "committed_usd": cap_row["committed_usd"] or 0,
            "pipeline": cap_row["pipeline_summary"],
            "pipeline_summary": cap_row["pipeline_summary"],
        }

    # Raymond block — only present when AI synthesis layer is enabled (rule 5.2).
    raymond = None
    if briefing_row.get("raymond_dispatch"):
        raymond = {
            "dispatch": briefing_row["raymond_dispatch"],
            "dispatch_source_refs": briefing_row.get("raymond_dispatch_source_refs") or [],
            "moves": three_moves,
        }
    else:
        # Deterministic mode: still expose three_moves under "raymond" so the
        # existing frontend renders them, but no narrative dispatch text.
        raymond = {
            "dispatch": None,
            "dispatch_source_refs": [],
            "moves": three_moves,
        }

    today = db.execute(text(
        "SELECT (NOW() AT TIME ZONE 'Asia/Dubai')::date AS d"
    )).mappings().first()["d"]

    return {
        "id": str(briefing_row["id"]),
        "source": "computed",
        "stale_warning": None,
        "generated_at": briefing_row["generated_at"],
        "workspace_id": str(workspace_id) if workspace_id else None,
        "briefing": {
            "date": today.isoformat(),
            "raymond": raymond,
            "open_loops": open_loops,
            "watchlist": watchlist,
            "capital_position": capital,
            "withheld": briefing_row.get("withheld"),
            "generation_mode": briefing_row["generation_mode"],
        },
    }


@router.get("/briefing/today", response_model=BriefingOut)
def get_today_briefing(workspace_id: Optional[str] = Query(default=None)):
    """Today's brief. workspace_id=null → cross-portfolio aggregate."""
    with get_db() as db:
        today = db.execute(text(
            "SELECT (NOW() AT TIME ZONE 'Asia/Dubai')::date AS d"
        )).mappings().first()["d"]

        row = db.execute(text("""
            SELECT * FROM briefing_synthesis
            WHERE workspace_id IS NOT DISTINCT FROM :wid
              AND brief_date = :d
        """), {"wid": workspace_id, "d": today}).mappings().first()

    # Generate on demand if today's brief doesn't exist yet
    if not row:
        try:
            briefing_generate.generate_briefing_for_workspace(workspace_id)
        except Exception:
            logger.exception("On-demand briefing generation failed for %s", workspace_id)
        with get_db() as db:
            row = db.execute(text("""
                SELECT * FROM briefing_synthesis
                WHERE workspace_id IS NOT DISTINCT FROM :wid
                  AND brief_date = :d
            """), {"wid": workspace_id, "d": today}).mappings().first()

    if not row:
        # Empty-state response — no data anywhere yet, no exception thrown
        return {
            "id": None,
            "source": "empty",
            "stale_warning": "No briefing yet — workspace has no signals to summarise.",
            "generated_at": None,
            "workspace_id": workspace_id,
            "briefing": None,
        }

    with get_db() as db:
        return _serialise_briefing(db, dict(row), workspace_id)


@router.get("/briefing/{date_str}", response_model=BriefingOut)
def get_briefing_by_date(date_str: str, workspace_id: Optional[str] = Query(default=None)):
    """Historical brief for a specific date (YYYY-MM-DD)."""
    with get_db() as db:
        row = db.execute(text("""
            SELECT * FROM briefing_synthesis
            WHERE workspace_id IS NOT DISTINCT FROM :wid AND brief_date = :d
        """), {"wid": workspace_id, "d": date_str}).mappings().first()
    if not row:
        raise HTTPException(404, f"No briefing found for {date_str}")
    with get_db() as db:
        return _serialise_briefing(db, dict(row), workspace_id)


@router.post("/briefing/regenerate")
def regenerate_today(workspace_id: Optional[str] = Query(default=None)):
    """Force-rebuild today's brief from current data (admin/debug)."""
    result = briefing_generate.generate_briefing_for_workspace(workspace_id)
    return result
