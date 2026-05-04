"""Microsoft Graph connector — admin-grant OAuth (premortem rules 5.6, 5.7).

Each company has its own M365 tenant (multi-tenant resolved 2026-05-04). For
every workspace, we register a separate Entra ID app inside the company's
tenant; the company's Global Admin grants `Mail.Read` (Application permission)
to that app once. From then on we authenticate via client_credentials, fetch
mailboxes via Graph delta query, and receive change notifications via webhook.

Activation gates (from architecture §5):
  - 5.5  categorizer_test_passed_at must be set on the workspace before
         the connector ingests any mail.
  - 5.6  aup_signed_at must be set; M365 connector refuses to ingest mail
         from any workspace without an Acceptable Use Policy on file.
  - 5.7  email_threads.monitoring_excluded is respected at ingestion
         (not just display) — excluded threads are never indexed.
  - 5.10 workspace must have ≥2 principal members before activation.

This module provides the **client primitives** (token acquisition, message
fetch, subscription management). The **ingestion worker** that uses these
primitives lives in app/workers/m365_ingest.py (built once a real tenant is
onboarded). The **webhook receiver** lives in app/connectors/m365_webhook.py.

Required workspace columns:
    workspaces.m365_tenant_id      Azure tenant GUID
    workspaces.m365_app_id         Entra app (client) ID
    workspaces.m365_consent_granted_at
    workspaces.aup_signed_at        (rule 5.6 gate)
    workspaces.categorizer_test_passed_at  (rule 5.5 gate)

The client secret is **never** stored in the workspaces table. It lives in
the OS keyring / vault, addressed by `m365:{workspace_id}` keys. The
onboarding script (scripts/onboard_workspace.py) handles secret entry.

Required pyproject deps (installed via `pip install -e .`):
    msal>=1.30.0
    httpx>=0.27.0   (already present)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
import msal
from sqlalchemy import text

from app.db.session import get_db

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


class M365Error(RuntimeError):
    pass


class WorkspaceNotActivated(M365Error):
    """Raised when an M365 operation is attempted on a workspace that hasn't
    cleared all activation gates (rules 5.5, 5.6, 5.10)."""


@dataclass
class WorkspaceM365Config:
    workspace_id: str
    tenant_id: str
    client_id: str
    client_secret: str  # never logged
    consent_granted_at: Optional[datetime]


def _secret_env_key(workspace_id: str) -> str:
    """Env var name where this workspace's M365 client secret is held in dev.

    Production should pull from a real vault. The onboarding script writes
    the env var name into the workspaces row so that's discoverable. We do
    NOT store the secret value in Postgres.
    """
    return f"M365_SECRET_{workspace_id.replace('-', '_').upper()}"


def load_workspace_config(workspace_id: str) -> WorkspaceM365Config:
    """Read tenant/app config from Postgres + secret from env (dev) or vault."""
    with get_db() as db:
        row = db.execute(text("""
            SELECT id, m365_tenant_id, m365_app_id, m365_consent_granted_at,
                   aup_signed_at, categorizer_test_passed_at, archived_at
            FROM workspaces
            WHERE id = :wid
        """), {"wid": workspace_id}).mappings().first()

    if not row:
        raise M365Error(f"Workspace {workspace_id} not found")
    if row["archived_at"]:
        raise M365Error(f"Workspace {workspace_id} is archived")
    if not row["m365_tenant_id"] or not row["m365_app_id"]:
        raise WorkspaceNotActivated(
            f"Workspace {workspace_id} has no M365 tenant/app yet. "
            f"Run scripts/onboard_workspace.py first."
        )
    if not row["m365_consent_granted_at"]:
        raise WorkspaceNotActivated(
            f"Workspace {workspace_id} M365 admin consent not granted. "
            f"Visit the consent URL printed by scripts/onboard_workspace.py."
        )
    if not row["aup_signed_at"]:
        raise WorkspaceNotActivated(
            f"Workspace {workspace_id} has no AUP on file (rule 5.6). "
            f"See docs/legal/AUP_TEMPLATE.md and complete legal review first."
        )
    # Note: rule 5.5 (categorizer_test) is enforced at ingest time, not at
    # token acquisition time — we let onboarding fetch a few sample messages
    # so the test corpus can be built.

    secret = os.getenv(_secret_env_key(workspace_id), "").strip()
    if not secret:
        raise WorkspaceNotActivated(
            f"Workspace {workspace_id} client secret missing. "
            f"Set env var {_secret_env_key(workspace_id)} (or vault pointer)."
        )

    return WorkspaceM365Config(
        workspace_id=str(row["id"]),
        tenant_id=str(row["m365_tenant_id"]),
        client_id=str(row["m365_app_id"]),
        client_secret=secret,
        consent_granted_at=row["m365_consent_granted_at"],
    )


# ─── Token acquisition (msal client_credentials) ─────────────────────────────


_token_cache: dict[str, tuple[str, datetime]] = {}


def _acquire_token(cfg: WorkspaceM365Config) -> str:
    """Get a Graph API access token via client_credentials flow.

    Cached per-workspace for the token's lifetime (typically ~1 hour).
    """
    cached = _token_cache.get(cfg.workspace_id)
    if cached:
        token, expires = cached
        if expires - datetime.utcnow() > timedelta(minutes=5):
            return token

    authority = f"https://login.microsoftonline.com/{cfg.tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=cfg.client_id,
        client_credential=cfg.client_secret,
        authority=authority,
    )
    result = app.acquire_token_for_client(scopes=GRAPH_SCOPES)
    if "access_token" not in result:
        raise M365Error(
            f"Token acquisition failed for workspace {cfg.workspace_id}: "
            f"{result.get('error_description', result.get('error', 'unknown'))}"
        )

    expires_in = int(result.get("expires_in", 3600))
    _token_cache[cfg.workspace_id] = (
        result["access_token"],
        datetime.utcnow() + timedelta(seconds=expires_in),
    )
    return result["access_token"]


# ─── Graph client ────────────────────────────────────────────────────────────


class GraphClient:
    """Thin wrapper around Microsoft Graph for one workspace.

    Auto-handles token refresh, basic retry on transient 429/503, and JSON
    response parsing. Does NOT do paging across @odata.nextLink — callers do
    that explicitly so they can stream/cancel.
    """

    def __init__(self, cfg: WorkspaceM365Config):
        self.cfg = cfg
        self._client = httpx.Client(timeout=30.0)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {_acquire_token(self.cfg)}",
            "Accept": "application/json",
        }

    def get(self, path: str, **params: Any) -> dict:
        url = f"{GRAPH_BASE}{path}" if path.startswith("/") else path
        resp = self._client.get(url, headers=self._headers(), params=params)
        if resp.status_code in (429, 503):
            # Retry-After is the documented backoff signal for Graph throttling.
            retry_after = int(resp.headers.get("Retry-After", "5"))
            logger.warning("Graph throttled; sleeping %ds", retry_after)
            import time
            time.sleep(retry_after)
            resp = self._client.get(url, headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, body: dict) -> dict:
        url = f"{GRAPH_BASE}{path}" if path.startswith("/") else path
        resp = self._client.post(url, headers={
            **self._headers(),
            "Content-Type": "application/json",
        }, json=body)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def delete(self, path: str) -> None:
        url = f"{GRAPH_BASE}{path}" if path.startswith("/") else path
        resp = self._client.delete(url, headers=self._headers())
        if resp.status_code not in (204, 404):
            resp.raise_for_status()

    # ─── high-level helpers (used by ingest worker) ──────────────────────

    def list_users(self, page_size: int = 100) -> list[dict]:
        """Enumerate users in the tenant. Subject to Exchange Online RBAC scoping."""
        return self.get("/users", **{"$top": page_size}).get("value", [])

    def list_messages(self, user_id: str, top: int = 50) -> dict:
        """Fetch the most-recent N messages for one mailbox (initial backfill)."""
        return self.get(
            f"/users/{user_id}/messages",
            **{
                "$top": top,
                "$select": "id,subject,from,toRecipients,sentDateTime,receivedDateTime,bodyPreview,internetMessageId,conversationId,parentFolderId",
                "$orderby": "receivedDateTime desc",
            },
        )

    def get_delta(self, user_id: str, delta_link: Optional[str] = None) -> dict:
        """Delta query — returns messages changed since the last delta token.

        On first call, pass delta_link=None; the response contains an
        `@odata.deltaLink` to use next time. Persist that delta_link in the
        per-mailbox state so we can resume.
        """
        if delta_link:
            return self.get(delta_link)
        return self.get(f"/users/{user_id}/mailFolders/inbox/messages/delta")

    def create_subscription(
        self,
        user_id: str,
        notification_url: str,
        client_state: str,
        expiration_minutes: int = 4230,  # ~70.5h, max for messages is 4230
    ) -> dict:
        """Create a change-notification webhook for one mailbox.

        See https://learn.microsoft.com/en-us/graph/change-notifications-overview
        Max lifetime for /messages is 4230 minutes — caller must renew.
        """
        return self.post("/subscriptions", {
            "changeType": "created,updated",
            "notificationUrl": notification_url,
            "resource": f"/users/{user_id}/mailFolders/inbox/messages",
            "expirationDateTime": (
                datetime.utcnow() + timedelta(minutes=expiration_minutes)
            ).isoformat() + "Z",
            "clientState": client_state,
        })

    def delete_subscription(self, subscription_id: str) -> None:
        self.delete(f"/subscriptions/{subscription_id}")

    def close(self) -> None:
        self._client.close()


def client_for_workspace(workspace_id: str) -> GraphClient:
    """Convenience factory — load config and return a GraphClient."""
    return GraphClient(load_workspace_config(workspace_id))
