"""Tests for premortem rule 5.9 — restricted domain enforcement.

These tests exist so any future engineer (or any future Claude session) who
tries to bypass the restriction sees a red CI immediately. Adding a domain to
RESTRICTED_DOMAINS is a one-way commitment; removing one requires a code
review with explicit justification.
"""
from __future__ import annotations

import pytest

from app.scrapers._restricted import (
    RESTRICTED_DOMAINS,
    RestrictedDomainError,
    enforce,
    is_restricted,
)


@pytest.mark.parametrize("url", [
    "https://www.bloomberg.com/news/articles/2026-05-04/oil-rises",
    "https://bloomberg.com/markets",
    "https://news.bloomberg.com/anything",
    "https://www.reuters.com/business/energy/whatever",
    "https://reuters.com/world/middle-east",
    "https://www.ft.com/content/abc",
    "https://kpler.com/insights/some-article",
    "https://www.platts.com/news/oil-and-gas",
    "https://x.com/some_handle/status/123",
    "https://twitter.com/some_handle",
    "https://www.linkedin.com/posts/whatever",
])
def test_restricted_urls_are_blocked(url):
    """Every URL on the restricted list raises RestrictedDomainError."""
    matched = is_restricted(url)
    assert matched is not None, f"{url} should have matched a restricted domain"
    with pytest.raises(RestrictedDomainError) as ex:
        enforce(url)
    assert ex.value.url == url
    assert ex.value.domain in RESTRICTED_DOMAINS


@pytest.mark.parametrize("url", [
    "https://example.com/article",
    "https://news.example.org/whatever",
    "https://api.openai.com/v1/messages",
    "https://developer.spglobal.com/apis/some-endpoint",  # API subdomain — allowed
    "https://developer.ice.com/kpler",                    # API subdomain — allowed
    "https://anthropic.com",
])
def test_unrestricted_urls_pass_through(url):
    """URLs not in the list don't raise."""
    assert is_restricted(url) is None
    enforce(url)  # should not raise


def test_subdomain_match():
    """News subdomains of restricted apex hit the apex match."""
    matched = is_restricted("https://research.bloomberg.com/whatever")
    assert matched == "bloomberg.com"


def test_developer_subdomain_explicitly_allowed():
    """The developer.spglobal.com path is the legitimate API; must not be blocked.

    This is critical — if RESTRICTED_DOMAINS ever accidentally lists
    `spglobal.com` in a way that matches the API subdomain, every legit data
    pull breaks. This test guards that.
    """
    enforce("https://developer.spglobal.com/apis/oil/v3/prices")
    enforce("https://developer.ice.com/kpler/v1/vessels")


def test_error_message_includes_reason():
    """Errors carry the human-readable reason so logs/CI failures point at the fix."""
    with pytest.raises(RestrictedDomainError) as ex:
        enforce("https://www.bloomberg.com/anything")
    assert "Bloomberg" in str(ex.value) or "bloomberg" in ex.value.reason
    assert "newsletter" in ex.value.reason.lower() or "license" in ex.value.reason.lower()


def test_empty_or_invalid_urls_dont_crash():
    """Bad URLs return None (not an error). Calling enforce() on them is a no-op."""
    assert is_restricted("") is None
    assert is_restricted("not a url") is None
    assert is_restricted("javascript:void(0)") is None
    enforce("")
    enforce("not a url")
