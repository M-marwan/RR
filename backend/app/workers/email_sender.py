"""Email sender worker — picks up approved drafts from outbound_queue and sends them via Gmail."""
import logging
from sqlalchemy import text
from app.db.session import get_db
from app.email.gmail_client import get_service, send_message

logger = logging.getLogger(__name__)


def send_approved():
    """Send every outbound_queue row whose status is 'approved'."""
    sent = 0
    failed = 0
    with get_db() as db:
        rows = db.execute(text("""
            SELECT * FROM outbound_queue
            WHERE status = 'approved'
            ORDER BY approved_at ASC NULLS FIRST
            LIMIT 20
        """)).mappings().all()

    for row in rows:
        queue_id = row["id"]
        with get_db() as db:
            db.execute(text("""
                UPDATE outbound_queue SET status = 'sending',
                    send_attempts = send_attempts + 1
                WHERE id = :id
            """), {"id": queue_id})

        try:
            service = get_service("marwan")
            if not service:
                raise RuntimeError("Gmail not authorized")

            response = send_message(
                service,
                to=list(row["to_addresses"]),
                subject=row["subject"],
                body_text=row["body_text"],
                cc=list(row["cc_addresses"] or []),
                in_reply_to=row["reply_to_message_id"],
                thread_id=row["thread_id"],
            )

            with get_db() as db:
                db.execute(text("""
                    UPDATE outbound_queue
                    SET status = 'sent', sent_at = NOW(),
                        sent_message_id = :mid, last_error = NULL
                    WHERE id = :id
                """), {"id": queue_id, "mid": response.get("id")})
            sent += 1
            logger.info(f"Sent {queue_id} to {row['to_addresses']}")

        except Exception as e:
            logger.exception(f"Failed to send {queue_id}")
            with get_db() as db:
                db.execute(text("""
                    UPDATE outbound_queue
                    SET status = 'failed', last_error = :err
                    WHERE id = :id
                """), {"id": queue_id, "err": str(e)[:1000]})
            failed += 1

    return {"sent": sent, "failed": failed, "total": len(rows)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(send_approved())
