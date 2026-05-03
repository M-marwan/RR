"""Resolve incoming email addresses to known entities + auto-create contacts."""
import uuid
from sqlalchemy import text
from app.db.session import get_db


def link_message_to_entities(message_db_id: str, addresses: list[str]) -> list[str]:
    """Given a list of email addresses on a message, find entity_ids via contacts."""
    if not addresses:
        return []
    addresses = [a.lower() for a in addresses if a]
    with get_db() as db:
        rows = db.execute(text("""
            SELECT DISTINCT entity_id FROM contacts
            WHERE LOWER(email_address) = ANY(:addrs) AND entity_id IS NOT NULL
        """), {"addrs": addresses}).scalars().all()
    return [str(r) for r in rows if r]


def auto_create_contact_for_unknown(email_address: str, display_name: str = ""):
    """If an email arrives from an unknown address, create a placeholder contact
    with no entity_id. User can later link it to an entity from the dashboard.
    """
    if not email_address:
        return
    email_address = email_address.lower()
    with get_db() as db:
        existing = db.execute(text("""
            SELECT 1 FROM contacts WHERE LOWER(email_address) = :e
        """), {"e": email_address}).first()
        if existing:
            return
        db.execute(text("""
            INSERT INTO contacts (id, display_name, email_address, added_by)
            VALUES (:id, :name, :email, 'auto_detected')
            ON CONFLICT DO NOTHING
        """), {
            "id": str(uuid.uuid4()),
            "name": display_name or email_address.split("@")[0],
            "email": email_address,
        })
