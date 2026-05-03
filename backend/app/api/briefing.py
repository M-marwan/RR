from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db.session import get_db
from app.api.schemas import BriefingOut
from datetime import date, timedelta
import json

router = APIRouter(tags=["briefing"])


@router.get("/briefing/today", response_model=BriefingOut)
def get_today_briefing():
    today = date.today().isoformat()
    with get_db() as db:
        row = db.execute(text("""
            SELECT * FROM synthesis_cache
            WHERE job_type = 'morning_brief'
              AND DATE(created_at AT TIME ZONE 'Asia/Dubai') = :today
            ORDER BY created_at DESC LIMIT 1
        """), {"today": today}).mappings().first()

    if row:
        return {"source": "cache", "briefing": row["output_json"], "generated_at": row["created_at"]}

    # Fallback: serve the most recent briefing with a staleness warning
    with get_db() as db:
        row = db.execute(text("""
            SELECT * FROM synthesis_cache
            WHERE job_type = 'morning_brief'
            ORDER BY created_at DESC LIMIT 1
        """)).mappings().first()

    if row:
        return {
            "source": "stale",
            "stale_warning": f"No briefing for today yet — showing last available",
            "briefing": row["output_json"],
            "generated_at": row["created_at"],
        }

    # No briefings at all yet — return the seeded inaugural briefing
    return {
        "source": "seed",
        "briefing": _seed_briefing(),
        "generated_at": None,
    }


@router.get("/briefing/{date_str}", response_model=BriefingOut)
def get_briefing_by_date(date_str: str):
    with get_db() as db:
        row = db.execute(text("""
            SELECT * FROM synthesis_cache
            WHERE job_type = 'morning_brief'
              AND DATE(created_at AT TIME ZONE 'Asia/Dubai') = :date
            ORDER BY created_at DESC LIMIT 1
        """), {"date": date_str}).mappings().first()
    if not row:
        raise HTTPException(404, f"No briefing found for {date_str}")
    return {"briefing": row["output_json"], "generated_at": row["created_at"]}


def _seed_briefing() -> dict:
    """Returns the inaugural 2026-04-30 briefing in the structured format."""
    return {
        "date": "2026-04-30",
        "raymond": {
            "dispatch": "Three structural moves this morning. UAE leaves OPEC tomorrow — the dirham remains pegged but the arithmetic shifts. MENA VC cooled hard in Q1 (down 37% YoY) but two rounds contradict the panic. PIF's 2026–2030 strategy dropped — six ecosystems, each an addressed surface for downstream operators.",
            "moves": [
                {"rank": 1, "move": "Pause energy-adjacent deals 48 hours. Open the tech/SaaS window instead.", "rationale": "Post-OPEC-exit compliance landscape hasn't been priced yet. Wait for the regulatory signal before committing."},
                {"rank": 2, "move": "Call Steve (O&G technical) — 'What changes for non-ADNOC operators after tomorrow?'", "rationale": "He'll tell you what he can't tell you officially, which is the actual answer."},
                {"rank": 3, "move": "Review the PIF six-ecosystem breakdown against your current deal pipeline.", "rationale": "The downstream operator space opens in Advanced Manufacturing and Industrial Logistics."},
            ],
        },
        "open_loops": [],
        "watchlist": [
            "UAE OPEC exit announcement — market reaction",
            "Non-ADNOC operator response to new compliance environment",
            "PIF Q1 deal flow under new strategic split",
            "Comfi $65M pre-Series A — who backed it",
            "Kenya Pipeline NSE IPO progress",
            "GCC HNW diversification signals post-Brent $118",
        ],
        "capital_position": {"deployable_usd": "5000-50000", "committed": 0, "pipeline": "OPP-001 to OPP-004"},
        "withheld": "Antigua program analysis held — window is 6-month, not this week. Returns next briefing.",
    }
