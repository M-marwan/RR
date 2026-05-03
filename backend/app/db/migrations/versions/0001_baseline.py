"""baseline — schema created by app/db/schema.sql

This migration is intentionally a no-op. It exists so alembic can track every
schema change starting from the existing schema.sql baseline.

ONE-TIME SETUP (existing databases):
    cd backend
    alembic stamp 0001        # marks the existing DB at this revision

FRESH SETUP (new database):
    docker-compose up postgres   # mounts schema.sql via Docker entrypoint
    alembic stamp 0001           # mark as at baseline
    alembic upgrade head         # apply 0002+ deltas

After this, every schema change MUST be a new alembic revision. Do not edit
schema.sql for incremental changes — only update it if you want to keep it in
sync as a single-file reference for fresh installs.

Revision ID: 0001
Revises:
Create Date: 2026-05-03
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op. The baseline is everything in app/db/schema.sql, applied once via
    # the Docker postgres entrypoint mount.
    pass


def downgrade() -> None:
    # Downgrade past the baseline is unsupported — would mean dropping every
    # table. If you really want a clean slate, drop the database and restart
    # docker-compose.
    pass
