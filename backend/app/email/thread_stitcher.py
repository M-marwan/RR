"""Stitch email_messages into email_threads and detect open loops."""
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from app.db.session import get_db


OPEN_LOOP_HOURS = 48


def upsert_thread(thread_id: str, marwan_address: str = "014.marwan@gmail.com"):
    """Recompute the thread row from its constituent messages."""
    with get_db() as db:
        rows = db.execute(text("""
            SELECT direction, from_address, to_addresses, cc_addresses,
                   subject, sent_at, category, account_id, entity_ids
            FROM email_messages
            WHERE thread_id = :tid
            ORDER BY sent_at ASC
        """), {"tid": thread_id}).mappings().all()

        if not rows:
            return

        first = rows[0]
        last = rows[-1]
        message_count = len(rows)

        # Collect unique participants
        participants: set[str] = set()
        for r in rows:
            participants.add(r["from_address"])
            for a in (r["to_addresses"] or []):
                participants.add(a)
            for a in (r["cc_addresses"] or []):
                participants.add(a)
        participants.discard("")

        # Status: open loop = last message is outbound (or last inbound from
        # Marwan to himself is rare) AND no reply for OPEN_LOOP_HOURS.
        last_sent_at = last["sent_at"]
        now = datetime.now(timezone.utc)
        hours_since = (now - last_sent_at).total_seconds() / 3600 if last_sent_at else 0

        last_was_outbound = last["direction"] == "outbound"
        open_loop = last_was_outbound and hours_since >= OPEN_LOOP_HOURS
        days_without_reply = int(hours_since // 24) if last_was_outbound else 0

        if open_loop:
            status = "waiting_reply"
        elif last_was_outbound:
            status = "replied"  # Marwan replied last
        else:
            status = "open"  # ball is in Marwan's court

        # Pick category: most recent non-null one
        category = None
        for r in reversed(rows):
            if r["category"]:
                category = r["category"]
                break

        # Aggregate entity_ids across all messages
        entity_ids: set = set()
        for r in rows:
            for eid in (r["entity_ids"] or []):
                entity_ids.add(str(eid))

        account_ids = list({str(r["account_id"]) for r in rows if r["account_id"]})

        acc_literal = "{" + ",".join(account_ids) + "}" if account_ids else "{}"
        eids_literal = "{" + ",".join(entity_ids) + "}" if entity_ids else "{}"

        db.execute(text("""
            INSERT INTO email_threads
                (thread_id, account_ids, subject, participants, message_count,
                 first_message_at, last_message_at, category, status,
                 open_loop, open_loop_since, days_without_reply, entity_ids,
                 updated_at)
            VALUES
                (:tid, CAST(:acc AS uuid[]), :subj, :parts, :mc,
                 :first, :last, CAST(:cat AS email_category), :status,
                 :ol, :ols, :dwr, CAST(:eids AS uuid[]),
                 NOW())
            ON CONFLICT (thread_id) DO UPDATE SET
                account_ids = EXCLUDED.account_ids,
                subject = EXCLUDED.subject,
                participants = EXCLUDED.participants,
                message_count = EXCLUDED.message_count,
                first_message_at = EXCLUDED.first_message_at,
                last_message_at = EXCLUDED.last_message_at,
                category = COALESCE(EXCLUDED.category, email_threads.category),
                status = EXCLUDED.status,
                open_loop = EXCLUDED.open_loop,
                open_loop_since = EXCLUDED.open_loop_since,
                days_without_reply = EXCLUDED.days_without_reply,
                entity_ids = EXCLUDED.entity_ids,
                updated_at = NOW()
        """), {
            "tid": thread_id,
            "acc": acc_literal,
            "subj": last["subject"] or first["subject"],
            "parts": list(participants),
            "mc": message_count,
            "first": first["sent_at"],
            "last": last["sent_at"],
            "cat": category,
            "status": status,
            "ol": open_loop,
            "ols": last_sent_at if open_loop else None,
            "dwr": days_without_reply,
            "eids": eids_literal,
        })


def recompute_all_open_loops():
    """Sweep: refresh open_loop status for every thread. Run hourly."""
    with get_db() as db:
        thread_ids = db.execute(text("""
            SELECT DISTINCT thread_id FROM email_messages WHERE thread_id IS NOT NULL
        """)).scalars().all()
    for tid in thread_ids:
        upsert_thread(tid)
