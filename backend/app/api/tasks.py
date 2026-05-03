from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text
from pydantic import BaseModel
from app.db.session import get_db
from app.api.schemas import TaskOut, OkOut
from typing import Optional
import uuid

router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    priority: int = 3
    due_at: Optional[str] = None
    assigned_to_entity_id: Optional[str] = None
    source_type: str = "manual"
    tags: list[str] = []


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    assigned_to: Optional[str] = None,
    overdue: bool = False,
    limit: int = Query(100, le=500),
):
    filters = []
    params: dict = {"limit": limit}

    if status:
        filters.append("t.status = :status")
        params["status"] = status
    else:
        filters.append("t.status != 'done'")

    if project_id:
        filters.append("t.project_id = :project_id")
        params["project_id"] = project_id

    if assigned_to:
        filters.append("t.assigned_to_entity_id = :assigned_to")
        params["assigned_to"] = assigned_to

    if overdue:
        filters.append("t.due_at < NOW() AND t.status != 'done'")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT t.*,
               p.code AS project_code,
               p.name AS project_name,
               e.canonical_name AS assigned_to_name
        FROM tasks t
        LEFT JOIN projects p ON p.id = t.project_id
        LEFT JOIN entities e ON e.id = t.assigned_to_entity_id
        {where}
        ORDER BY t.priority ASC, t.due_at ASC NULLS LAST, t.created_at DESC
        LIMIT :limit
    """
    with get_db() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


@router.post("/tasks", response_model=TaskOut)
def create_task(body: TaskCreate):
    task_id = str(uuid.uuid4())
    with get_db() as db:
        row = db.execute(text("""
            INSERT INTO tasks (id, title, description, project_id, priority,
                due_at, assigned_to_entity_id, source_type, tags)
            VALUES (:id, :title, :description, :project_id, :priority,
                :due_at, :assigned_to_entity_id, :source_type, :tags)
            RETURNING *
        """), {
            "id": task_id,
            **body.model_dump(),
            "tags": body.tags,
        }).mappings().first()
    return dict(row)


@router.patch("/tasks/{task_id}", response_model=OkOut)
def update_task(task_id: str, body: dict):
    allowed = {"status", "priority", "due_at", "assigned_to_entity_id", "notes", "title"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(400, "No valid fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    with get_db() as db:
        db.execute(
            text(f"UPDATE tasks SET {set_clause}, updated_at = NOW() WHERE id = :id"),
            {**updates, "id": task_id},
        )
    return {"ok": True}
