"""Per-claim feedback on the morning brief (premortem rule 5.13).

The frontend renders 👍/👎 buttons next to each claim (Three Move, watchlist
item, dispatch sentence). Click POSTs here. We aggregate weekly; if a workspace
has <70% positive over 14 days we auto-disable AI synthesis for that workspace
(set `enable_ai_synthesis=FALSE`) and fall back to deterministic-only.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text

from app.api.schemas import BriefingFeedbackCreate, BriefingFeedbackOut
from app.auth import current_user
from app.db.session import get_db

router = APIRouter(tags=["briefing"])


@router.post("/briefing/feedback", response_model=BriefingFeedbackOut)
def submit_feedback(
    body: BriefingFeedbackCreate,
    request: Request,
    user: dict = Depends(current_user),
):
    actor_email = (user.get("preferred_username") or user.get("email") or "").lower() or None
    with get_db() as db:
        # Verify the briefing exists
        exists = db.execute(
            text("SELECT 1 FROM briefing_synthesis WHERE id = :id"),
            {"id": body.briefing_id},
        ).first()
        if not exists:
            raise HTTPException(404, f"briefing_id {body.briefing_id} not found")

        row = db.execute(text("""
            INSERT INTO briefing_feedback
                (briefing_id, claim_path, actor_email, verdict, note)
            VALUES (:bid, :path, :email, :v, :note)
            RETURNING *
        """), {
            "bid": body.briefing_id,
            "path": body.claim_path,
            "email": actor_email,
            "v": body.verdict,
            "note": body.note,
        }).mappings().first()
    return dict(row)


@router.get("/briefing/feedback/summary")
def feedback_summary(
    workspace_id: Optional[str] = Query(default=None),
    days: int = Query(default=14, ge=1, le=90),
):
    """Aggregate verdicts over the last N days for a workspace.

    Used by the auto-disable rule (rule 5.13). Frontend can also display this
    on /settings to show the principal how the briefing has been received.
    """
    with get_db() as db:
        rows = db.execute(text("""
            SELECT verdict, COUNT(*)::int AS n
            FROM briefing_feedback bf
            JOIN briefing_synthesis bs ON bs.id = bf.briefing_id
            WHERE bf.created_at > NOW() - (:days || ' days')::interval
              AND bs.workspace_id IS NOT DISTINCT FROM :wid
            GROUP BY verdict
        """), {"wid": workspace_id, "days": days}).mappings().all()

    counts = {r["verdict"]: r["n"] for r in rows}
    total = sum(counts.values())
    useful = counts.get("useful", 0)
    pct = (useful / total) if total > 0 else None
    return {
        "workspace_id": workspace_id,
        "days": days,
        "total": total,
        "useful": useful,
        "wrong": counts.get("wrong", 0),
        "noise": counts.get("noise", 0),
        "useful_pct": pct,
        "auto_disable_threshold": 0.70,
        "should_disable": pct is not None and total >= 10 and pct < 0.70,
    }
