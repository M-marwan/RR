"""Read-event audit logging (premortem rule 5.11).

Wraps endpoints that return sensitive data so we have a row in
`read_audit_log` for every access. Required for DIFC / UAE PDPL audit
readiness — auditors want to see "who viewed which email content, when".

Usage
-----

    from app.auth_audit import audit_read

    @router.get("/api/email/threads/{thread_id}")
    @audit_read(target_type="email_thread", target_id_arg="thread_id")
    def get_thread(thread_id: str, user: dict = Depends(current_user), ...):
        ...

The decorator inspects the call's keyword arguments to find:
  - the user (via Depends(current_user) — required)
  - the target id (via the `target_id_arg` name)
  - the request (for IP/User-Agent — optional but logged when present)

Failures in audit logging never break the underlying endpoint — they're
logged at WARN level only.
"""
from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, Callable, Optional

from sqlalchemy import text

from app.db.session import get_db

logger = logging.getLogger(__name__)


def _coerce_target_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _record_read(
    *,
    actor_email: Optional[str],
    target_type: str,
    target_id: str,
    workspace_id: Optional[str],
    ip: Optional[str],
    user_agent: Optional[str],
) -> None:
    try:
        with get_db() as db:
            db.execute(text("""
                INSERT INTO read_audit_log
                    (workspace_id, actor_email, target_type, target_id,
                     ip_address, user_agent)
                VALUES (:wid, :email, :tt, :tid, :ip, :ua)
            """), {
                "wid": workspace_id,
                "email": actor_email,
                "tt": target_type,
                "tid": target_id,
                "ip": ip,
                "ua": user_agent,
            })
    except Exception:
        # Never let audit failure break the actual endpoint — log and continue.
        logger.exception("read_audit_log insert failed for %s/%s", target_type, target_id)


def audit_read(*, target_type: str, target_id_arg: str = "id"):
    """Decorator factory for FastAPI endpoint functions.

    Args:
        target_type: classifier for `read_audit_log.target_type`
                     (e.g. 'email_thread', 'capital_position', 'audit_log').
        target_id_arg: name of the function parameter that holds the
                     target's identifier. Defaults to 'id'.
    """

    def decorator(func: Callable):
        sig = inspect.signature(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Bind args/kwargs to the function's parameters so we can look up
            # named values regardless of positional vs. keyword call style.
            try:
                bound = sig.bind_partial(*args, **kwargs)
            except TypeError:
                bound = None

            target_id_value = None
            user = None
            request = None
            workspace_id = None

            if bound is not None:
                target_id_value = bound.arguments.get(target_id_arg)
                user = bound.arguments.get("user")
                request = bound.arguments.get("request")
                workspace_id = bound.arguments.get("workspace_id")

            actor_email = None
            if isinstance(user, dict):
                actor_email = (
                    user.get("preferred_username") or user.get("email") or ""
                ).lower() or None

            ip = None
            ua = None
            if request is not None:
                try:
                    ip = request.client.host if request.client else None
                    ua = request.headers.get("user-agent")
                except Exception:
                    pass

            _record_read(
                actor_email=actor_email,
                target_type=target_type,
                target_id=_coerce_target_id(target_id_value) or "",
                workspace_id=_coerce_target_id(workspace_id),
                ip=ip,
                user_agent=ua,
            )

            return func(*args, **kwargs)

        return wrapper

    return decorator
