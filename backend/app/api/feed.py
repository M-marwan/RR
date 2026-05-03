from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from app.db.session import get_db
from typing import Optional
import json
import asyncio

router = APIRouter(tags=["feed"])


@router.get("/feed")
def get_feed(
    since: Optional[str] = None,
    sector: Optional[str] = None,
    min_relevance: float = 0.5,
    limit: int = Query(50, le=200),
):
    params: dict = {"limit": limit, "min_relevance": min_relevance}
    filters = ["e.relevance_score >= :min_relevance"]

    if since:
        filters.append("e.occurred_at >= :since")
        params["since"] = since
    if sector:
        filters.append("e.entity_ids && (SELECT ARRAY_AGG(id) FROM entities WHERE profile->>'sector' ILIKE :sector)")
        params["sector"] = f"%{sector}%"

    where = "WHERE " + " AND ".join(filters)
    sql = f"""
        SELECT e.*,
               s.name AS source_name,
               s.credibility_score AS source_credibility,
               s.bias_label AS source_bias
        FROM events e
        LEFT JOIN LATERAL (
            SELECT s2.name, s2.credibility_score, s2.bias_label
            FROM sources s2
            WHERE s2.id = ANY(e.source_ids)
            ORDER BY s2.credibility_score DESC
            LIMIT 1
        ) s ON TRUE
        {where}
        ORDER BY e.relevance_score DESC, e.occurred_at DESC
        LIMIT :limit
    """
    with get_db() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/feed/stream")
async def stream_feed():
    """SSE endpoint for real-time intelligence feed updates."""
    async def event_generator():
        last_id = None
        while True:
            with get_db() as db:
                query = "SELECT * FROM events WHERE relevance_score >= 0.5"
                if last_id:
                    query += " AND id > :last_id"
                query += " ORDER BY created_at DESC LIMIT 10"
                params = {"last_id": last_id} if last_id else {}
                rows = db.execute(text(query), params).mappings().all()

            for row in rows:
                last_id = str(row["id"])
                data = json.dumps(dict(row), default=str)
                yield f"data: {data}\n\n"

            await asyncio.sleep(30)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/intelligence/synthesis")
def get_synthesis(job_type: str = "hidden_truth", limit: int = 20):
    with get_db() as db:
        rows = db.execute(text("""
            SELECT * FROM synthesis_cache
            WHERE job_type = :job_type
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"job_type": job_type, "limit": limit}).mappings().all()
    return [dict(r) for r in rows]
