"""Tests for premortem rule 5.8 — thread stitching is RFC 2822 only.

These tests exist so two distinct conversations with similar (or identical)
subject lines NEVER get merged into one thread. Cross-thread contamination
is a confidentiality breach: replying inside the wrong thread can leak one
client's content to another.

The rule: matching is by Message-ID + In-Reply-To + References. Subject is
never a discriminator. If anyone reintroduces subject-based fallback,
these tests fail.
"""
from __future__ import annotations

from app.email._threading import (
    _extract_references,
    _normalize_message_id,
    thread_key_for_message,
)


# ─── _normalize_message_id ───────────────────────────────────────────────────


def test_normalize_strips_angle_brackets():
    assert _normalize_message_id("<abc@example.com>") == "abc@example.com"


def test_normalize_lowercases():
    assert _normalize_message_id("<ABC@EXAMPLE.COM>") == "abc@example.com"


def test_normalize_rejects_no_at_sign():
    assert _normalize_message_id("<no-at-sign>") is None


def test_normalize_handles_empty():
    assert _normalize_message_id(None) is None
    assert _normalize_message_id("") is None
    assert _normalize_message_id("   ") is None


# ─── _extract_references ─────────────────────────────────────────────────────


def test_references_parses_chain():
    refs = "<a@x.com> <b@y.com> <c@z.com>"
    assert _extract_references(refs) == ["a@x.com", "b@y.com", "c@z.com"]


def test_references_handles_whitespace_and_newlines():
    refs = "  <a@x.com>\n\t<b@y.com>  "
    assert _extract_references(refs) == ["a@x.com", "b@y.com"]


def test_references_empty():
    assert _extract_references(None) == []
    assert _extract_references("") == []


# ─── thread_key_for_message — the headline rule ──────────────────────────────


class FakeLookup:
    """Pretends to be `SELECT thread_id FROM email_messages WHERE message_id = :id`.

    Construct with a dict mapping seen Message-IDs to their thread_keys.
    """

    def __init__(self, seen: dict[str, str]):
        self.seen = {k.lower(): v for k, v in seen.items()}
        self.calls: list[str] = []

    def __call__(self, message_id: str):
        self.calls.append(message_id)
        return self.seen.get(message_id.lower())


def test_in_reply_to_takes_us_to_existing_thread():
    """The most common case — direct reply — uses In-Reply-To header."""
    lookup = FakeLookup({"original@gia.com": "thread-A"})
    headers = {
        "Message-ID": "<reply@external.com>",
        "In-Reply-To": "<original@gia.com>",
        "References": "<original@gia.com>",
        "Subject": "Re: Q3 numbers",
    }
    assert thread_key_for_message(headers, lookup_thread=lookup) == "thread-A"


def test_references_chain_finds_thread_when_in_reply_to_unknown():
    """Forwarded chains may not have In-Reply-To matching, but References will."""
    lookup = FakeLookup({"first@gia.com": "thread-original"})
    headers = {
        "Message-ID": "<reply2@external.com>",
        "In-Reply-To": "<reply1@external.com>",  # we haven't seen this one
        "References": "<first@gia.com> <reply1@external.com>",
        "Subject": "Re: Q3 numbers",
    }
    assert thread_key_for_message(headers, lookup_thread=lookup) == "thread-original"


def test_unknown_chain_starts_new_thread():
    """No matching In-Reply-To, no matching Reference → fresh thread."""
    lookup = FakeLookup({})
    headers = {
        "Message-ID": "<brand-new@somewhere.com>",
        "In-Reply-To": "<unrelated@elsewhere.com>",
        "References": "<also-unrelated@nope.com>",
        "Subject": "Q3 update",
    }
    assert thread_key_for_message(headers, lookup_thread=lookup) == "brand-new@somewhere.com"


# ─── THE INVARIANT: same subject != same thread (rule 5.8) ──────────────────


def test_two_unrelated_conversations_with_same_subject_stay_separate():
    """If a future engineer adds subject-based matching, this test fails.

    Scenario: Client A (account-a@partner.com) and Client B (account-b@vendor.com)
    both happen to email Marwan with the subject "Re: Q3 update". They are
    completely unrelated — different Message-IDs, no overlap in References.
    They must end up in DIFFERENT threads.
    """
    # Pretend we've seen Client A's first message before, in thread-A
    lookup = FakeLookup({"clienta-orig@partner.com": "thread-A"})

    msg_from_client_a = {
        "Message-ID": "<clienta-reply@partner.com>",
        "In-Reply-To": "<clienta-orig@partner.com>",
        "References": "<clienta-orig@partner.com>",
        "Subject": "Re: Q3 update",
    }
    msg_from_client_b = {
        "Message-ID": "<clientb-orig@vendor.com>",
        "In-Reply-To": None,
        "References": None,
        "Subject": "Re: Q3 update",  # SAME subject, totally different conversation
    }

    key_a = thread_key_for_message(msg_from_client_a, lookup_thread=lookup)
    key_b = thread_key_for_message(msg_from_client_b, lookup_thread=lookup)

    assert key_a == "thread-A"
    assert key_b == "clientb-orig@vendor.com"
    assert key_a != key_b, (
        "Rule 5.8 violation: two unrelated conversations with the same subject "
        "must NOT collapse into one thread. Subject-based matching is forbidden."
    )


def test_three_separate_conversations_same_subject_stay_separate():
    """The same property holds at scale — N unrelated 'Re: Q3 update' threads
    stay as N distinct threads, never merged."""
    lookup = FakeLookup({})

    msgs = [
        {
            "Message-ID": f"<msg-{i}@source-{i}.com>",
            "In-Reply-To": None,
            "References": None,
            "Subject": "Re: Q3 update",
        }
        for i in range(3)
    ]
    keys = [thread_key_for_message(m, lookup_thread=lookup) for m in msgs]
    assert len(set(keys)) == 3, f"Expected 3 distinct threads, got {keys}"


def test_no_message_id_raises_value_error():
    """Message without a Message-ID is malformed; the ingester must handle
    this explicitly (synthesise one) rather than silently merging."""
    lookup = FakeLookup({})
    headers = {
        "Subject": "Re: Q3 update",
        "From": "rogue@nomailheader.com",
        # Note: no Message-ID
    }
    try:
        thread_key_for_message(headers, lookup_thread=lookup)
    except ValueError as e:
        assert "Message-ID" in str(e)
    else:
        raise AssertionError("Expected ValueError for missing Message-ID")


def test_lookup_called_for_in_reply_to_first_then_references():
    """We probe In-Reply-To before References — In-Reply-To is the most-likely
    immediate parent, so we save lookups in the common case."""
    lookup = FakeLookup({"x@y.com": "t-1"})
    headers = {
        "Message-ID": "<new@z.com>",
        "In-Reply-To": "<x@y.com>",
        "References": "<irrelevant@a.com> <x@y.com>",
        "Subject": "Anything",
    }
    thread_key_for_message(headers, lookup_thread=lookup)
    assert lookup.calls[0] == "x@y.com"  # In-Reply-To probed first
    # And once we got a hit, we stop — no need to also probe References
    assert lookup.calls == ["x@y.com"]
