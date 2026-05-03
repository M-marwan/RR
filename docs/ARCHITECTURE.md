# RR Command Center — Architecture (v2026-05-03)

> Status: proposed, awaiting one decision (M365 tenant topology) before lock-in.
> This document supersedes any prior architectural sketches.

## 1. North-star principle

**Read everywhere. Direct quietly. Never force the team to change tools.**

The system silently ingests every team mailbox via Microsoft Graph admin-grant OAuth. Team members keep using Outlook exactly as today and never log into the platform. The principal sees every thread from one dashboard, sliced by company / project / deal / person / topic, and directs via dashboard clicks. Outbound messages are sent **as-the-team-member** by default (an assignment lands in Ahmed's Outlook like a normal email he owns) or **as-the-principal** (rare, ghostwriter mode).

## 2. Why this is novel

Market validation (2026-05-03) confirmed no existing product covers this combination:

- Front, Hiver, Missive, Superhuman for Teams — **all require every team member to adopt a new client.** That kills the principal's stated requirement.
- AlphaSense, Sentieo, Factiva — strong intel, **no email orchestration, no action layer.**
- Addepar, Asora, Mirador, Eton Solutions — financial operations only, **don't touch communications.**

Closest pattern is Missive's "Observer" role — but their unified-inbox view excludes Observer-only mailboxes, defeating the purpose.

## 3. Verticals served

Multi-vertical operation across the principal's ~5–10 companies:

- Oil & gas full chain (upstream / midstream / downstream / trading)
- Tech VC / startups
- Diplomacy / sovereign / family office (Antigua & Barbuda surfaced, UAE/GCC primary)
- Likely real estate

Topic filter taxonomy is principal-tunable.

## 4. Architecture diagram (text)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Connectors                                     │
│  M365 Graph (per-tenant)  ⟶  Gmail (Marwan)  ⟶  RSS / Newsletters      │
│  Reuters RDP API (Phase 2)  Kpler/S&P APIs (Phase 2)  Twitter v2        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Ingestion pipeline                               │
│  Webhook ⟶ fetch ⟶ parse ⟶ embed (fastembed 384-dim)                   │
│         ⟶ classify (Claude) ⟶ extract tasks ⟶ route to project          │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Postgres + pgvector                              │
│  entities · projects · tasks · email_threads · email_messages · events  │
│  briefing_synthesis · open_loops · capital_position · watchlist (NEW)   │
│  newsletter_sources · synthesis_cache · claude_usage · workspaces (NEW) │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     FastAPI + RBAC + audit log                           │
│  /api/email · /api/projects · /api/tasks · /api/briefing · /api/feed    │
│  /api/workspaces · /api/audit · /auth (NEW)                             │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                Next.js 14 dashboard (mobile + desktop)                   │
│  morning · war-room · intelligence · comms · wire · ledger · vault      │
│  rolodex · team · concierge · library · blacklist · map · settings      │
└─────────────────────────────────────────────────────────────────────────┘
```

## 5. Connector layer

### M365 Graph (the critical one)

| Decision | Choice |
|---|---|
| Auth flow | Application permissions with **admin-grant** consent (not delegated) |
| Required scopes | `Mail.Read` (Application), `User.Read.All`, `MailboxSettings.Read` |
| Mailbox scoping | Exchange Online RBAC for Applications — `New-ManagementScope` with `RecipientRestrictionFilter`, `New-ManagementRoleAssignment`. Limit access to only the 20–50 mailboxes in scope |
| Update model | **Hybrid**: change-notification webhooks subscribe per-mailbox; webhook fires → call delta query for that mailbox to fetch only new/changed messages |
| Multi-tenant | Separate Entra ID app registration + Global Admin consent **per M365 tenant** |
| Rate limits | Global 130k req / 10s across all tenants per app, write 500/20s per tenant. Trivial at this scale |
| Subscription cap | 1,000 active subscriptions per mailbox per app — well within for our use case |

**Source files** (to be created):
- `backend/app/connectors/m365.py` — Graph client wrapper
- `backend/app/connectors/m365_webhook.py` — webhook receiver, delta orchestration
- `backend/app/connectors/__init__.py` — registry pattern
- Migration: add `m365_tenant`, `m365_app_id`, `m365_admin_consent_at` to `email_accounts` table

### Gmail (existing — keep)

`backend/app/email/gmail_client.py` already implements list/get/parse/send. Refactor under `connectors/gmail.py`. Rotate the leaked OAuth credentials.

### RSS + Newsletter inbox (Phase 2)

Subscribe principal's email to Bloomberg, FT, Reuters free newsletters → ingest via M365 Graph → tagged as `source=newsletter` in `email_messages` → routed into `intel_feed` view rather than project mailbox.

### Reuters RDP, Kpler, S&P Platts (Phase 2)

Real APIs exist. Connectors built when budget for licensed feeds is approved. Stub interfaces in `app/connectors/intel/` so wiring is ready.

### Twitter / X (Phase 2)

`tweepy>=4.14.0` already in deps. Free tier: 500K reads/month. Build `connectors/twitter.py` for handle + keyword monitoring.

### Brave Search (Phase 2)

Free 2,000 queries/month. `connectors/brave.py` for daily deep research agent.

## 6. Multi-tenant data model additions

```sql
-- Workspaces = one per company
CREATE TABLE workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  m365_tenant_id TEXT,            -- Azure tenant GUID
  m365_app_id TEXT,               -- per-tenant Entra app
  m365_consent_granted_at TIMESTAMPTZ,
  primary_color TEXT,
  industry TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Membership = who is in which workspace
CREATE TABLE workspace_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  entity_id UUID REFERENCES entities(id),
  role TEXT NOT NULL CHECK (role IN ('principal','exec','operator','readonly')),
  joined_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(workspace_id, entity_id)
);

-- Add workspace_id to scoped tables
ALTER TABLE projects        ADD COLUMN workspace_id UUID REFERENCES workspaces(id);
ALTER TABLE tasks           ADD COLUMN workspace_id UUID REFERENCES workspaces(id);
ALTER TABLE email_messages  ADD COLUMN workspace_id UUID REFERENCES workspaces(id);
ALTER TABLE email_threads   ADD COLUMN workspace_id UUID REFERENCES workspaces(id);
ALTER TABLE outbound_queue  ADD COLUMN workspace_id UUID REFERENCES workspaces(id);

-- Audit log (UAE PDPL / DIFC requirement)
CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id),
  actor_entity_id UUID REFERENCES entities(id),
  action TEXT NOT NULL,           -- 'view_email','assign_task','approve_draft', etc.
  target_type TEXT,
  target_id UUID,
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_log_workspace_created ON audit_log(workspace_id, created_at DESC);
```

## 7. Briefing data layer (the morning room hardening)

The current `_seed_briefing()` hardcoded JSON gets replaced by real materialized data. New tables:

```sql
CREATE TABLE briefing_synthesis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id),
  brief_date DATE NOT NULL,
  raymond_dispatch TEXT,
  three_moves JSONB,              -- [{rank,move,rationale},...]
  withheld TEXT,
  generated_at TIMESTAMPTZ,
  source TEXT CHECK (source IN ('cache','seed','stale')),
  UNIQUE(workspace_id, brief_date)
);

CREATE TABLE open_loops (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id),
  thread_id UUID REFERENCES email_threads(id),
  person_entity_id UUID REFERENCES entities(id),
  days_waiting INT,
  last_outbound_at TIMESTAMPTZ,
  status TEXT CHECK (status IN ('open','closed','snoozed'))
);

CREATE TABLE capital_position (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id),
  recorded_for DATE NOT NULL,
  deployable_usd_low INT,
  deployable_usd_high INT,
  committed_usd BIGINT,
  pipeline_summary TEXT,
  UNIQUE(workspace_id, recorded_for)
);

CREATE TABLE watchlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id),
  brief_date DATE NOT NULL,
  rank INT,
  item TEXT NOT NULL
);
```

**Briefing job** (`backend/app/workers/briefing_generate.py`) — runs daily at 04:30 GST:
1. Aggregate prior 24h email/event/task signals per workspace
2. Build prompt context from `synthesis_cache`, `open_loops`, `capital_position`
3. Call Claude with `prompts/morning_brief.md`
4. Parse JSON → write `briefing_synthesis` + `watchlist` rows
5. Recompute `open_loops` (already runs hourly via existing `recompute_all_open_loops`)

Frontend `morning/page.tsx` already consumes `/api/briefing/today` and renders all of these blocks — only the data source changes from `_seed_briefing()` to real reads.

## 8. Action layer (principal-directed comms)

When the principal clicks "Tell Ahmed to follow up by Friday" on a thread:

1. UI calls `POST /api/threads/<id>/direct` with `{assignee, due_date, message}`
2. Backend creates a `task` row (status=`pending`, owner=Ahmed, due=Friday)
3. Backend writes to `outbound_queue` with `from_account=ahmed@company.com`, `to=<counterparty>`, `body=ghostwritten by Claude using thread context + principal's directive`, `status=draft`
4. Ahmed receives an email in his Outlook **from himself** (no separate channel) with subject `[Marwan] Action: follow up X by Friday` — a normal email he can reply to / send
5. When Ahmed replies, M365 webhook captures it → backend updates `task.status=in_progress` → audit log entry

No tool switch for Ahmed. No login required. He sees the assignment in his normal inbox.

## 9. Auth and RBAC

- **Authentication**: Microsoft SSO (since team is on M365). Users log in with their `@company.com` account. We trust the Entra tenant.
- **Authorization**: enforced at API layer. JWT issued post-MS-OAuth includes `workspace_memberships: [{workspace_id, role}, ...]`.
- **Role matrix**:

| Role | Sees | Can edit |
|---|---|---|
| Principal | All workspaces | Everything |
| Exec | Their workspace only | Projects, tasks, threads in workspace |
| Operator | Threads/tasks they're assigned to | Their own assignments |
| Read-only | Their workspace | Nothing |

Audit log entries on every mutation.

## 10. Hosting

| Layer | Tool | Region |
|---|---|---|
| App + API | Fly.io or Hetzner Cloud (Frankfurt) | EU initially; flag to migrate to UAE/DIFC for sovereign workloads |
| Postgres | Hetzner managed Postgres or Supabase | Same region as app |
| Redis | Hetzner Redis or Upstash | Same region |
| File storage | Cloudflare R2 (S3-compatible, no egress fees) | EU |
| Background jobs | APScheduler in-process for now; migrate to RQ/Celery if scale demands | — |
| CDN | Cloudflare in front of Next.js | Global |
| Monitoring | Sentry + Better Stack (logs + uptime) | — |

Estimated monthly cost: $80–200 at MVP scale, $300–600 at full Phase 1 scale (50 mailboxes flowing).

## 11. Phased build plan

### Phase 0 — Foundation hardening (Week 1)
- Rotate leaked Gmail OAuth creds (USER ACTION in Google Cloud Console)
- Move project out of OneDrive to e.g. `C:\Users\HELIOS\projects\rr-command-center`
- `git init` + first commit, push to private GitHub repo
- Bootstrap alembic from current `schema.sql` (one initial migration)
- Add Microsoft SSO auth middleware (`app/auth.py`) and apply to all routes
- Pydantic out-schemas for the 8 existing routes
- Write `frontend/lib/api.ts` shared client + global error boundary
- Fix `wire/page.tsx` SSE memory leak
- Add missing indexes (`open_loop_since`, `deal_stage`, `tasks(assigned_to,status)`)

### Phase 1A — Briefing data layer + one workspace (Week 2)
- Migration adding `workspaces`, `workspace_members`, scoped foreign keys, briefing tables, audit log
- Seed one workspace for principal's primary company
- Build `briefing_generate` worker + `prompts/morning_brief.md`
- Wire `/api/briefing/today` to real data; remove `_seed_briefing()`
- Frontend: workspace selector in CommandBar (single-workspace state for now)

### Phase 1B — M365 connector (Weeks 3–4)
- `app/connectors/m365.py` — Graph SDK + admin-grant flow
- `app/connectors/m365_webhook.py` — change notification receiver
- One-time onboarding script: `python scripts/onboard_workspace.py --tenant <id>` to register Entra app + grant consent
- Backfill: pull last 30 days for new mailbox into `email_messages`
- Re-categorize backfill via `email_categorize` worker
- Frontend: existing `comms/`, `wire/`, `morning/` pages now show real M365 data

### Phase 1C — Cloud deploy + multi-workspace (Weeks 5–6)
- Hetzner / Fly.io provisioning, secrets in vault, CI on GitHub Actions
- Docker compose: add `backend` + `frontend` services for production
- Add second workspace for second company
- Mobile responsive testing on iPhone Safari + Android Chrome
- Sentry, Better Stack wiring
- DPIA + employment policy template (UAE PDPL preparation)

### Phase 2 — Intel + outbound (Weeks 7–10, after Phase 1 lands)
- RSS + newsletter ingestion (route Bloomberg/FT newsletters)
- Twitter v2 connector
- Brave Search daily research agent (`workers/deep_research.py`)
- Topic filter UI in `settings/topics`
- Outbound queue activation (assignment-as-email pattern)
- Reuters RDP / Kpler / S&P API connectors as licensed feeds approved

### Phase 3 — White-space finder (Weeks 11+)
- Cross-reference principal's email deal flow + Kpler commodity flows + geopolitical news + tech deal signals
- Agentic research loop with verifiable claims
- New `opportunities` table + `concierge` page upgrade

## 12. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Multi-tenant M365 architecture unknown | Confirmed before Phase 1B starts. If 1 tenant: simple. If many: per-tenant onboarding script + cost grows linearly |
| Bloomberg/Reuters scraping liability | Avoided. Newsletter ingestion only. Real APIs in Phase 2 |
| UAE PDPL / DIFC employee monitoring exposure | Employment contract clauses + IT acceptable use policy + DPIA template before go-live |
| Categorization accuracy on Arabic + domain-specific email | Day-1 human review loop in `comms/` UI; track misclassification feedback to fine-tune over time |
| Engineering scope vs 4–6 week MVP | Aggressively cut to 1 workspace + briefing + email aggregation. Multi-workspace, paid intel, white-space all later |
| Cost ceiling underestimation | Track LLM spend per workspace via existing `claude_usage` hypertable. Set $1k/mo soft cap with budget alerts |

## 13. Decisions still open

1. **M365 tenant topology** — Are your 5–10 companies on one M365 tenant or many? *(Blocks Phase 1B start.)*
2. **GitHub repo URL** — Where to push? *(Blocks Phase 0 git init.)*
3. **DIFC DPO contact** — Do you have one or need a recommendation? *(Blocks Phase 1C go-live.)*
4. **Phase 2 paid feed budget** — Any of Reuters/Kpler/S&P preauthorized for $5–20K/year licensing? *(Affects Phase 2 timing.)*
