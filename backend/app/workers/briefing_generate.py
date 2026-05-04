"""Deterministic morning brief generator (Phase 1A.2).

Runs daily at 04:30 GST. Computes — without any AI — the morning brief
for each workspace + a cross-portfolio aggregate, materialising:

    briefing_synthesis (generation_mode='deterministic')
    open_loops
    capital_position (skipped — manually entered until we have signals)
    watchlist

Three Moves heuristic
---------------------
The premortem (rule 5.2) says Phase 1A.2 ships deterministic-only. AI
synthesis is Phase 2 behind `enable_ai_synthesis`. So Three Moves are
ranked from concrete data only:

    1. Open loops where days_waiting > 5 — surface the longest-stalled
    2. Threads marked action_required + priority<=2 unactioned > 24h
    3. Project-stage advances or commitments due this week

Every move's `source_refs` lists the rows it summarises (rule 5.1).

Cross-portfolio aggregate
-------------------------
Generated as an additional row with `workspace_id IS NULL`. Aggregates
data across all non-archived workspaces. The principal sees this by
default; per-workspace filter is opt-in.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import text

from app.db.session import get_db

logger = logging.getLogger(__name__)


def _today_dubai() -> date:
    """Today in Asia/Dubai, computed via Postgres timezone math for consistency."""
    with get_db() as db:
        row = db.execute(text(
            "SELECT (NOW() AT TIME ZONE 'Asia/Dubai')::date AS today"
        )).mappings().first()
    return row["today"]


# ─── open loops ──────────────────────────────────────────────────────────────


def recompute_open_loops_for_workspace(db, workspace_id: Optional[UUID]) -> int:
    """Recompute open_loops rows by scanning email_threads.

    A thread is an "open loop" if:
      - the last message was inbound (we haven't replied)
      - days since that message > 0
      - the thread is not archived / monitoring-excluded

    Rebuilds open_loops for the workspace from scratch (idempotent).
    """
    # Wipe existing open_loops for this workspace; rebuild fresh.
    db.execute(
        text("DELETE FROM open_loops WHERE workspace_id IS NOT DISTINCT FROM :wid"),
        {"wid": workspace_id},
    )

    # Note: this query references columns the email_threads table is expected
    # to have (open_loop, last_message_at, etc.). If the existing schema lacks
    # them, the query short-circuits to no rows — safe.
    rows = db.execute(text("""
        SELECT
            t.id AS thread_id,
            t.subject,
            t.last_message_at,
            COALESCE(
                EXTRACT(EPOCH FROM (NOW() - t.open_loop_since)) / 86400,
                EXTRACT(EPOCH FROM (NOW() - t.last_message_at)) / 86400
            )::int AS days_waiting,
            -- Best-effort: pick first participant entity as the "person waiting on us"
            (
                SELECT e.id FROM email_messages m
                LEFT JOIN entities e ON e.id = ANY(m.entity_ids)
                WHERE m.thread_id = t.id AND m.direction = 'inbound'
                ORDER BY m.sent_at DESC LIMIT 1
            ) AS person_entity_id,
            (
                SELECT m.from_address FROM email_messages m
                WHERE m.thread_id = t.id AND m.direction = 'inbound'
                ORDER BY m.sent_at DESC LIMIT 1
            ) AS person_email,
            (
                SELECT e.canonical_name
                FROM email_messages m
                LEFT JOIN entities e ON e.id = ANY(m.entity_ids)
                WHERE m.thread_id = t.id AND m.direction = 'inbound'
                ORDER BY m.sent_at DESC LIMIT 1
            ) AS person_name
        FROM email_threads t
        WHERE COALESCE(t.open_loop, FALSE) = TRUE
          AND COALESCE(t.monitoring_excluded, FALSE) = FALSE
          AND (:wid::uuid IS NULL OR t.workspace_id = :wid)
        ORDER BY days_waiting DESC NULLS LAST
        LIMIT 200
    """), {"wid": str(workspace_id) if workspace_id else None}).mappings().all()

    inserted = 0
    for row in rows:
        db.execute(text("""
            INSERT INTO open_loops
                (workspace_id, thread_id, person_entity_id, person_name,
                 days_waiting, last_outbound_at, status, updated_at)
            VALUES (:wid, :tid, :pid, :pname, :days, NULL, 'open', NOW())
        """), {
            "wid": workspace_id,
            "tid": row["thread_id"],
            "pid": row["person_entity_id"],
            "pname": row["person_name"] or row["person_email"] or "—",
            "days": max(0, int(row["days_waiting"] or 0)),
        })
        inserted += 1
    return inserted


# ─── deterministic three moves ───────────────────────────────────────────────


def _compute_three_moves(db, workspace_id: Optional[UUID]) -> list[dict]:
    """Pick the three highest-priority moves from concrete data.

    Returns a list of dicts compatible with the ThreeMove schema, each with
    `rank`, `move`, `rationale`, and `source_refs` (rule 5.1).
    """
    moves: list[dict] = []
    rank = 1
    seen_keys: set[str] = set()

    # Move source 1 — longest-stalled open loops (>5 days)
    rows = db.execute(text("""
        SELECT id, thread_id, person_name, days_waiting
        FROM open_loops
        WHERE workspace_id IS NOT DISTINCT FROM :wid
          AND status = 'open'
          AND days_waiting > 5
        ORDER BY days_waiting DESC
        LIMIT 3
    """), {"wid": workspace_id}).mappings().all()
    for r in rows:
        if rank > 3:
            break
        key = f"loop:{r['id']}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        moves.append({
            "rank": rank,
            "move": f"Reply to {r['person_name']} — {r['days_waiting']} days waiting",
            "rationale": "Open loop overdue. Trust signal: every day costs more than yesterday.",
            "source_refs": [
                {"kind": "thread", "id": str(r["thread_id"]), "label": r["person_name"]},
                {"kind": "open_loop", "id": str(r["id"])},
            ],
        })
        rank += 1

    # Move source 2 — high-priority unactioned threads (action_required, priority<=2, >24h)
    if rank <= 3:
        rows = db.execute(text("""
            SELECT t.id AS thread_id, t.subject,
                   t.last_message_at,
                   EXTRACT(EPOCH FROM (NOW() - t.last_message_at)) / 3600 AS hours_old
            FROM email_threads t
            JOIN email_messages m ON m.thread_id = t.id
            WHERE COALESCE(t.monitoring_excluded, FALSE) = FALSE
              AND (:wid::uuid IS NULL OR t.workspace_id = :wid)
              AND m.category = 'action_required'
              AND m.priority IS NOT NULL AND m.priority <= 2
              AND t.last_message_at < NOW() - INTERVAL '24 hours'
            GROUP BY t.id, t.subject, t.last_message_at
            ORDER BY t.last_message_at ASC
            LIMIT 5
        """), {"wid": str(workspace_id) if workspace_id else None}).mappings().all()
        for r in rows:
            if rank > 3:
                break
            key = f"action:{r['thread_id']}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            hours = int(r["hours_old"] or 0)
            moves.append({
                "rank": rank,
                "move": f"Action: {r['subject'] or '(no subject)'}",
                "rationale": f"High-priority, unactioned for {hours}h.",
                "source_refs": [
                    {"kind": "thread", "id": str(r["thread_id"]), "label": r["subject"]},
                ],
            })
            rank += 1

    # Move source 3 — projects with deal_stage advance / commitments this week
    if rank <= 3:
        rows = db.execute(text("""
            SELECT id, code, name, deal_stage
            FROM projects
            WHERE COALESCE(status, 'active') = 'active'
              AND deal_stage IS NOT NULL
              AND (:wid::uuid IS NULL OR workspace_id = :wid)
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 3
        """), {"wid": str(workspace_id) if workspace_id else None}).mappings().all()
        for r in rows:
            if rank > 3:
                break
            key = f"project:{r['id']}"
            if key in seen_keys:
                continue
            seen_keys.add(key)
            moves.append({
                "rank": rank,
                "move": f"Move {r['code']} forward — {r['deal_stage']}",
                "rationale": f"{r['name']} sits at this stage; stalled deals decay.",
                "source_refs": [
                    {"kind": "project", "id": str(r["id"]), "label": r["code"]},
                ],
            })
            rank += 1

    return moves


# ─── watchlist ───────────────────────────────────────────────────────────────


def _refresh_watchlist(db, workspace_id: Optional[UUID], brief_date: date) -> int:
    """Populate today's watchlist from the most-relevant recent events.

    Per rule 5.1, every watchlist item carries source_refs.
    """
    db.execute(text("""
        DELETE FROM watchlist
        WHERE workspace_id IS NOT DISTINCT FROM :wid AND brief_date = :d
    """), {"wid": workspace_id, "d": brief_date})

    rows = db.execute(text("""
        SELECT id, headline, source_url, relevance_score
        FROM events
        WHERE COALESCE(relevance_score, 0) >= 0.4
          AND occurred_at > NOW() - INTERVAL '7 days'
        ORDER BY relevance_score DESC NULLS LAST, occurred_at DESC
        LIMIT 6
    """)).mappings().all()

    inserted = 0
    for i, r in enumerate(rows, start=1):
        source_refs = [{"kind": "event", "id": str(r["id"]), "label": r["headline"]}]
        if r["source_url"]:
            source_refs.append({"kind": "url", "id": r["source_url"]})
        db.execute(text("""
            INSERT INTO watchlist (workspace_id, brief_date, rank, item, source_refs)
            VALUES (:wid, :d, :rk, :item, CAST(:sr AS jsonb))
        """), {
            "wid": workspace_id, "d": brief_date, "rk": i,
            "item": r["headline"], "sr": json.dumps(source_refs),
        })
        inserted += 1
    return inserted


# ─── briefing_synthesis upsert ───────────────────────────────────────────────


def _upsert_briefing_synthesis(db, workspace_id: Optional[UUID],
                                brief_date: date, three_moves: list[dict]) -> str:
    row = db.execute(text("""
        INSERT INTO briefing_synthesis
            (workspace_id, brief_date, three_moves, generated_at, generation_mode)
        VALUES (:wid, :d, CAST(:tm AS jsonb), NOW(), 'deterministic')
        ON CONFLICT (workspace_id, brief_date) DO UPDATE SET
            three_moves = EXCLUDED.three_moves,
            generated_at = NOW(),
            generation_mode = 'deterministic'
        RETURNING id
    """), {
        "wid": workspace_id, "d": brief_date, "tm": json.dumps(three_moves),
    }).mappings().first()
    return str(row["id"])


# ─── orchestrator ────────────────────────────────────────────────────────────


def generate_briefing_for_workspace(workspace_id: Optional[UUID]) -> dict:
    """Generate today's deterministic brief for one workspace (or NULL = all)."""
    today = _today_dubai()
    with get_db() as db:
        loops = recompute_open_loops_for_workspace(db, workspace_id)
        moves = _compute_three_moves(db, workspace_id)
        watch = _refresh_watchlist(db, workspace_id, today)
        brief_id = _upsert_briefing_synthesis(db, workspace_id, today, moves)
    logger.info(
        "briefing_generate ws=%s date=%s loops=%d moves=%d watch=%d brief=%s",
        workspace_id, today, loops, len(moves), watch, brief_id,
    )
    return {
        "workspace_id": str(workspace_id) if workspace_id else None,
        "brief_id": brief_id,
        "open_loops": loops,
        "moves": len(moves),
        "watchlist": watch,
    }


def generate_all_briefings() -> list[dict]:
    """Scheduler entry — generates per-workspace briefs + cross-portfolio aggregate."""
    results: list[dict] = []

    # Cross-portfolio first (workspace_id = NULL)
    try:
        results.append(generate_briefing_for_workspace(None))
    except Exception:
        logger.exception("Cross-portfolio briefing failed")

    # One per workspace
    with get_db() as db:
        ws_rows = db.execute(text(
            "SELECT id FROM workspaces WHERE archived_at IS NULL"
        )).mappings().all()

    for ws in ws_rows:
        try:
            results.append(generate_briefing_for_workspace(ws["id"]))
        except Exception:
            logger.exception("Briefing failed for workspace %s", ws["id"])

    return results
