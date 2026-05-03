"""Claude-powered email categorization (batch).

Pulls uncategorized email_messages, sends 50 at a time to Claude with the
email_categorize prompt, writes back category/priority/action_summary/tasks.
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from app.db.session import get_db
from app.ai.claude import call_claude

logger = logging.getLogger(__name__)
PROMPTS = Path(__file__).resolve().parent.parent / "ai" / "prompts"
BATCH_SIZE = 50


def _build_prompt(messages: list[dict]) -> str:
    base = (PROMPTS / "email_categorize.md").read_text(encoding="utf-8")
    payload = []
    for m in messages:
        body = (m.get("body_text") or m.get("snippet") or "")[:2000]
        payload.append({
            "id": str(m["id"]),
            "from": m.get("from_address"),
            "from_name": m.get("from_name"),
            "subject": m.get("subject"),
            "sent_at": m.get("sent_at").isoformat() if m.get("sent_at") else None,
            "body": body,
        })
    return base + "\n\n" + json.dumps(payload, indent=2)


def _resolve_entity_refs(refs: list[str]) -> list[str]:
    """Map display-name refs (e.g. 'Stephen') to entity UUIDs."""
    if not refs:
        return []
    with get_db() as db:
        rows = db.execute(text("""
            SELECT id, canonical_name FROM entities WHERE canonical_name = ANY(:names)
        """), {"names": refs}).mappings().all()
    return [str(r["id"]) for r in rows]


def _resolve_project_refs(codes: list[str]) -> list[str]:
    if not codes:
        return []
    with get_db() as db:
        rows = db.execute(text("""
            SELECT id FROM projects WHERE code = ANY(:codes)
        """), {"codes": codes}).scalars().all()
    return [str(r) for r in rows]


def _apply_classification(message_id: str, cls: dict, marwan_entity_id: str | None):
    """Write Claude's classification back to the email_messages row."""
    entity_ids = _resolve_entity_refs(cls.get("entity_refs") or [])
    project_ids = _resolve_project_refs(cls.get("project_refs") or [])

    extracted = cls.get("extracted_tasks") or []
    task_ids: list[str] = []

    with get_db() as db:
        # Build the task rows
        for t in extracted:
            tid = str(uuid.uuid4())
            due = t.get("due")
            db.execute(text("""
                INSERT INTO tasks (id, title, status, source_type, source_email_id,
                                   due_at, project_id, created_at)
                VALUES (:id, :title, 'open', 'email', :src,
                        :due, :proj, NOW())
            """), {
                "id": tid,
                "title": t.get("title", "")[:200],
                "src": message_id,
                "due": due,
                "proj": project_ids[0] if project_ids else None,
            })
            task_ids.append(tid)

        db.execute(text("""
            UPDATE email_messages SET
                category = :cat,
                priority = :pri,
                action_required = :ar,
                action_summary = :sum,
                entity_ids = (
                    SELECT array_agg(DISTINCT eid)
                    FROM unnest(COALESCE(entity_ids, '{}'::uuid[]) || CAST(:new_eids AS uuid[])) AS eid
                ),
                project_ids = CAST(:pids AS uuid[]),
                task_ids = CAST(:tids AS uuid[]),
                processed_at = NOW()
            WHERE id = :id
        """), {
            "cat": cls.get("category"),
            "pri": cls.get("priority"),
            "ar": bool(cls.get("action_required")),
            "sum": cls.get("action_summary"),
            "new_eids": "{" + ",".join(entity_ids) + "}" if entity_ids else "{}",
            "pids": "{" + ",".join(project_ids) + "}" if project_ids else "{}",
            "tids": "{" + ",".join(task_ids) + "}" if task_ids else "{}",
            "id": message_id,
        })


def categorize_batch(limit: int = BATCH_SIZE) -> dict:
    """Pull up to `limit` unprocessed messages, classify them, write back."""
    with get_db() as db:
        rows = db.execute(text("""
            SELECT id, from_address, from_name, subject, body_text, snippet, sent_at
            FROM email_messages
            WHERE processed_at IS NULL
            ORDER BY sent_at DESC
            LIMIT :n
        """), {"n": limit}).mappings().all()

    if not rows:
        return {"processed": 0, "skipped_no_messages": True}

    messages = [dict(r) for r in rows]
    prompt = _build_prompt(messages)

    try:
        result = call_claude(
            prompt,
            job_type="email_categorize",
            job_source="scheduler",
            timeout_seconds=240,
        )
    except Exception as e:
        logger.exception("Claude call failed for email_categorize")
        return {"processed": 0, "error": str(e)}

    # Result is expected to be a dict keyed by email_id
    if not isinstance(result, dict) or "text" in result:
        logger.warning("Claude returned non-JSON response; aborting batch")
        return {"processed": 0, "error": "non_json_response"}

    applied = 0
    for m in messages:
        cls = result.get(str(m["id"]))
        if not cls:
            continue
        try:
            _apply_classification(str(m["id"]), cls, marwan_entity_id=None)
            applied += 1
        except Exception:
            logger.exception(f"failed to apply classification for {m['id']}")

    logger.info(f"categorized {applied}/{len(messages)} messages")
    return {"processed": applied, "of": len(messages)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(categorize_batch())
