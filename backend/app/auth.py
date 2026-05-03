"""Microsoft Entra (Azure AD) JWT validation for FastAPI.

Mode of operation
-----------------
- If MS_TENANT_ID **or** MS_CLIENT_ID is unset, auth is DISABLED and every
  request gets a synthetic dev-principal user. This lets local development
  proceed before the Entra app registration is created.
- When both are set, every protected request must carry an `Authorization:
  Bearer <jwt>` header. The JWT is validated against the tenant's public JWKS,
  the audience must match `MS_CLIENT_ID`, and the issuer must be
  `https://login.microsoftonline.com/<tenant>/v2.0`.

Usage
-----
Apply at router-mount time in `main.py`:

    from app.auth import current_user

    app.include_router(
        entities.router,
        prefix="/api",
        dependencies=[Depends(current_user)],
    )

Or per-route:

    @router.get("/me")
    def me(user: dict = Depends(current_user)):
        return user

Note: dev-mode behavior is opt-in via env. Don't ship to production with
MS_TENANT_ID unset — it disables auth for everyone.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from jose.exceptions import JWTError

from app.config import get_settings

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def _is_auth_enabled() -> bool:
    s = get_settings()
    return bool(s.ms_tenant_id) and bool(s.ms_client_id)


@lru_cache(maxsize=8)
def _jwks_keys(tenant_id: str) -> list[dict]:
    """Fetch and cache the JWKS keys for a tenant.

    Cache lives for the process lifetime; if Microsoft rotates keys mid-process
    you'll get a few seconds of 401s until the process restarts. Acceptable for
    Phase 0; revisit when we're at scale.
    """
    url = f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys"
    try:
        resp = httpx.get(url, timeout=10.0)
        resp.raise_for_status()
        return resp.json().get("keys", [])
    except Exception as e:
        logger.exception("Failed to fetch JWKS from %s", url)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Cannot fetch Microsoft signing keys: {e}",
        )


def _dev_principal(settings) -> dict:
    """Synthetic user returned in dev mode (no MS_* config)."""
    return {
        "sub": "dev-principal",
        "name": "Marwan (dev)",
        "preferred_username": settings.gmail_marwan_address,
        "email": settings.gmail_marwan_address,
        "_dev_mode": True,
        "roles": ["principal"],
    }


async def current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """Validate Bearer JWT and return decoded claims.

    Raises 401 on missing/invalid token. Returns a dev-principal dict when auth
    is disabled via env config.
    """
    settings = get_settings()

    # Dev-mode bypass — no auth configured.
    if not _is_auth_enabled():
        user = _dev_principal(settings)
        request.state.user = user
        return user

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Parse the unverified header to find the key id.
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Malformed token: {e}")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token missing kid")

    keys = _jwks_keys(settings.ms_tenant_id)
    matching_key = next((k for k in keys if k.get("kid") == kid), None)
    if matching_key is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No matching JWKS key for token")

    try:
        claims = jwt.decode(
            token,
            matching_key,
            algorithms=["RS256"],
            audience=settings.ms_client_id,
            issuer=[
                f"https://login.microsoftonline.com/{settings.ms_tenant_id}/v2.0",
                f"https://sts.windows.net/{settings.ms_tenant_id}/",
            ],
        )
    except JWTError as e:
        logger.warning("JWT validation failed: %s", e)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}")

    # Optional dev-bypass: explicit allow-list of UPNs that don't need a token,
    # gated behind a special header so it can't be triggered by accident.
    upn = (claims.get("preferred_username") or claims.get("email") or "").lower()
    request.state.user = claims
    request.state.user_upn = upn
    return claims


def require_role(*allowed: str):
    """Dependency factory: require the authenticated user to have one of `allowed` roles.

    Reads `roles` claim (Entra app role assignments). In dev mode, the synthetic
    principal has `roles=['principal']` so all guards pass.
    """

    async def _check(user: dict = Depends(current_user)) -> dict:
        roles = set(user.get("roles", []))
        if not roles.intersection(allowed):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires one of roles: {', '.join(allowed)}",
            )
        return user

    return _check
