"""Admin endpoints — manual trigger for workers, smoke tests."""
from fastapi import APIRouter, HTTPException
from app.workers.email_ingest import run_all as ingest_emails, ingest_account
from app.workers.email_categorize import categorize_batch
from app.workers.email_sender import send_approved
from app.email.thread_stitcher import recompute_all_open_loops
from app.ai.claude import call_claude, ClaudeError
from app.email.gmail_client import get_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/email/ingest")
def trigger_ingest(account: str = "marwan"):
    return ingest_account(account)


@router.post("/email/ingest-all")
def trigger_ingest_all():
    return ingest_emails()


@router.post("/email/categorize")
def trigger_categorize(limit: int = 50):
    return categorize_batch(limit=limit)


@router.post("/email/sweep-open-loops")
def trigger_open_loop_sweep():
    recompute_all_open_loops()
    return {"ok": True}


@router.post("/email/send-approved")
def trigger_sender():
    return send_approved()


@router.get("/gmail/status")
def gmail_status(account: str = "marwan"):
    """Reports whether OAuth tokens are present and the API responds."""
    service = get_service(account)
    if not service:
        return {"authorized": False, "account": account,
                "hint": "Run python scripts/gmail_auth.py to authorize."}
    try:
        profile = service.users().getProfile(userId="me").execute()
        return {
            "authorized": True,
            "account": account,
            "email": profile.get("emailAddress"),
            "messages_total": profile.get("messagesTotal"),
            "threads_total": profile.get("threadsTotal"),
        }
    except Exception as e:
        return {"authorized": False, "account": account, "error": str(e)}


@router.post("/claude/test")
def claude_test():
    """Smoke test: round-trip through the Claude CLI."""
    try:
        result = call_claude(
            "Reply with the single word: ok",
            job_type="smoke_test",
            job_source="admin_api",
            timeout_seconds=60,
            include_system_context=False,
        )
        return {"ok": True, "result": result}
    except ClaudeError as e:
        raise HTTPException(500, str(e))
