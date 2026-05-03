"""phase 0 — add missing indexes for hot query paths

Indexes added (all CONCURRENTLY-friendly, IF NOT EXISTS so reruns are safe):
- email_threads(open_loop_since)         — hourly open-loop sweep filter
- projects(deal_stage)                   — concierge dealflow filter
- tasks(assigned_to_entity_id, status)   — war-room kanban + per-person task list

Discovered by the 2026-05-03 audit (memory key: rr-audit-2026-05-03).
None of these tables are large yet so we use plain CREATE INDEX, not CONCURRENTLY.
Switch to CONCURRENTLY in a follow-up migration once row counts grow past ~100k.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-03
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_threads_open_loop_since "
        "ON email_threads(open_loop_since) WHERE open_loop = true"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_deal_stage "
        "ON projects(deal_stage) WHERE deal_stage IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_status "
        "ON tasks(assigned_to_entity_id, status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_tasks_assigned_status")
    op.execute("DROP INDEX IF EXISTS idx_projects_deal_stage")
    op.execute("DROP INDEX IF EXISTS idx_email_threads_open_loop_since")
