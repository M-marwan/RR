from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text
from pydantic import BaseModel
from app.db.session import get_db
from typing import Optional
import uuid

router = APIRouter(tags=["email"])


@router.get("/email/threads")
def list_threads(
    category: Optional[str] = None,
    status: Optional[str] = None,
    project_id: Optional[str] = None,
    open_loop: Optional[bool] = None,
    canvas_col: Optional[str] = None,
    show_noise: bool = False,
    q: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = []
    params: dict = {"limit": limit, "offset": offset}

    if category:
        filters.append("t.category = :category")
        params["category"] = category
    if status:
        filters.append("t.status = :status")
        params["status"] = status
    if open_loop is not None:
        filters.append("t.open_loop = :open_loop")
        params["open_loop"] = open_loop
    if project_id:
        if project_id == "inbox":
            filters.append("t.canvas_project_id IS NULL")
            if not show_noise:
                # Inbox by default: hide noise/admin/newsletter that haven't been
                # explicitly assigned to a project. They're in the database but
                # off the command board.
                filters.append("(t.category IS NULL OR t.category NOT IN ('noise','admin','newsletter'))")
                filters.append("t.hidden_from_inbox = false")
        else:
            filters.append("t.canvas_project_id = :project_id")
            params["project_id"] = project_id
    if q:
        filters.append("t.subject ILIKE :q")
        params["q"] = f"%{q}%"

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    sql = f"""
        SELECT t.*,
               p.name AS project_name,
               p.code AS project_code,
               e.canonical_name AS assigned_to_name
        FROM email_threads t
        LEFT JOIN projects p ON p.id = t.canvas_project_id
        LEFT JOIN entities e ON e.id = t.assigned_to_entity_id
        {where}
        ORDER BY
            CASE t.category WHEN 'action_required' THEN 0 ELSE 1 END,
            t.open_loop DESC,
            t.last_message_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """
    with get_db() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


# ── Thread mutations: assign, move, status, hide ─────────────────────────────

class ThreadPatch(BaseModel):
    canvas_project_id: Optional[str] = None
    status: Optional[str] = None
    assigned_to_entity_id: Optional[str] = None
    hidden_from_inbox: Optional[bool] = None
    canvas_position: Optional[int] = None
    clear_project: bool = False
    clear_assignee: bool = False


@router.patch("/email/threads/{thread_key}")
def patch_thread(thread_key: str, body: ThreadPatch):
    """Update canvas placement, status, assignment, or visibility of a thread.

    Accepts either the Gmail thread_id or the email_threads.id (UUID)."""
    sets = []
    params: dict = {"key": thread_key}

    if body.clear_project:
        sets.append("canvas_project_id = NULL")
    elif body.canvas_project_id is not None:
        sets.append("canvas_project_id = CAST(:proj AS uuid)")
        params["proj"] = body.canvas_project_id

    if body.clear_assignee:
        sets.append("assigned_to_entity_id = NULL")
    elif body.assigned_to_entity_id is not None:
        sets.append("assigned_to_entity_id = CAST(:assignee AS uuid)")
        params["assignee"] = body.assigned_to_entity_id

    if body.status is not None:
        sets.append("status = CAST(:status AS thread_status)")
        params["status"] = body.status

    if body.hidden_from_inbox is not None:
        sets.append("hidden_from_inbox = :hidden")
        params["hidden"] = body.hidden_from_inbox

    if body.canvas_position is not None:
        sets.append("canvas_position = :pos")
        params["pos"] = body.canvas_position

    if not sets:
        raise HTTPException(400, "No fields to update")

    sets.append("updated_at = NOW()")
    sql = f"""
        UPDATE email_threads
        SET {', '.join(sets)}
        WHERE thread_id = :key OR id::text = :key
        RETURNING *
    """
    with get_db() as db:
        row = db.execute(text(sql), params).mappings().first()
    if not row:
        raise HTTPException(404, "Thread not found")
    return dict(row)


# ── Team list (people contacts that we know how to email) ────────────────────

@router.get("/email/team")
def list_team():
    """Returns assignable team members — entities of type 'person' that have a contact email."""
    with get_db() as db:
        rows = db.execute(text("""
            SELECT DISTINCT ON (e.id)
                   e.id, e.canonical_name, c.email_address, c.label
            FROM entities e
            LEFT JOIN contacts c ON c.entity_id = e.id
            WHERE e.type = 'person'
              AND e.canonical_name <> 'Marwan'
              AND e.canonical_name <> '00 Marwan'
            ORDER BY e.id, c.is_primary DESC NULLS LAST
        """)).mappings().all()
    return [dict(r) for r in rows]


# ── Comment / reply on a thread (becomes a queued email) ─────────────────────

class ThreadComment(BaseModel):
    body_text: str
    send_as_email: bool = False
    to_email: Optional[str] = None
    to_entity_id: Optional[str] = None
    subject_override: Optional[str] = None


@router.post("/email/threads/{thread_key}/comment")
def comment_on_thread(thread_key: str, body: ThreadComment):
    """Two modes:
       1. Internal note (send_as_email=false): appends to thread.internal_notes.
       2. Email reply (send_as_email=true): drafts an outbound email to the
          assignee or to_email, queued for Marwan's approval before sending.
    """
    with get_db() as db:
        thread = db.execute(text("""
            SELECT t.*, e.canonical_name AS assigned_to_name,
                   (SELECT email_address FROM contacts
                    WHERE entity_id = t.assigned_to_entity_id
                    ORDER BY is_primary DESC NULLS LAST LIMIT 1) AS assignee_email,
                   (SELECT message_id FROM email_messages
                    WHERE thread_id = t.thread_id
                    ORDER BY sent_at DESC LIMIT 1) AS latest_message_id
            FROM email_threads t
            LEFT JOIN entities e ON e.id = t.assigned_to_entity_id
            WHERE t.thread_id = :key OR t.id::text = :key
        """), {"key": thread_key}).mappings().first()
        if not thread:
            raise HTTPException(404, "Thread not found")

        if not body.send_as_email:
            db.execute(text("""
                UPDATE email_threads
                SET internal_notes = COALESCE(internal_notes, '{}'::text[]) || :note,
                    updated_at = NOW()
                WHERE id = :id
            """), {"id": thread["id"], "note": body.body_text})
            return {"saved_as": "internal_note"}

        # Email mode — resolve recipient
        recipient = body.to_email
        if not recipient and body.to_entity_id:
            r = db.execute(text("""
                SELECT email_address FROM contacts
                WHERE entity_id = CAST(:eid AS uuid)
                ORDER BY is_primary DESC NULLS LAST LIMIT 1
            """), {"eid": body.to_entity_id}).mappings().first()
            if r:
                recipient = r["email_address"]
        if not recipient:
            recipient = thread["assignee_email"]
        if not recipient:
            raise HTTPException(400, "No recipient: pass to_email, to_entity_id, or assign the thread first.")

        subject = body.subject_override or (thread["subject"] or "")
        if subject and not subject.lower().startswith("re:"):
            subject = "Re: " + subject

        from app.config import get_settings
        settings = get_settings()
        from_address = settings.gmail_marwan_address

        account = db.execute(
            text("SELECT id FROM email_accounts WHERE email_address = :a"),
            {"a": from_address},
        ).mappings().first()

        new_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO outbound_queue (id, from_account_id, from_address, to_addresses,
                subject, body_text, reply_to_message_id, thread_id, drafted_by, status)
            VALUES (:id, :acc, :from_a, ARRAY[:to_a]::text[], :subj, :body,
                    :reply, :tid, 'user_comment', 'draft')
        """), {
            "id": new_id,
            "acc": str(account["id"]) if account else None,
            "from_a": from_address,
            "to_a": recipient,
            "subj": subject,
            "body": body.body_text,
            "reply": thread["latest_message_id"],
            "tid": thread["thread_id"],
        })

    return {"saved_as": "email_draft", "queue_id": new_id, "to": recipient,
            "next_step": "Approve at /api/compose/approve/{queue_id} to send."}


@router.get("/email/threads/{thread_id}")
def get_thread(thread_id: str):
    with get_db() as db:
        thread = db.execute(
            text("SELECT * FROM email_threads WHERE thread_id = :id OR id::text = :id"),
            {"id": thread_id},
        ).mappings().first()
        if not thread:
            raise HTTPException(404, "Thread not found")

        messages = db.execute(text("""
            SELECT id, message_id, direction, from_address, from_name,
                   to_addresses, subject, body_text, snippet, sent_at,
                   category, action_summary, entity_ids
            FROM email_messages
            WHERE thread_id = :tid
            ORDER BY sent_at ASC
        """), {"tid": thread["thread_id"]}).mappings().all()

    return {
        "thread": dict(thread),
        "messages": [dict(m) for m in messages],
    }


@router.get("/email/messages/{message_id}")
def get_message(message_id: str):
    with get_db() as db:
        row = db.execute(
            text("SELECT * FROM email_messages WHERE id::text = :id OR message_id = :id"),
            {"id": message_id},
        ).mappings().first()
    if not row:
        raise HTTPException(404, "Message not found")
    return dict(row)


# ── Contacts ─────────────────────────────────────────────────────────────────

@router.get("/email/contacts")
def list_contacts(q: Optional[str] = None, limit: int = 50):
    params: dict = {"limit": limit}
    where = ""
    if q:
        where = "WHERE c.display_name ILIKE :q OR c.email_address ILIKE :q"
        params["q"] = f"%{q}%"
    sql = f"""
        SELECT c.*, e.canonical_name AS entity_name, e.type AS entity_type
        FROM contacts c
        LEFT JOIN entities e ON e.id = c.entity_id
        {where}
        ORDER BY c.last_used_at DESC NULLS LAST, c.display_name
        LIMIT :limit
    """
    with get_db() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/email/contacts/resolve")
def resolve_contact(name: str, thread_id: Optional[str] = None):
    """Disambiguation: given a name, return matching contacts ordered by relevance.
    If thread_id is provided, pre-scores by domain match with thread participants."""
    params: dict = {"q": f"%{name}%"}
    sql = """
        SELECT c.*, e.canonical_name AS entity_name
        FROM contacts c
        LEFT JOIN entities e ON e.id = c.entity_id
        WHERE c.display_name ILIKE :q OR e.canonical_name ILIKE :q OR e.aliases::text ILIKE :q
        ORDER BY c.is_primary DESC, c.last_used_at DESC NULLS LAST
        LIMIT 10
    """
    with get_db() as db:
        contacts = db.execute(text(sql), params).mappings().all()
        thread_domains: list[str] = []
        if thread_id:
            thread = db.execute(
                text("SELECT participants FROM email_threads WHERE thread_id = :id"),
                {"id": thread_id},
            ).mappings().first()
            if thread and thread["participants"]:
                thread_domains = [
                    p.split("@")[1] for p in thread["participants"] if "@" in p
                ]

    results = [dict(c) for c in contacts]
    if thread_domains:
        for r in results:
            domain = r.get("domain", "")
            r["domain_match"] = domain in thread_domains
        results.sort(key=lambda x: (not x.get("domain_match"), not x.get("is_primary")))

    return results


class ContactCreate(BaseModel):
    display_name: str
    email_address: str
    label: Optional[str] = None
    entity_id: Optional[str] = None
    is_primary: bool = False


@router.post("/email/contacts")
def create_contact(body: ContactCreate):
    with get_db() as db:
        row = db.execute(text("""
            INSERT INTO contacts (id, display_name, email_address, label, entity_id, is_primary)
            VALUES (:id, :display_name, :email_address, :label, :entity_id, :is_primary)
            ON CONFLICT (entity_id, email_address) DO UPDATE
              SET label = EXCLUDED.label, is_primary = EXCLUDED.is_primary
            RETURNING *
        """), {
            "id": str(uuid.uuid4()),
            **body.model_dump(),
        }).mappings().first()
    return dict(row)


# ── Compose / Outbound queue ─────────────────────────────────────────────────

class ComposeDraft(BaseModel):
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str] = []
    subject: str
    body_text: str
    body_html: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    thread_id: Optional[str] = None
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    drafted_by: str = "user"
    draft_prompt: Optional[str] = None


@router.post("/compose/queue")
def queue_draft(body: ComposeDraft):
    with get_db() as db:
        account = db.execute(
            text("SELECT id FROM email_accounts WHERE email_address = :addr"),
            {"addr": body.from_address},
        ).mappings().first()
        account_id = str(account["id"]) if account else None

        row = db.execute(text("""
            INSERT INTO outbound_queue (id, from_account_id, from_address, to_addresses,
                cc_addresses, subject, body_text, body_html, reply_to_message_id,
                thread_id, project_id, task_id, drafted_by, draft_prompt, status)
            VALUES (:id, :account_id, :from_address, :to_addresses, :cc_addresses,
                :subject, :body_text, :body_html, :reply_to_message_id, :thread_id,
                :project_id, :task_id, :drafted_by, :draft_prompt, 'draft')
            RETURNING *
        """), {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            **body.model_dump(),
        }).mappings().first()
    return dict(row)


@router.post("/compose/approve/{queue_id}")
def approve_draft(queue_id: str):
    with get_db() as db:
        row = db.execute(
            text("SELECT * FROM outbound_queue WHERE id = :id"),
            {"id": queue_id},
        ).mappings().first()
        if not row:
            raise HTTPException(404, "Draft not found")
        if row["status"] not in ("draft",):
            raise HTTPException(400, f"Cannot approve: status is {row['status']}")

        db.execute(text("""
            UPDATE outbound_queue SET status = 'approved', approved_at = NOW()
            WHERE id = :id
        """), {"id": queue_id})
    return {"ok": True, "message": "Email queued for sending."}


@router.get("/compose/drafts")
def list_drafts(status: str = "draft"):
    with get_db() as db:
        rows = db.execute(text("""
            SELECT * FROM outbound_queue WHERE status = :status
            ORDER BY created_at DESC LIMIT 50
        """), {"status": status}).mappings().all()
    return [dict(r) for r in rows]
