"""RFC 2822 thread-key derivation (premortem rule 5.8).

This is a **pure** function used by the ingester to decide which thread a
new message belongs to. It uses ONLY the standardised RFC 2822 headers
that real mail clients populate:

  - In-Reply-To  — points at the immediate parent message's Message-ID.
  - References   — chain of all prior Message-IDs in the conversation.
  - Message-ID   — globally unique identifier for THIS message.

It does **NOT** match by subject. Subject-only matching is forbidden
because two unrelated conversations may share the subject "Re: Q3 update"
or "Fwd: budget" — merging them is a confidentiality breach.

Algorithm
---------

For an inbound message:

1. If `In-Reply-To` is set and we've seen that Message-ID before, return
   that message's thread_key. (Direct reply — same thread.)
2. Else, if any Message-ID in `References` matches one we've seen, return
   that thread's key. (Forwarded chain — same thread.)
3. Else, this message starts a new thread. Use its own Message-ID as the
   thread_key.

The "have we seen this Message-ID" lookup is provided by the caller
(typically a database query against `email_messages.message_id`). This
keeps the function pure and trivially testable.

Test in tests/email/test_thread_isolation.py — never relax the rule that
two messages with the same subject but disjoint Message-ID chains end up
in different threads.
"""
from __future__ import annotations

import re
from email.utils import parseaddr
from typing import Callable, Iterable, Optional


_MSGID_RE = re.compile(r"<([^>]+)>")


def _normalize_message_id(raw: Optional[str]) -> Optional[str]:
    """Extract the bare Message-ID, stripping <>, whitespace, RFC oddities.

    Returns None if the input is empty or doesn't look like a Message-ID.
    """
    if not raw:
        return None
    raw = raw.strip()
    m = _MSGID_RE.search(raw)
    if m:
        candidate = m.group(1).strip()
    else:
        candidate = raw.strip("<>").strip()
    # A valid Message-ID must contain '@' per RFC 2822.
    if "@" not in candidate:
        return None
    return candidate.lower()


def _extract_references(refs_header: Optional[str]) -> list[str]:
    """Parse a References header into a list of Message-IDs (without <>).

    Order is preserved (most-recent-first per RFC 2822 §3.6.4).
    """
    if not refs_header:
        return []
    out: list[str] = []
    for match in _MSGID_RE.finditer(refs_header):
        norm = _normalize_message_id(f"<{match.group(1)}>")
        if norm:
            out.append(norm)
    return out


def thread_key_for_message(
    headers: dict[str, str],
    *,
    lookup_thread: Callable[[str], Optional[str]],
) -> str:
    """Decide which thread_key a new incoming message belongs to.

    `headers` is a case-insensitive map of RFC 2822 headers (we expect at
    least Message-ID, In-Reply-To, References). The caller normalises
    casing.

    `lookup_thread(message_id)` returns the thread_key of a previously
    ingested message with that Message-ID, or None. Typically backed by
    `SELECT thread_id FROM email_messages WHERE message_id = :id`.

    Returns: the thread_key (a Message-ID) this message belongs to.

    NEVER falls back to subject matching. If neither In-Reply-To nor any
    Message-ID in References matches a previously-seen message, this
    starts a new thread keyed by its own Message-ID.

    Raises ValueError if the message has no Message-ID — can't track
    correspondence without one. Callers (the ingester) should generate a
    synthetic Message-ID at that point and log the irregularity.
    """
    # Case-insensitive header lookup
    lower = {k.lower(): v for k, v in headers.items()}

    own_id = _normalize_message_id(lower.get("message-id"))
    if not own_id:
        raise ValueError(
            "Message has no Message-ID header — cannot derive a thread key. "
            "Ingester should synthesise one before calling this function."
        )

    in_reply_to = _normalize_message_id(lower.get("in-reply-to"))
    references = _extract_references(lower.get("references"))

    # Step 1: direct reply (In-Reply-To)
    if in_reply_to:
        existing = lookup_thread(in_reply_to)
        if existing:
            return existing

    # Step 2: forwarded chain (any References match)
    for ref in references:
        existing = lookup_thread(ref)
        if existing:
            return existing

    # Step 3: new thread, keyed by this message's own ID
    return own_id
