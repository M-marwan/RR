"""Email ingest worker — polls Gmail every 5 min, stores new messages."""
import logging
from datetime import datetime, timezone
from sqlalchemy import text
from app.db.session import get_db
from app.email.gmail_client import (
    get_service, list_message_ids, get_message, parse_message,
)
from app.email.thread_stitcher import upsert_thread
from app.email.contact_resolver import (
    link_message_to_entities, auto_create_contact_for_unknown,
)
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_account_id(email_address: str) -> str | None:
    with get_db() as db:
        row = db.execute(text("""
            SELECT id FROM email_accounts WHERE email_address = :e
        """), {"e": email_address}).first()
        return str(row[0]) if row else None


def _store_message(parsed: dict, account_id: str, marwan_address: str) -> bool:
    """Insert a parsed message. Returns True if newly inserted."""
    direction = "outbound" if parsed["from_address"].lower() == marwan_address.lower() else "inbound"

    with get_db() as db:
        existing = db.execute(text("""
            SELECT id FROM email_messages WHERE message_id = :mid
        """), {"mid": parsed["message_id"]}).first()
        if existing:
            return False

        # Auto-create contact for the from-address if unknown
        auto_create_contact_for_unknown(parsed["from_address"], parsed.get("from_name") or "")

        all_addresses = [parsed["from_address"]] + (parsed.get("to_addresses") or []) + (parsed.get("cc_addresses") or [])
        entity_ids = link_message_to_entities("", all_addresses)

        result = db.execute(text("""
            INSERT INTO email_messages (
                message_id, account_id, thread_id, in_reply_to,
                direction, from_address, from_name,
                to_addresses, cc_addresses,
                subject, body_text, body_html, snippet,
                sent_at, labels, has_attachments, is_read,
                entity_ids
            ) VALUES (
                :mid, :acc, :tid, :reply,
                :dir, :from_a, :from_n,
                :to_a, :cc_a,
                :subj, :body_t, :body_h, :snip,
                :sent, :labels, :att, :read,
                CAST(:eids AS uuid[])
            )
            RETURNING id
        """), {
            "mid": parsed["message_id"],
            "acc": account_id,
            "tid": parsed["thread_id"],
            "reply": parsed["in_reply_to"],
            "dir": direction,
            "from_a": parsed["from_address"],
            "from_n": parsed["from_name"],
            "to_a": parsed["to_addresses"],
            "cc_a": parsed["cc_addresses"],
            "subj": parsed["subject"],
            "body_t": parsed["body_text"],
            "body_h": parsed["body_html"],
            "snip": parsed["snippet"],
            "sent": parsed["sent_at"],
            "labels": parsed["labels"],
            "att": parsed["has_attachments"],
            "read": parsed["is_read"],
            "eids": "{" + ",".join(entity_ids) + "}" if entity_ids else "{}",
        })
        return True


def ingest_account(account: str = "marwan", lookback_query: str = "newer_than:7d"):
    """Pull recent messages for one account, store anything new, update threads."""
    service = get_service(account)
    if not service:
        logger.warning(f"No Gmail credentials for account '{account}' — skipping. "
                       f"Run scripts/gmail_auth.py to authorize.")
        return {"new_messages": 0, "skipped": True, "reason": "no_credentials"}

    if account == "marwan":
        marwan_address = settings.gmail_marwan_address
    else:
        marwan_address = settings.gmail_subscriptions_address

    account_id = _get_account_id(marwan_address)
    if not account_id:
        logger.warning(f"No email_accounts row for {marwan_address} — skipping.")
        return {"new_messages": 0, "skipped": True, "reason": "no_account_row"}

    message_ids = list_message_ids(service, query=lookback_query, max_results=200)
    new_count = 0
    affected_threads: set[str] = set()

    for mid in message_ids:
        try:
            raw = get_message(service, mid)
            parsed = parse_message(raw)
            inserted = _store_message(parsed, account_id, marwan_address)
            if inserted:
                new_count += 1
                if parsed["thread_id"]:
                    affected_threads.add(parsed["thread_id"])
        except Exception as e:
            logger.exception(f"Failed to ingest message {mid}: {e}")

    # Update last_sync_at
    with get_db() as db:
        db.execute(text("""
            UPDATE email_accounts SET last_sync_at = NOW() WHERE id = :id
        """), {"id": account_id})

    # Recompute affected threads
    for tid in affected_threads:
        try:
            upsert_thread(tid, marwan_address=marwan_address)
        except Exception:
            logger.exception(f"thread upsert failed for {tid}")

    logger.info(f"[{account}] ingested {new_count} new, {len(affected_threads)} threads updated")
    return {"new_messages": new_count, "threads_updated": len(affected_threads)}


def run_all():
    """Entrypoint for the scheduler."""
    results = {}
    for account in ("marwan", "subscriptions"):
        try:
            results[account] = ingest_account(account)
        except Exception as e:
            logger.exception(f"Ingest failed for {account}")
            results[account] = {"error": str(e)}
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run_all())
