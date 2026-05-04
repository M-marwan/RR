"""Cost dashboard endpoints (premortem rule 5.4).

GET /api/costs/today          — today's spend vs cap (cross-portfolio or per-workspace)
GET /api/costs/history?days=30 — daily spend trend
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.schemas import CostTodayOut
from app.db.session import get_db

router = APIRouter(tags=["costs"])


@router.get("/costs/today", response_model=CostTodayOut)
def costs_today(workspace_id: Optional[str] = Query(default=None)):
    """Spend vs daily cap, today, for one workspace or all."""
    with get_db() as db:
        # Cap: per-workspace or sum across all workspaces
        if workspace_id:
            cap_row = db.execute(text("""
                SELECT COALESCE(daily_cost_cap_usd, 5.00)::float AS cap
                FROM workspaces WHERE id = :wid
            """), {"wid": workspace_id}).mappings().first()
            cap_usd = float(cap_row["cap"]) if cap_row else 5.00
        else:
            cap_row = db.execute(text("""
                SELECT COALESCE(SUM(daily_cost_cap_usd), 0)::float AS total_cap
                FROM workspaces WHERE archived_at IS NULL
            """)).mappings().first()
            cap_usd = float(cap_row["total_cap"]) if cap_row else 0.0

        # Spend today
        params = {"wid": workspace_id}
        scope_clause = ":wid::uuid IS NULL OR workspace_id = :wid"
        spent = db.execute(text(f"""
            SELECT
                COALESCE(SUM(total_usd), 0)::float AS spent,
                COALESCE(SUM(call_count), 0)::int  AS calls
            FROM daily_cost_summary
            WHERE cost_date = CURRENT_DATE AND ({scope_clause})
        """), params).mappings().first()

        # Per-model breakdown
        by_model_rows = db.execute(text(f"""
            SELECT model,
                   COALESCE(SUM(total_usd), 0)::float AS usd,
                   COALESCE(SUM(total_input_tokens), 0)::int AS input_tokens,
                   COALESCE(SUM(total_output_tokens), 0)::int AS output_tokens,
                   COALESCE(SUM(call_count), 0)::int AS call_count
            FROM daily_cost_summary
            WHERE cost_date = CURRENT_DATE AND ({scope_clause})
            GROUP BY model
            ORDER BY usd DESC
        """), params).mappings().all()

    spent_usd = float(spent["spent"])
    return {
        "workspace_id": workspace_id,
        "cap_usd": cap_usd,
        "spent_usd": spent_usd,
        "remaining_usd": max(0.0, cap_usd - spent_usd),
        "call_count": int(spent["calls"]),
        "by_model": [dict(r) for r in by_model_rows],
    }


@router.get("/costs/history")
def costs_history(
    workspace_id: Optional[str] = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
):
    """Daily spend trend for the last N days (default 30)."""
    with get_db() as db:
        scope_clause = ":wid::uuid IS NULL OR workspace_id = :wid"
        rows = db.execute(text(f"""
            SELECT cost_date,
                   SUM(total_usd)::float AS usd,
                   SUM(call_count)::int  AS calls
            FROM daily_cost_summary
            WHERE cost_date > CURRENT_DATE - (:days || ' days')::interval
              AND ({scope_clause})
            GROUP BY cost_date
            ORDER BY cost_date ASC
        """), {"wid": workspace_id, "days": days}).mappings().all()
    return {
        "workspace_id": workspace_id,
        "days": days,
        "series": [
            {"date": r["cost_date"].isoformat(), "usd": r["usd"], "calls": r["calls"]}
            for r in rows
        ],
    }
