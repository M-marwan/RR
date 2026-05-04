"""RESTRICTED_DOMAINS enforcement (premortem rule 5.9).

A frozen set of domains that the system **must not** scrape via Playwright,
requests, or any HTTP fetch. Each domain on this list is here because
either:

- the publisher's Terms of Service explicitly prohibit automated access
  (e.g., Bloomberg ToS Section A.3 quoted in our 2026-05-03 market validation
  research), or
- a paid licensed feed exists and is the only legitimate access path.

If you genuinely need data from one of these sources, the answer is one of:
  1. Subscribe to that publisher's email newsletter and ingest it via M365.
  2. Buy a licensed data feed (Bloomberg Data License, LSEG/Reuters RDP,
     Kpler API via ICE, S&P Global at developer.spglobal.com).
  3. Find a public alternative.

The connector layer enforces this hard. Adding a domain here is a one-way
decision — never silently bypass.

Usage
-----
    from app.scrapers._restricted import enforce, is_restricted, RestrictedDomainError

    enforce("https://www.bloomberg.com/news/articles/...")  # raises
    if is_restricted(url):
        ...
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse


class RestrictedDomainError(RuntimeError):
    """Raised when scraping/fetching a restricted domain is attempted."""

    def __init__(self, domain: str, url: str, reason: str):
        self.domain = domain
        self.url = url
        self.reason = reason
        super().__init__(
            f"Refused to fetch {url!r}: {domain} is on RESTRICTED_DOMAINS "
            f"({reason}). See app/scrapers/_restricted.py for the legitimate path."
        )


# Each entry: domain → reason. The reason is the single sentence we show
# to the operator if they hit this error in logs / CI.
RESTRICTED_DOMAINS: dict[str, str] = {
    # News + financial data — ToS prohibits automated access
    "bloomberg.com":          "Bloomberg ToS Section A.3 prohibits scrapers/bots; use newsletter ingestion or Data License.",
    "www.bloomberg.com":      "Bloomberg ToS Section A.3 prohibits scrapers/bots; use newsletter ingestion or Data License.",
    "reuters.com":            "Reuters ToS prohibits automated retrieval; use Refinitiv RDP API (developers.lseg.com).",
    "www.reuters.com":        "Reuters ToS prohibits automated retrieval; use Refinitiv RDP API (developers.lseg.com).",
    "wsj.com":                "Dow Jones / WSJ ToS prohibits scraping; use Factiva licensed feed.",
    "www.wsj.com":            "Dow Jones / WSJ ToS prohibits scraping; use Factiva licensed feed.",
    "ft.com":                 "FT ToS prohibits automated retrieval; subscribe to email alerts and ingest via M365.",
    "www.ft.com":             "FT ToS prohibits automated retrieval; subscribe to email alerts and ingest via M365.",
    "nytimes.com":            "NYT ToS prohibits automated access; use API for licensed content if available.",
    "www.nytimes.com":        "NYT ToS prohibits automated access; use API for licensed content if available.",
    "economist.com":          "Economist ToS prohibits scrapers; subscribe to email digests and ingest via M365.",
    "www.economist.com":      "Economist ToS prohibits scrapers; subscribe to email digests and ingest via M365.",

    # Commodity portals — official APIs exist; never scrape
    "kpler.com":              "Kpler API available via ICE Developer Portal (developer.ice.com); no scraping.",
    "www.kpler.com":          "Kpler API available via ICE Developer Portal (developer.ice.com); no scraping.",
    "platts.com":             "S&P Global Platts API at developer.spglobal.com; no scraping.",
    "www.platts.com":         "S&P Global Platts API at developer.spglobal.com; no scraping.",
    "spglobal.com":           "S&P Global API at developer.spglobal.com; no scraping the marketing site.",
    "www.spglobal.com":       "S&P Global API at developer.spglobal.com; no scraping the marketing site.",

    # Social platforms — covered by their own APIs / explicit ToS
    "linkedin.com":           "LinkedIn ToS prohibits scraping; use official LinkedIn API where available.",
    "www.linkedin.com":       "LinkedIn ToS prohibits scraping; use official LinkedIn API where available.",
    "x.com":                  "X / Twitter ToS prohibits scraping; use API v2 (already in our deps via tweepy).",
    "twitter.com":            "X / Twitter ToS prohibits scraping; use API v2 (already in our deps via tweepy).",
}


def _domain_of(url: str) -> str:
    """Extract the lower-cased registrable host of a URL."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().strip()
        return host
    except Exception:
        return ""


def is_restricted(url: str) -> Optional[str]:
    """Return the matching domain (with reason) if the URL is restricted, else None.

    Matches both exact host and any host whose registrable suffix is in the
    list. e.g. `news.bloomberg.com` matches `bloomberg.com`.
    """
    host = _domain_of(url)
    if not host:
        return None
    if host in RESTRICTED_DOMAINS:
        return host
    # Also match subdomains: any.X.bloomberg.com → bloomberg.com
    parts = host.split(".")
    for i in range(1, len(parts)):
        candidate = ".".join(parts[i:])
        if candidate in RESTRICTED_DOMAINS:
            return candidate
    return None


def enforce(url: str) -> None:
    """Raise RestrictedDomainError if the URL targets a restricted domain.

    Connectors **must** call this before any HTTP fetch. CI test in
    tests/scrapers/test_restricted.py asserts the enforcement.
    """
    matched = is_restricted(url)
    if matched:
        raise RestrictedDomainError(
            domain=matched,
            url=url,
            reason=RESTRICTED_DOMAINS[matched],
        )
