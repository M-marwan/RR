from fastapi import APIRouter, Query, HTTPException, Request, Depends
from sqlalchemy import text
from app.db.session import get_db
from app.api.schemas import EntityOut, EntityDossierOut
from app.auth import current_user
from app.auth_audit import audit_read
from typing import Optional

router = APIRouter(tags=["entities"])


@router.get("/entities", response_model=list[EntityOut])
def list_entities(
    type: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = []
    params: dict = {"limit": limit, "offset": offset}
    if type:
        filters.append("type = :type")
        params["type"] = type
    if q:
        filters.append("canonical_name ILIKE :q")
        params["q"] = f"%{q}%"

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT id, type, canonical_name, aliases, country_code, profile, last_updated
        FROM entities {where}
        ORDER BY last_updated DESC
        LIMIT :limit OFFSET :offset
    """
    with get_db() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/entities/{entity_id}", response_model=EntityOut)
def get_entity(entity_id: str):
    sql = "SELECT * FROM entities WHERE id = :id"
    with get_db() as db:
        row = db.execute(text(sql), {"id": entity_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Entity not found")
    return dict(row)


@router.get("/entities/{entity_id}/dossier", response_model=EntityDossierOut)
@audit_read(target_type="entity_dossier", target_id_arg="entity_id")
def get_dossier(
    entity_id: str,
    request: Request = None,  # noqa: B008 — FastAPI handles
    user: dict = Depends(current_user),
):
    with get_db() as db:
        entity = db.execute(
            text("SELECT * FROM entities WHERE id = :id"), {"id": entity_id}
        ).mappings().first()
        if not entity:
            raise HTTPException(404, "Entity not found")

        relationships = db.execute(text("""
            SELECT r.*, e.canonical_name AS related_name, e.type AS related_type
            FROM relationships r
            JOIN entities e ON (
                CASE WHEN r.subject_id = :id THEN r.object_id ELSE r.subject_id END = e.id
            )
            WHERE r.subject_id = :id OR r.object_id = :id
            LIMIT 50
        """), {"id": entity_id}).mappings().all()

        contacts = db.execute(text("""
            SELECT * FROM contacts WHERE entity_id = :id ORDER BY is_primary DESC
        """), {"id": entity_id}).mappings().all()

        recent_emails = db.execute(text("""
            SELECT id, subject, snippet, sent_at, direction, category, from_address
            FROM email_messages
            WHERE entity_ids @> ARRAY[:id]::uuid[]
            ORDER BY sent_at DESC
            LIMIT 10
        """), {"id": entity_id}).mappings().all()

    return {
        "entity": dict(entity),
        "relationships": [dict(r) for r in relationships],
        "contacts": [dict(c) for c in contacts],
        "recent_emails": [dict(e) for e in recent_emails],
    }
