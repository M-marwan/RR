"""phase 1A.1 — workspaces, members, audit log, scoped FKs

Adds the multi-tenant data model. Each "workspace" is one of Marwan's companies.
The principal can belong to all of them; staff belong to one.

Design decisions
----------------
- workspace_id is NULLABLE on existing tables (projects, tasks, email_*).
  NULL = "unassigned" / global / pre-multi-tenant data. The settings UI lets
  the principal re-assign legacy rows in a follow-up.
- workspace_members links entity (person) → workspace + role. Role is one of
  principal / exec / operator / readonly.
- audit_log captures every mutation for UAE PDPL / DIFC compliance.
- We do NOT seed a default workspace here. The user creates their first
  workspace via the settings UI. Until then, all new rows have workspace_id
  set explicitly when created (or NULL for global views like the cross-
  portfolio briefing).

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── workspaces ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug            TEXT UNIQUE NOT NULL,
            display_name    TEXT NOT NULL,
            industry        TEXT,
            primary_color   TEXT,
            -- M365 tenant binding (set when admin grants OAuth consent in Phase 1B)
            m365_tenant_id  TEXT,
            m365_app_id     TEXT,
            m365_consent_granted_at TIMESTAMPTZ,
            -- Soft delete
            archived_at     TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspaces_slug ON workspaces(slug) "
        "WHERE archived_at IS NULL"
    )

    # ─── workspace_members ──────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS workspace_members (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            entity_id     UUID REFERENCES entities(id) ON DELETE SET NULL,
            email         TEXT NOT NULL,
            role          TEXT NOT NULL
                CHECK (role IN ('principal','exec','operator','readonly')),
            joined_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(workspace_id, email)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspace_members_email "
        "ON workspace_members(LOWER(email))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspace_members_workspace "
        "ON workspace_members(workspace_id)"
    )

    # ─── audit_log ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id              BIGSERIAL PRIMARY KEY,
            workspace_id    UUID REFERENCES workspaces(id) ON DELETE SET NULL,
            actor_email     TEXT,
            actor_entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
            action          TEXT NOT NULL,
            target_type     TEXT,
            target_id       TEXT,
            payload         JSONB,
            ip_address      INET,
            user_agent      TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_workspace_created "
        "ON audit_log(workspace_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_log_actor_created "
        "ON audit_log(actor_email, created_at DESC)"
    )

    # ─── scope existing tables to a workspace (nullable) ────────────────────
    # NULL is intentionally allowed — pre-existing rows from schema.sql
    # baseline will sit at NULL until reassigned.
    for table in (
        "projects",
        "tasks",
        "email_messages",
        "email_threads",
        "outbound_queue",
    ):
        op.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN IF NOT EXISTS workspace_id UUID "
            f"REFERENCES workspaces(id) ON DELETE SET NULL"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_workspace "
            f"ON {table}(workspace_id) WHERE workspace_id IS NOT NULL"
        )


def downgrade() -> None:
    # Drop the scoping columns first
    for table in (
        "projects",
        "tasks",
        "email_messages",
        "email_threads",
        "outbound_queue",
    ):
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_workspace")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS workspace_id")

    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS workspace_members")
    op.execute("DROP TABLE IF EXISTS workspaces")
