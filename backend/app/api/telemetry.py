"""Usage telemetry collection endpoint (premortem rule 5.12).

The frontend's `useTelemetry()` hook posts events here. They feed the
weekly feature-lifecycle report that flags rooms with <5 visits / 30 days.

POST /api/telemetry        — record one event (page_view / room_open / feature_use)
GET  /api/telemetry/usage  — summary report per room/feature for last N days
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text

from app.api.schemas import OkOut, TelemetryEventCreate
from app.auth import current_user
from app.db.session import get_db

router = APIRouter(tags=["telemetry"])


@router.post("/telemetry", response_model=OkOut)
def record_event(
    body: TelemetryEventCreate,
    request: Request,
    user: dict = Depends(current_user),
):
    actor_email = (user.get("preferred_username") or user.get("email") or "").lower() or None
    with get_db() as db:
        db.execute(text("""
            INSERT INTO usage_telemetry
                (workspace_id, actor_email, event_type, event_target,
                 duration_ms, extra, created_at)
            VALUES (:wid, :email, :etype, :etarget, :dur, CAST(:extra AS jsonb), NOW())
        """), {
            "wid": body.workspace_id,
            "email": actor_email,
            "etype": body.event_type,
            "etarget": body.event_target,
            "dur": body.duration_ms,
            "extra": __import__("json").dumps(body.extra) if body.extra else None,
        })
    return {"ok": True}


@router.get("/telemetry/usage")
def usage_report(
    days: int = Query(default=30, ge=1, le=365),
    workspace_id: Optional[str] = Query(default=None),
):
    """Per-room usage report — used by feature_lifecycle worker and /settings."""
    with get_db() as db:
        scope_clause = ":wid::uuid IS NULL OR workspace_id = :wid"
        rows = db.execute(text(f"""
            SELECT event_target,
                   COUNT(*)::int AS visits,
                   COUNT(DISTINCT actor_email)::int AS unique_users,
                   MAX(created_at) AS last_visit
            FROM usage_telemetry
            WHERE created_at > NOW() - (:days || ' days')::interval
              AND event_type IN ('room_open','page_view')
              AND ({scope_clause})
            GROUP BY event_target
            ORDER BY visits DESC
        """), {"wid": workspace_id, "days": days}).mappings().all()

    return {
        "days": days,
        "workspace_id": workspace_id,
        "rooms": [
            {
                "target": r["event_target"],
                "visits": r["visits"],
                "unique_users": r["unique_users"],
                "last_visit": r["last_visit"].isoformat() if r["last_visit"] else None,
                "verdict": (
                    "healthy" if r["visits"] >= 20
                    else "marginal" if r["visits"] >= 5
                    else "dying"
                ),
            }
            for r in rows
        ],
    }
