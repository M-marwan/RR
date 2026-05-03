"""Pydantic response schemas for the RR Command Center API.

Design notes
------------
- Every model has `extra="allow"` so existing routes that return raw
  `dict(row)` keep working even if a column we haven't modelled yet is
  added to the schema. Tightening (`extra="forbid"`) happens later, after
  the briefing data layer lands.
- Field types are intentionally permissive (Optional + relaxed) — Postgres
  rows arrive with mixed types (UUIDs as strings, timestamps as datetimes,
  JSONB as dict). Pydantic v2 handles this with `from_attributes=True`.
- Routes opt in via `response_model=...` on the route decorator. Where a
  response shape is too complex (nested dossier, canvas board state),
  we return a typed `ResponseEnvelope` and document the inner shape
  separately.

Usage
-----
    from app.api.schemas import EntityOut, TaskOut, MeOut

    @router.get("/entities", response_model=list[EntityOut])
    def list_entities(...):
        ...
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── shared base ─────────────────────────────────────────────────────────────


class _RRBase(BaseModel):
    """Base model with permissive config matching our raw-dict return style."""

    model_config = ConfigDict(
        extra="allow",
        from_attributes=True,
        populate_by_name=True,
    )


class ErrorOut(_RRBase):
    """Standard error envelope — used by FastAPI's HTTPException output too."""

    detail: str


class OkOut(_RRBase):
    """Generic success acknowledgement."""

    ok: bool = True


# ─── workspaces (companies) ──────────────────────────────────────────────────


class WorkspaceOut(_RRBase):
    """One of the principal's companies."""

    id: str
    slug: str
    display_name: str
    industry: Optional[str] = None
    primary_color: Optional[str] = None
    m365_tenant_id: Optional[str] = None
    m365_consent_granted_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Convenience aggregates added by the list endpoint
    member_count: Optional[int] = None
    project_count: Optional[int] = None


class WorkspaceCreate(_RRBase):
    slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    display_name: str = Field(min_length=1, max_length=120)
    industry: Optional[str] = Field(default=None, max_length=64)
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class WorkspaceUpdate(_RRBase):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    industry: Optional[str] = Field(default=None, max_length=64)
    primary_color: Optional[str] = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    m365_tenant_id: Optional[str] = Field(default=None, max_length=64)


class WorkspaceMemberOut(_RRBase):
    id: str
    workspace_id: str
    entity_id: Optional[str] = None
    email: str
    role: str
    joined_at: Optional[datetime] = None
    # Joined fields when membership is fetched with entity info
    name: Optional[str] = None


class WorkspaceMemberCreate(_RRBase):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(pattern=r"^(principal|exec|operator|readonly)$")
    entity_id: Optional[str] = None


# ─── auth ────────────────────────────────────────────────────────────────────


class MeOut(_RRBase):
    """Authenticated principal echo (returned by /api/me)."""

    sub: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    roles: list[str] = Field(default_factory=list)
    dev_mode: bool = False
    # Workspaces this user belongs to, with their role per workspace.
    workspaces: list[WorkspaceOut] = Field(default_factory=list)


# ─── entities ────────────────────────────────────────────────────────────────


class EntityOut(_RRBase):
    """A node in the entity graph: person, company, country, sector, etc."""

    id: str
    type: Optional[str] = None
    canonical_name: Optional[str] = None
    aliases: Optional[list[str]] = None
    country_code: Optional[str] = None
    profile: Optional[dict[str, Any]] = None
    last_updated: Optional[datetime] = None


class EntityDossierOut(_RRBase):
    """Composite dossier returned by GET /api/entities/{id}/dossier."""

    entity: EntityOut
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    contacts: list[dict[str, Any]] = Field(default_factory=list)
    recent_emails: list[dict[str, Any]] = Field(default_factory=list)


# ─── projects ────────────────────────────────────────────────────────────────


class ProjectOut(_RRBase):
    """A deal, venture, or internal initiative."""

    id: str
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    deal_stage: Optional[str] = None
    deal_value_usd: Optional[int] = None
    counterparty_id: Optional[str] = None
    open_task_count: Optional[int] = None
    last_activity_at: Optional[datetime] = None


# ─── tasks ───────────────────────────────────────────────────────────────────


class TaskOut(_RRBase):
    """A work item, possibly delegated."""

    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    project_id: Optional[str] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    due_at: Optional[datetime] = None
    assigned_to_entity_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    source_type: Optional[str] = None
    tags: Optional[list[str]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─── email ───────────────────────────────────────────────────────────────────


class EmailMessageOut(_RRBase):
    id: str
    subject: Optional[str] = None
    snippet: Optional[str] = None
    from_address: Optional[str] = None
    sent_at: Optional[datetime] = None
    direction: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[int] = None
    action_required: Optional[bool] = None


class EmailThreadOut(_RRBase):
    id: str
    subject: Optional[str] = None
    summary: Optional[str] = None
    open_loop: Optional[bool] = None
    open_loop_since: Optional[datetime] = None
    project_id: Optional[str] = None
    canvas_column: Optional[str] = None
    last_message_at: Optional[datetime] = None
    message_count: Optional[int] = None


# ─── briefing (morning room) ─────────────────────────────────────────────────


class ThreeMove(_RRBase):
    rank: int
    move: str
    rationale: Optional[str] = None


class CapitalPosition(_RRBase):
    deployable_usd: Optional[str] = None  # currently a range like "5000-50000"
    committed: Optional[int] = 0
    pipeline: Optional[str] = None


class OpenLoop(_RRBase):
    person: Optional[str] = None
    days: Optional[int] = None
    thread_id: Optional[str] = None


class RaymondDispatch(_RRBase):
    dispatch: Optional[str] = None
    moves: list[ThreeMove] = Field(default_factory=list)


class BriefingPayload(_RRBase):
    date: Optional[str] = None
    raymond: Optional[RaymondDispatch] = None
    open_loops: list[OpenLoop] = Field(default_factory=list)
    watchlist: list[str] = Field(default_factory=list)
    capital_position: Optional[CapitalPosition] = None
    withheld: Optional[str] = None


class BriefingOut(_RRBase):
    """Wrapper returned by /api/briefing/today and /api/briefing/{date}."""

    source: Optional[str] = None  # "cache" | "stale" | "seed"
    stale_warning: Optional[str] = None
    briefing: Optional[BriefingPayload] = None
    generated_at: Optional[datetime] = None


# ─── feed (intelligence wire) ────────────────────────────────────────────────


class FeedItemOut(_RRBase):
    id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    relevance: Optional[float] = None
    occurred_at: Optional[datetime] = None
    tags: Optional[list[str]] = None


class FeedSynthesisOut(_RRBase):
    job_type: Optional[str] = None
    output_json: Optional[dict[str, Any]] = None
    created_at: Optional[datetime] = None


# ─── search (global) ─────────────────────────────────────────────────────────


class SearchResultsOut(_RRBase):
    entities: list[EntityOut] = Field(default_factory=list)
    threads: list[EmailThreadOut] = Field(default_factory=list)
    projects: list[ProjectOut] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


# ─── system / health ─────────────────────────────────────────────────────────


class HealthOut(_RRBase):
    status: str
    db: str
    redis: str
    auth_enabled: Optional[bool] = None
