"""Workspace CRUD — one workspace per company.

The principal creates a workspace per company they run; team members get
auto-added when their M365 mailbox is connected (Phase 1B). For now the
principal can manually add members by email.

Routes
------
GET    /api/workspaces                     — list workspaces visible to me
POST   /api/workspaces                     — create
GET    /api/workspaces/{id}                — detail
PATCH  /api/workspaces/{id}                — update
DELETE /api/workspaces/{id}                — soft delete (archived_at = NOW)
GET    /api/workspaces/{id}/members        — list members
POST   /api/workspaces/{id}/members        — add member
DELETE /api/workspaces/{id}/members/{mid}  — remove member
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text

from app.api.schemas import (
    OkOut,
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.auth import current_user
from app.db.session import get_db

router = APIRouter(tags=["workspaces"])


def _audit(db, *, workspace_id: Optional[str], actor: dict, action: str,
           target_type: str, target_id: str, payload: Optional[dict] = None,
           request: Optional[Request] = None) -> None:
    """Insert an audit_log row. Best-effort — failures here must not break the request."""
    try:
        db.execute(text("""
            INSERT INTO audit_log
                (workspace_id, actor_email, action, target_type, target_id,
                 payload, ip_address, user_agent)
            VALUES (:workspace_id, :actor_email, :action, :target_type, :target_id,
                    :payload, :ip_address, :user_agent)
        """), {
            "workspace_id": workspace_id,
            "actor_email": (actor.get("preferred_username") or actor.get("email") or "").lower() or None,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "payload": payload,
            "ip_address": request.client.host if request and request.client else None,
            "user_agent": request.headers.get("user-agent") if request else None,
        })
    except Exception:
        # audit failures shouldn't break the user action; log silently.
        pass


def _workspaces_for_user(db, email: str) -> list[dict]:
    """Return workspaces the user is a member of. Principal sees all (non-archived)."""
    # Detect principal — either via membership role OR the dev-mode bypass.
    is_principal = db.execute(text("""
        SELECT 1 FROM workspace_members
        WHERE LOWER(email) = LOWER(:email) AND role = 'principal'
        LIMIT 1
    """), {"email": email}).first() is not None

    if is_principal:
        rows = db.execute(text("""
            SELECT w.*,
                   (SELECT COUNT(*) FROM workspace_members m WHERE m.workspace_id = w.id) AS member_count,
                   (SELECT COUNT(*) FROM projects p WHERE p.workspace_id = w.id) AS project_count
            FROM workspaces w
            WHERE w.archived_at IS NULL
            ORDER BY w.display_name ASC
        """)).mappings().all()
    else:
        rows = db.execute(text("""
            SELECT w.*,
                   (SELECT COUNT(*) FROM workspace_members m WHERE m.workspace_id = w.id) AS member_count,
                   (SELECT COUNT(*) FROM projects p WHERE p.workspace_id = w.id) AS project_count
            FROM workspaces w
            JOIN workspace_members m ON m.workspace_id = w.id
            WHERE w.archived_at IS NULL
              AND LOWER(m.email) = LOWER(:email)
            ORDER BY w.display_name ASC
        """), {"email": email}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(user: dict = Depends(current_user)):
    email = (user.get("preferred_username") or user.get("email") or "").lower()
    with get_db() as db:
        # Dev-mode principal: synthetic user gets ALL non-archived workspaces.
        if user.get("_dev_mode"):
            rows = db.execute(text("""
                SELECT w.*,
                       (SELECT COUNT(*) FROM workspace_members m WHERE m.workspace_id = w.id) AS member_count,
                       (SELECT COUNT(*) FROM projects p WHERE p.workspace_id = w.id) AS project_count
                FROM workspaces w
                WHERE w.archived_at IS NULL
                ORDER BY w.display_name ASC
            """)).mappings().all()
            return [dict(r) for r in rows]
        return _workspaces_for_user(db, email)


@router.post("/workspaces", response_model=WorkspaceOut)
def create_workspace(
    body: WorkspaceCreate,
    request: Request,
    user: dict = Depends(current_user),
):
    new_id = str(uuid.uuid4())
    actor_email = (user.get("preferred_username") or user.get("email") or "").lower()

    with get_db() as db:
        existing = db.execute(
            text("SELECT id FROM workspaces WHERE slug = :slug"),
            {"slug": body.slug},
        ).first()
        if existing:
            raise HTTPException(409, f"slug '{body.slug}' is already taken")

        row = db.execute(text("""
            INSERT INTO workspaces (id, slug, display_name, industry, primary_color)
            VALUES (:id, :slug, :display_name, :industry, :primary_color)
            RETURNING *,
                      0::bigint AS member_count,
                      0::bigint AS project_count
        """), {
            "id": new_id,
            "slug": body.slug,
            "display_name": body.display_name,
            "industry": body.industry,
            "primary_color": body.primary_color,
        }).mappings().first()

        # First creator becomes principal of this workspace.
        if actor_email:
            db.execute(text("""
                INSERT INTO workspace_members (workspace_id, email, role)
                VALUES (:wid, :email, 'principal')
                ON CONFLICT (workspace_id, email) DO NOTHING
            """), {"wid": new_id, "email": actor_email})

        _audit(db, workspace_id=new_id, actor=user,
               action="workspace.create", target_type="workspace",
               target_id=new_id, payload={"slug": body.slug, "display_name": body.display_name},
               request=request)

    return dict(row)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, user: dict = Depends(current_user)):
    with get_db() as db:
        row = db.execute(text("""
            SELECT w.*,
                   (SELECT COUNT(*) FROM workspace_members m WHERE m.workspace_id = w.id) AS member_count,
                   (SELECT COUNT(*) FROM projects p WHERE p.workspace_id = w.id) AS project_count
            FROM workspaces w
            WHERE w.id = :id AND w.archived_at IS NULL
        """), {"id": workspace_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Workspace not found")
    return dict(row)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str,
    body: WorkspaceUpdate,
    request: Request,
    user: dict = Depends(current_user),
):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(400, "No fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    with get_db() as db:
        existing = db.execute(
            text("SELECT id FROM workspaces WHERE id = :id AND archived_at IS NULL"),
            {"id": workspace_id},
        ).first()
        if not existing:
            raise HTTPException(404, "Workspace not found")

        row = db.execute(text(f"""
            UPDATE workspaces
            SET {set_clause}, updated_at = NOW()
            WHERE id = :id
            RETURNING *,
                      (SELECT COUNT(*) FROM workspace_members m WHERE m.workspace_id = workspaces.id) AS member_count,
                      (SELECT COUNT(*) FROM projects p WHERE p.workspace_id = workspaces.id) AS project_count
        """), {**updates, "id": workspace_id}).mappings().first()

        _audit(db, workspace_id=workspace_id, actor=user,
               action="workspace.update", target_type="workspace",
               target_id=workspace_id, payload=updates, request=request)

    return dict(row)


@router.delete("/workspaces/{workspace_id}", response_model=OkOut)
def archive_workspace(
    workspace_id: str,
    request: Request,
    user: dict = Depends(current_user),
):
    """Soft-delete: sets archived_at, keeps data for audit."""
    with get_db() as db:
        existing = db.execute(
            text("SELECT id, slug FROM workspaces WHERE id = :id AND archived_at IS NULL"),
            {"id": workspace_id},
        ).mappings().first()
        if not existing:
            raise HTTPException(404, "Workspace not found")

        db.execute(
            text("UPDATE workspaces SET archived_at = NOW(), updated_at = NOW() WHERE id = :id"),
            {"id": workspace_id},
        )
        _audit(db, workspace_id=workspace_id, actor=user,
               action="workspace.archive", target_type="workspace",
               target_id=workspace_id, payload={"slug": existing["slug"]},
               request=request)
    return {"ok": True}


# ─── members ─────────────────────────────────────────────────────────────────


@router.get("/workspaces/{workspace_id}/members", response_model=list[WorkspaceMemberOut])
def list_members(workspace_id: str, user: dict = Depends(current_user)):
    with get_db() as db:
        rows = db.execute(text("""
            SELECT m.*, e.canonical_name AS name
            FROM workspace_members m
            LEFT JOIN entities e ON e.id = m.entity_id
            WHERE m.workspace_id = :wid
            ORDER BY
                CASE m.role
                    WHEN 'principal' THEN 1
                    WHEN 'exec' THEN 2
                    WHEN 'operator' THEN 3
                    WHEN 'readonly' THEN 4
                END,
                m.joined_at ASC
        """), {"wid": workspace_id}).mappings().all()
    return [dict(r) for r in rows]


@router.post("/workspaces/{workspace_id}/members", response_model=WorkspaceMemberOut)
def add_member(
    workspace_id: str,
    body: WorkspaceMemberCreate,
    request: Request,
    user: dict = Depends(current_user),
):
    with get_db() as db:
        existing_ws = db.execute(
            text("SELECT id FROM workspaces WHERE id = :id AND archived_at IS NULL"),
            {"id": workspace_id},
        ).first()
        if not existing_ws:
            raise HTTPException(404, "Workspace not found")

        try:
            row = db.execute(text("""
                INSERT INTO workspace_members (workspace_id, entity_id, email, role)
                VALUES (:wid, :entity_id, :email, :role)
                RETURNING *
            """), {
                "wid": workspace_id,
                "entity_id": body.entity_id,
                "email": body.email,
                "role": body.role,
            }).mappings().first()
        except Exception as e:
            # UNIQUE(workspace_id, email) violation
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise HTTPException(409, f"{body.email} is already a member of this workspace")
            raise

        _audit(db, workspace_id=workspace_id, actor=user,
               action="workspace.member.add", target_type="workspace_member",
               target_id=str(row["id"]),
               payload={"email": body.email, "role": body.role},
               request=request)

    return dict(row)


@router.delete("/workspaces/{workspace_id}/members/{member_id}", response_model=OkOut)
def remove_member(
    workspace_id: str,
    member_id: str,
    request: Request,
    user: dict = Depends(current_user),
):
    with get_db() as db:
        existing = db.execute(text("""
            SELECT id, email, role FROM workspace_members
            WHERE id = :mid AND workspace_id = :wid
        """), {"mid": member_id, "wid": workspace_id}).mappings().first()
        if not existing:
            raise HTTPException(404, "Member not found")

        db.execute(
            text("DELETE FROM workspace_members WHERE id = :mid"),
            {"mid": member_id},
        )
        _audit(db, workspace_id=workspace_id, actor=user,
               action="workspace.member.remove", target_type="workspace_member",
               target_id=member_id,
               payload={"email": existing["email"], "role": existing["role"]},
               request=request)
    return {"ok": True}
