from fastapi import APIRouter, Query
from sqlalchemy import text
from app.db.session import get_db

router = APIRouter(tags=["search"])


@router.get("/search")
def global_search(q: str = Query(..., min_length=2), limit: int = 20):
    """Cross-entity search across entities, threads, events, projects."""
    pattern = f"%{q}%"
    params = {"q": pattern, "limit": limit}

    with get_db() as db:
        entities = db.execute(text("""
            SELECT id, type, canonical_name, 'entity' AS result_type
            FROM entities
            WHERE canonical_name ILIKE :q OR aliases::text ILIKE :q
            LIMIT :limit
        """), params).mappings().all()

        threads = db.execute(text("""
            SELECT id::text, subject AS canonical_name, 'thread' AS result_type,
                   'email_thread' AS type
            FROM email_threads
            WHERE subject ILIKE :q
            LIMIT :limit
        """), params).mappings().all()

        projects = db.execute(text("""
            SELECT id::text, name AS canonical_name, 'project' AS result_type, type
            FROM projects
            WHERE name ILIKE :q OR code ILIKE :q OR description ILIKE :q
            LIMIT :limit
        """), params).mappings().all()

        events = db.execute(text("""
            SELECT id::text, headline AS canonical_name, 'event' AS result_type,
                   'event' AS type
            FROM events
            WHERE headline ILIKE :q OR summary ILIKE :q
            ORDER BY relevance_score DESC
            LIMIT :limit
        """), params).mappings().all()

    return {
        "entities": [dict(r) for r in entities],
        "threads": [dict(r) for r in threads],
        "projects": [dict(r) for r in projects],
        "events": [dict(r) for r in events],
        "total": len(entities) + len(threads) + len(projects) + len(events),
    }
