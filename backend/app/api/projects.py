from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text
from pydantic import BaseModel
from app.db.session import get_db
from typing import Optional
import uuid

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    code: str
    name: str
    type: str
    status: str = "active"
    priority: int = 3
    description: Optional[str] = None
    deal_stage: Optional[str] = None
    deal_value_usd: Optional[float] = None
    target_close_at: Optional[str] = None
    reddington_ref: Optional[str] = None


@router.get("/projects")
def list_projects(
    type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = []
    params: dict = {"limit": limit, "offset": offset}
    if type:
        filters.append("type = :type")
        params["type"] = type
    if status:
        filters.append("status = :status")
        params["status"] = status

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT p.*,
               (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'done') AS open_task_count_live
        FROM projects p {where}
        ORDER BY p.last_activity_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    with get_db() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/projects/canvas")
def get_canvas(show_noise: bool = False):
    """Returns projects as kanban columns + the inbox column.

    Inbox by default: action_required + categorized 'project'/'deal' threads
    that haven't been moved to a project yet, plus any open loops.
    Noise/admin/newsletter are hidden unless show_noise=true.
    """
    with get_db() as db:
        projects = db.execute(text("""
            SELECT id, code, name, type, status, priority, canvas_order, deal_stage
            FROM projects WHERE status NOT IN ('dead', 'closed')
            ORDER BY canvas_order, created_at
        """)).mappings().all()

        threads = db.execute(text("""
            SELECT t.*,
                   e.canonical_name AS assigned_to_name,
                   p.code AS project_code,
                   p.name AS project_name,
                   (SELECT COUNT(*) FROM outbound_queue o
                    WHERE o.thread_id = t.thread_id AND o.status IN ('draft','approved','sending')
                   ) AS pending_outbound
            FROM email_threads t
            LEFT JOIN entities e ON e.id = t.assigned_to_entity_id
            LEFT JOIN projects p ON p.id = t.canvas_project_id
            ORDER BY
                CASE t.category WHEN 'action_required' THEN 0 ELSE 1 END,
                t.open_loop DESC,
                t.last_message_at DESC NULLS LAST
        """)).mappings().all()

    thread_map: dict = {}
    inbox_threads: list = []

    for t in threads:
        d = dict(t)
        if t["canvas_project_id"]:
            thread_map.setdefault(str(t["canvas_project_id"]), []).append(d)
            continue

        # Inbox filtering
        if t["hidden_from_inbox"]:
            continue
        if not show_noise and t["category"] in ("noise", "admin", "newsletter"):
            continue
        inbox_threads.append(d)

    return {
        "inbox": {
            "id": "inbox",
            "label": "Inbox",
            "threads": inbox_threads,
        },
        "columns": [
            {
                "project": dict(p),
                "threads": thread_map.get(str(p["id"]), []),
            }
            for p in projects
        ],
    }


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    with get_db() as db:
        row = db.execute(
            text("SELECT * FROM projects WHERE id = :id OR code = :id"),
            {"id": project_id},
        ).mappings().first()
    if not row:
        raise HTTPException(404, "Project not found")
    return dict(row)


@router.post("/projects")
def create_project(body: ProjectCreate):
    with get_db() as db:
        row = db.execute(text("""
            INSERT INTO projects (id, code, name, type, status, priority, description,
                deal_stage, deal_value_usd, reddington_ref)
            VALUES (:id, :code, :name, :type, :status, :priority, :description,
                :deal_stage, :deal_value_usd, :reddington_ref)
            RETURNING *
        """), {
            "id": str(uuid.uuid4()),
            **body.model_dump(),
        }).mappings().first()
    return dict(row)


@router.patch("/projects/{project_id}/canvas")
def move_thread_to_project(project_id: str, thread_id: str):
    """Drag-and-drop: assign a thread to a canvas column."""
    pid = None if project_id == "inbox" else project_id
    with get_db() as db:
        db.execute(text("""
            UPDATE email_threads SET canvas_project_id = :project_id
            WHERE thread_id = :thread_id
        """), {"project_id": pid, "thread_id": thread_id})
    return {"ok": True}
