from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis as redis_client
import logging

from app.config import get_settings
from app.db.session import db_health, get_db
from sqlalchemy import text
from app import scheduler as rr_scheduler
from app.auth import current_user
from app.api.schemas import HealthOut, MeOut

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RR Command Center starting up...")
    try:
        rr_scheduler.start()
    except Exception:
        logger.exception("Scheduler failed to start; continuing without background jobs")
    yield
    logger.info("RR Command Center shutting down...")
    rr_scheduler.shutdown()


app = FastAPI(
    title="RR Command Center API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000",
                   "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# /health is intentionally unauthenticated so cloud uptime probes can hit it.
@app.get("/health", response_model=HealthOut)
def health():
    db_ok = db_health()
    try:
        r = redis_client.from_url(settings.redis_url)
        r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "auth_enabled": bool(settings.ms_tenant_id and settings.ms_client_id),
    }


# Echoes the authenticated principal — frontend uses this to confirm session
# and discover the workspaces (companies) they belong to.
@app.get("/api/me", response_model=MeOut)
def me(user: dict = Depends(current_user)):
    email = (user.get("preferred_username") or user.get("email") or "").lower()
    workspaces = []
    try:
        with get_db() as db:
            # Dev-mode principal sees ALL workspaces; real users see their memberships.
            if user.get("_dev_mode"):
                rows = db.execute(text("""
                    SELECT * FROM workspaces
                    WHERE archived_at IS NULL
                    ORDER BY display_name ASC
                """)).mappings().all()
            else:
                rows = db.execute(text("""
                    SELECT w.*
                    FROM workspaces w
                    JOIN workspace_members m ON m.workspace_id = w.id
                    WHERE w.archived_at IS NULL
                      AND LOWER(m.email) = :email
                    ORDER BY w.display_name ASC
                """), {"email": email}).mappings().all()
            workspaces = [dict(r) for r in rows]
    except Exception:
        # If the workspaces table doesn't exist yet (alembic not run), return empty.
        # The frontend handles empty workspaces gracefully.
        workspaces = []

    return {
        "sub": user.get("sub"),
        "name": user.get("name"),
        "email": email or None,
        "roles": user.get("roles", []),
        "dev_mode": bool(user.get("_dev_mode")),
        "workspaces": workspaces,
    }


# API routes — every router mounted here is auth-protected via Depends(current_user).
# /health and /api/me above are explicit (me is auth-protected; health is not).
from app.api import (
    entities, projects, tasks, email, briefing, feed, search, admin,
    workspaces, costs, telemetry, feedback,
)

_auth = [Depends(current_user)]

# Order: workspaces first (everything else queries workspace context),
# then briefing (most-traffic), then the rest.
app.include_router(workspaces.router, prefix="/api", dependencies=_auth)
app.include_router(briefing.router,   prefix="/api", dependencies=_auth)
app.include_router(feedback.router,   prefix="/api", dependencies=_auth)
app.include_router(costs.router,      prefix="/api", dependencies=_auth)
app.include_router(telemetry.router,  prefix="/api", dependencies=_auth)
app.include_router(entities.router,   prefix="/api", dependencies=_auth)
app.include_router(projects.router,   prefix="/api", dependencies=_auth)
app.include_router(tasks.router,      prefix="/api", dependencies=_auth)
app.include_router(email.router,      prefix="/api", dependencies=_auth)
app.include_router(feed.router,       prefix="/api", dependencies=_auth)
app.include_router(search.router,     prefix="/api", dependencies=_auth)
app.include_router(admin.router,      prefix="/api", dependencies=_auth)
