"""phase 1A.2 — briefing data layer + premortem invariants

Replaces the hardcoded `_seed_briefing()` JSON with real materialized
data, and bakes in the failure-mode preventives from the 2026-05-03
premortem (architecture doc Section 5).

Tables added
  briefing_synthesis     — daily brief per workspace (or NULL = cross-portfolio).
                           Three Moves stored as JSONB with REQUIRED source_refs.
  briefing_feedback      — per-claim 👍/👎 (rule 5.13)
  open_loops             — person + days_waiting (rule 5.1, source-cited)
  capital_position       — deployable / committed / pipeline per workspace+date
  watchlist              — daily watch items per workspace, source-cited
  read_audit_log         — sensitive-resource read events (rule 5.11)
  daily_cost_summary     — Claude spend per workspace+date+model (rule 5.4)
  usage_telemetry        — page views / room visits (rule 5.12)

Workspace columns added
  daily_cost_cap_usd               default $5 (rule 5.4)
  enable_ai_synthesis              default FALSE (rule 5.2)
  aup_signed_at, aup_signed_by_email
                                    AUP gate before M365 activation (rule 5.6)
  categorizer_test_passed_at
  categorizer_test_recall
  categorizer_test_precision        recall/precision floor (rule 5.5)

email_threads columns added
  monitoring_excluded BOOL          per-thread opt-out (rule 5.7)
  excluded_reason TEXT

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-04
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── workspace columns: cost cap, AUP, categorizer gates, AI flag ────
    op.execute("""
        ALTER TABLE workspaces
            ADD COLUMN IF NOT EXISTS daily_cost_cap_usd NUMERIC(8,2) NOT NULL DEFAULT 5.00,
            ADD COLUMN IF NOT EXISTS enable_ai_synthesis BOOL NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS aup_signed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS aup_signed_by_email TEXT,
            ADD COLUMN IF NOT EXISTS categorizer_test_passed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS categorizer_test_recall NUMERIC(4,3),
            ADD COLUMN IF NOT EXISTS categorizer_test_precision NUMERIC(4,3)
    """)

    # ─── email_threads: per-thread monitoring opt-out (rule 5.7) ─────────
    op.execute("""
        ALTER TABLE email_threads
            ADD COLUMN IF NOT EXISTS monitoring_excluded BOOL NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS excluded_reason TEXT
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_threads_excluded "
        "ON email_threads(monitoring_excluded) WHERE monitoring_excluded = true"
    )

    # ─── briefing_synthesis (rule 5.1 source_refs required) ───────────────
    # workspace_id NULLABLE — NULL means cross-portfolio aggregate.
    op.execute("""
        CREATE TABLE IF NOT EXISTS briefing_synthesis (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
            brief_date DATE NOT NULL,
            -- Deterministic aggregation (rule 5.2 — always populated)
            three_moves JSONB NOT NULL DEFAULT '[]'::jsonb,
            -- AI synthesis layer (rule 5.2 — populated only when enable_ai_synthesis)
            raymond_dispatch TEXT,
            raymond_dispatch_source_refs JSONB,
            withheld TEXT,
            generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            generation_mode TEXT NOT NULL
                CHECK (generation_mode IN ('deterministic','ai_synthesized')),
            UNIQUE(workspace_id, brief_date)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_briefing_synthesis_date "
        "ON briefing_synthesis(brief_date DESC)"
    )

    # If raymond_dispatch is set, source_refs must also be set (rule 5.1).
    op.execute("""
        ALTER TABLE briefing_synthesis
        ADD CONSTRAINT IF NOT EXISTS briefing_dispatch_requires_sources
        CHECK (
            raymond_dispatch IS NULL
            OR (raymond_dispatch_source_refs IS NOT NULL
                AND jsonb_array_length(raymond_dispatch_source_refs) > 0)
        )
    """)

    # ─── briefing_feedback (rule 5.13) ────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS briefing_feedback (
            id BIGSERIAL PRIMARY KEY,
            briefing_id UUID NOT NULL REFERENCES briefing_synthesis(id) ON DELETE CASCADE,
            claim_path TEXT NOT NULL,
            actor_email TEXT,
            verdict TEXT NOT NULL CHECK (verdict IN ('useful','wrong','noise')),
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_briefing_feedback_briefing "
        "ON briefing_feedback(briefing_id, created_at DESC)"
    )

    # ─── open_loops ───────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS open_loops (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
            thread_id UUID REFERENCES email_threads(id) ON DELETE SET NULL,
            person_entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
            person_name TEXT,
            days_waiting INT NOT NULL DEFAULT 0,
            last_outbound_at TIMESTAMPTZ,
            status TEXT NOT NULL DEFAULT 'open'
                CHECK (status IN ('open','closed','snoozed')),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_open_loops_workspace_status "
        "ON open_loops(workspace_id, status, days_waiting DESC) "
        "WHERE status = 'open'"
    )

    # ─── capital_position ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS capital_position (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
            recorded_for DATE NOT NULL,
            deployable_usd_low BIGINT,
            deployable_usd_high BIGINT,
            committed_usd BIGINT NOT NULL DEFAULT 0,
            pipeline_summary TEXT,
            source TEXT NOT NULL DEFAULT 'manual'
                CHECK (source IN ('manual','derived')),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(workspace_id, recorded_for)
        )
    """)

    # ─── watchlist (rule 5.1 — every item must cite a source) ────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
            brief_date DATE NOT NULL,
            rank INT NOT NULL DEFAULT 0,
            item TEXT NOT NULL,
            source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            CHECK (jsonb_array_length(source_refs) > 0)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_watchlist_workspace_date "
        "ON watchlist(workspace_id, brief_date DESC, rank)"
    )

    # ─── read_audit_log (rule 5.11) ───────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS read_audit_log (
            id BIGSERIAL PRIMARY KEY,
            workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
            actor_email TEXT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            ip_address INET,
            user_agent TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_read_audit_workspace_target "
        "ON read_audit_log(workspace_id, target_type, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_read_audit_actor "
        "ON read_audit_log(actor_email, created_at DESC)"
    )

    # ─── daily_cost_summary (rule 5.4) ────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS daily_cost_summary (
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            cost_date DATE NOT NULL,
            model TEXT NOT NULL,
            total_input_tokens BIGINT NOT NULL DEFAULT 0,
            total_output_tokens BIGINT NOT NULL DEFAULT 0,
            total_usd NUMERIC(10,4) NOT NULL DEFAULT 0,
            call_count INT NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (workspace_id, cost_date, model)
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_cost_summary_date "
        "ON daily_cost_summary(cost_date DESC)"
    )

    # ─── usage_telemetry (rule 5.12) ──────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS usage_telemetry (
            id BIGSERIAL PRIMARY KEY,
            workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
            actor_email TEXT,
            event_type TEXT NOT NULL
                CHECK (event_type IN ('page_view','room_open','feature_use','session_start')),
            event_target TEXT NOT NULL,
            duration_ms INT,
            extra JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_telemetry_target_date "
        "ON usage_telemetry(event_target, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_telemetry_workspace_date "
        "ON usage_telemetry(workspace_id, created_at DESC) "
        "WHERE workspace_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS usage_telemetry")
    op.execute("DROP TABLE IF EXISTS daily_cost_summary")
    op.execute("DROP TABLE IF EXISTS read_audit_log")
    op.execute("DROP TABLE IF EXISTS watchlist")
    op.execute("DROP TABLE IF EXISTS capital_position")
    op.execute("DROP TABLE IF EXISTS open_loops")
    op.execute("DROP TABLE IF EXISTS briefing_feedback")
    op.execute("DROP TABLE IF EXISTS briefing_synthesis")

    op.execute("""
        ALTER TABLE email_threads
            DROP COLUMN IF EXISTS excluded_reason,
            DROP COLUMN IF EXISTS monitoring_excluded
    """)

    op.execute("""
        ALTER TABLE workspaces
            DROP COLUMN IF EXISTS categorizer_test_precision,
            DROP COLUMN IF EXISTS categorizer_test_recall,
            DROP COLUMN IF EXISTS categorizer_test_passed_at,
            DROP COLUMN IF EXISTS aup_signed_by_email,
            DROP COLUMN IF EXISTS aup_signed_at,
            DROP COLUMN IF EXISTS enable_ai_synthesis,
            DROP COLUMN IF EXISTS daily_cost_cap_usd
    """)
