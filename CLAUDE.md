# RR Command Center — Claude Code project guide

This file is auto-loaded when Claude Code (or any Ruflo agent) opens this folder.
It exists so future sessions don't re-discover the project from scratch.

## What this is

Personal executive intelligence + operations dashboard for **Marwan** (014.marwan@gmail.com), with an AI chief-of-staff persona named **Raymond**. Aggregates Gmail (2 accounts), Twitter, Brave Search, and Playwright-driven paid portals (Kpler, Platts, Bloomberg, S&P Global) into a single command center timed to Asia/Dubai. Migrating from a prior markdown-based "RR" system at `.claude/RR/RR/` via `backend/scripts/seed_from_rr.py`.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14 App Router, React 18, TypeScript 5, Tailwind, Radix UI, maplibre-gl, recharts, swr, zustand, dnd-kit |
| Backend | FastAPI 0.115, SQLAlchemy 2 (sync), asyncpg (in deps, currently unused), pgvector, alembic (installed, not configured), Redis, apscheduler |
| Integrations | Gmail API, Tweepy, Brave Search, Playwright, fastembed (local), pdfminer, Claude CLI (subprocess) |
| Data | PostgreSQL + Redis via docker-compose (ports 5433, 6380 — non-default to avoid host conflicts) |

## Frontend layout — 14 dashboard "rooms"

Default landing is `/morning`. Routes live in `frontend/app/(dashboard)/<room>/page.tsx`.

| Room | Purpose | Status |
|------|---------|--------|
| `/morning` | Raymond's morning dispatch + Three Moves + Open Loops + Watchlist + Capital | UI built, **data is hardcoded seed** |
| `/war-room` | Kanban task board | Built |
| `/intelligence` | Hidden-truth synthesis | Built |
| `/comms` | Drag-drop email thread canvas | Built |
| `/wire` | Real-time intel feed (SSE + polling) | Built (SSE cleanup leak) |
| `/vault` | Ventures grid | Built |
| `/rolodex` | People grid | Built |
| `/blacklist` | Searchable entity dossier | Built |
| `/concierge` | Deal pipeline | Partial — no drill-down |
| `/ledger` | Capital summary | Partial — deployable hardcoded |
| `/library` | Sector intel | Partial — no defensive null checks |
| `/team` | Team list + delegations + open asks | Partial — only people list rendered |
| `/map` | Geographic intel | Stub — "Phase 2" placeholder |
| `/settings/accounts` | Account settings | **Missing — 404** |

Theme tokens are in `frontend/app/globals.css`: `--rr-obsidian` (bg), `--rr-charcoal`, `--rr-brass` (accent), `--rr-cream`, `--rr-urgent`, `--rr-ok`, `--rr-warn`, plus `.rr-card`, `.rr-heading`, `.rr-mono` classes.

Header includes hardcoded `#ticker-brent` and `#ticker-dxy` placeholders (no live feed).

## Backend layout

```
backend/app/
├── main.py            FastAPI entry, CORS (localhost only), /health, scheduler lifecycle
├── config.py          Settings dataclass, .env loaded via python-dotenv
├── scheduler.py       APScheduler — 4 background jobs
├── api/               8 routers: entities, projects, tasks, email, briefing, feed, search, admin
├── workers/           email_ingest, email_categorize, email_sender
├── email/             gmail_client, contact_resolver, thread_stitcher
├── ai/                claude.py (subprocess) + prompts/{email_categorize.md, system_context.md}
├── db/                schema.sql (548 lines), session.py, db_health()
├── enrichment/        EMPTY STUB
├── ingestion/         EMPTY STUB
├── scrapers/          EMPTY STUB
└── social/            EMPTY STUB
```

API mount prefix: `/api`. All endpoints listed in `app/main.py:61-70`.

## Scheduler jobs (APScheduler in-process)

| Job | Cadence | Function |
|-----|---------|----------|
| `email_ingest` | 5 min | `app.workers.email_ingest.run_all` — pulls Gmail messages from both accounts |
| `email_categorize` | 10 min | `app.workers.email_categorize.categorize_batch` — Claude CLI classifies, extracts tasks |
| `email_sender` | 2 min | `app.workers.email_sender.send_approved` — sends drafts marked `approved` |
| `open_loop_sweep` | hourly | `app.email.thread_stitcher.recompute_all_open_loops` — flags `>48h` waiting |

## Database schema highlights

Schema lives in `backend/app/db/schema.sql` (loaded once via Docker entrypoint at `001_schema.sql`). 15 core tables baseline, 7 with `vector(384)` columns and HNSW indexes. Alembic migrations layer on top of that baseline.

**Baseline (schema.sql):**
- **Entity graph**: `entities`, `sources`, `documents`, `claims`, `events`, `relationships`
- **Email**: `email_accounts`, `contacts`, `email_messages` (24 cols incl. Claude classification), `email_threads`, `email_attachments`
- **Work**: `projects`, `tasks`, `outbound_queue`
- **Intel ingestion**: `newsletter_sources`, `social_monitors`, `intel_project_matches`
- **Synthesis & metrics**: `synthesis_cache`, `claude_usage`, `economic_indicators`, `commodity_prices`

**Migration 0002** — added 3 hot-path indexes.

**Migration 0003 (Phase 1A.1)** — multi-tenant tables:
- `workspaces` — one per company (slug, display_name, industry, primary_color, M365 binding fields, archived_at soft delete)
- `workspace_members` — entity ↔ workspace with role (`principal` / `exec` / `operator` / `readonly`)
- `audit_log` — every mutation, for UAE PDPL / DIFC compliance
- Added nullable `workspace_id` FK to `projects`, `tasks`, `email_messages`, `email_threads`, `outbound_queue`

Hypertables (TimescaleDB-style): `claude_usage`, `economic_indicators`, `commodity_prices`.

**Missing tables** (Phase 1A.2 — next):
- `briefing_synthesis` (Raymond's daily dispatch + Three Moves)
- `open_loops` (person + days_waiting)
- `capital_position` (deployable / committed / pipeline)
- `watchlist` (string array per day)

## Local dev commands

```powershell
# 1. Bring up Postgres + Redis
cd "C:\Users\HELIOS\OneDrive - giavc.com\Desktop\Claude\rr-command-center"
docker-compose up -d

# 2. Backend (Python 3.11+, FastAPI)
cd backend
.\.venv\Scripts\activate
pip install -e .                            # ensure new deps (python-jose) are installed
alembic stamp 0001                          # ONE TIME on existing DBs created from schema.sql
alembic upgrade head                        # apply 0002+ index migrations
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Frontend (Node 22, Next.js)
cd frontend
npm run dev   # http://localhost:3000

# 4. One-time setup
python backend\scripts\gmail_auth.py        # OAuth dance — needs Google Cloud creds in .env first
python backend\scripts\seed_from_rr.py      # Loads markdown dossiers from RR_SOURCE_PATH

# 5. Health check
curl http://localhost:8000/health           # {status, db, redis, auth_enabled}
curl http://localhost:8000/api/me           # in dev mode, returns synthetic principal
```

## Auth modes

- **Dev mode** (default): `MS_TENANT_ID` and/or `MS_CLIENT_ID` empty in `.env`. Every request gets a synthetic `_dev_mode: true` principal. Use this until the Entra app is registered.
- **Prod mode**: both env vars set. Frontend must obtain a token (MSAL.js — wired up in Phase 1B) and pass `Authorization: Bearer <jwt>`. Backend validates against `https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys`.

## Known issues — see audit at `~/.claude` Ruflo memory key `rr-audit-2026-05-03`

### 🔴 Must fix
1. `.env` contains real Gmail OAuth Client ID + Secret — rotate them and treat them as compromised. `.env` is in `.gitignore` but project isn't in git yet anyway.
2. Project is **not under version control**. No `.git/` folder. Init git + push to private remote before any further work.
3. ~~Backend has zero authentication.~~ ✅ **Fixed in Phase 0** — `app/auth.py` validates Microsoft Entra JWTs against the tenant JWKS. Set `MS_TENANT_ID` + `MS_CLIENT_ID` in `.env` to enable; leave empty for dev-mode bypass with synthetic principal.
4. Morning briefing returns **hardcoded seed JSON** — no real data layer behind it yet. (Phase 1A.)
5. ~~No alembic migrations live.~~ ✅ **Fixed in Phase 0** — `alembic.ini` + `migrations/env.py` + baseline `0001` + `0002_phase0_indexes` written. Run `cd backend && alembic stamp 0001 && alembic upgrade head` once.

### 🟠 Important
6. ~~`frontend/lib/` is empty.~~ ✅ **Fixed in Phase 0** — `frontend/lib/api.ts` provides `api.get/post/patch/delete/stream` plus SWR-compatible `apiFetcher`. All new pages should use it.
7. ~~No React error boundaries.~~ ✅ **Fixed in Phase 0** — `components/layout/ErrorBoundary.tsx` wraps `<main>` in dashboard layout.
8. ~~`wire/page.tsx` SSE leak.~~ ✅ **Fixed in Phase 0** — uses `api.stream` with proper `close()` on unmount + error fallback to polling.
9. Sync SQLAlchemy in async FastAPI — works via thread pool, wastes the asyncpg dep. (Phase 2 cleanup.)
10. ~~Routes return raw dict(r).~~ ✅ **Partially fixed in Phase 0** — `app/api/schemas.py` defines `EntityOut`, `TaskOut`, `BriefingOut`, `MeOut`, `HealthOut`, etc. Applied via `response_model=` on entities, tasks, briefing, /health, /api/me. Remaining (projects, email, feed, search, admin) deferred to follow-up.
11. ~~Missing indexes.~~ ✅ **Fixed in Phase 0** — see migration `0002_phase0_indexes.py`. Run `alembic upgrade head` to apply.

### 🟡 Polish
12. Hardcoded values: ledger deployable, header tickers (BRENT/DXY).
13. Empty Concierge / Library / Team drill-downs.
14. **No tests anywhere** — 0 of 45 source files covered.
15. **No CI/CD** — no `.github/workflows/`.
16. Backend deps unpinned (`fastapi>=0.115.0` etc.) — no lock file.
17. No backend service in `docker-compose.yml` — only Postgres + Redis.

## Conventions

- **Timezone**: Asia/Dubai everywhere. Dates render as `en-AE`.
- **API base URL**: `http://localhost:8000` (frontend env: `NEXT_PUBLIC_API_URL`).
- **Personas in briefing**: Raymond (CEO advisor), Dembe (open loops tracker), Bookkeeper (capital).
- **Project codes**: `OPP-001..OPP-004` (deals), `GIA-001` (Gia ventures). Hardcoded in `seed_from_rr.py`.
- **Money**: `deal_value_usd` int, capital position string `"5000-50000"` for ranges.
- **Embedding model**: fastembed local (no AI spend), 384-dim.

## Forbidden / dangerous

- Never commit `.env` — keep it gitignored, rotate the values that already leaked.
- Never put credentials in `data/credentials/` into git.
- Don't add `async def` to existing routes without also switching the engine to `postgresql+asyncpg://`.
- Don't edit `schema.sql` without a matching alembic migration once that's bootstrapped.
- Don't expose port 8000 outside localhost without auth middleware.

## Useful Ruflo memory keys

- `projects/rr-command-center-overview` — high-level project facts
- `projects/rr-audit-2026-05-03` — full audit synthesis
- `profile/user-profile` — Marwan's environment + projects
