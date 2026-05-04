# RR Command Center — Architecture (v2026-05-04)

> Status: locked architecture, awaiting one decision (M365 tenant topology) before Phase 1B starts.
> Revised 2026-05-04 to bake the **premortem failure-mode preventives** in as enforced engineering invariants (Section 5).
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

## 4. Architecture diagram

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
│         ⟶ classify (Claude, cost-capped) ⟶ extract tasks ⟶ route       │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Postgres + pgvector                              │
│  entities · projects · tasks · email_threads · email_messages · events  │
│  briefing_synthesis · open_loops · capital_position · watchlist         │
│  workspaces · workspace_members · audit_log · read_audit_log            │
│  daily_cost_summary · usage_telemetry · categorizer_test_results        │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     FastAPI + RBAC + audit log                           │
│  /api/email · /api/projects · /api/tasks · /api/briefing · /api/feed    │
│  /api/workspaces · /api/audit · /api/costs · /api/telemetry · /auth     │
└──────────────────────────────────┬──────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                Next.js 14 dashboard (mobile + desktop)                   │
│  morning · war-room · intelligence · comms · wire · ledger · vault      │
│  rolodex · team · concierge · library · blacklist · map · settings      │
└─────────────────────────────────────────────────────────────────────────┘
```

## 5. Failure-mode prevention — non-negotiable engineering invariants

These rules exist because of the 2026-05-03 premortem (`memory key: rr-premortem-2026-05-03`). They are **enforced in code or schema**, not by discipline. Every PR must respect them; CI tests and constraints exist to make violation impossible.

### 5.1 No AI claim without a source

Every claim rendered in any AI-generated artifact (morning brief, intelligence synthesis, white-space recommendation) **must** carry one or more `source_refs` pointing back to a verifiable record (email_id, event_id, document_id, or external URL). The renderer **refuses to display** a claim with empty `source_refs`. Schema-enforced via `NOT NULL` and runtime-validated.

> Why: hallucination → trust collapse on day 12 → abandonment.

### 5.2 AI synthesis is opt-in per workspace

`workspaces.enable_ai_synthesis BOOL DEFAULT FALSE`. Phase 1A.2 ships the morning brief with **deterministic aggregation only** — Three Moves come from a heuristic over open_loops + capital_position + watchlist + recent thread activity. Claude-generated synthesis is a layer added in Phase 2, behind this flag, and only after the user has trusted the deterministic version for at least 30 days.

> Why: a wrong AI brief poisons trust faster than a boring deterministic one.

### 5.3 No outbound email without explicit human approval

`outbound_queue.status` transitions: `draft → pending_approval → sent`. No background job ever transitions `pending_approval → sent`. The transition requires a `POST /api/outbound/{id}/approve` call originating from a real user session (verified via `request.state.user`). Diff preview shown on the approval screen. CI test `test_no_blind_send` walks the full flow and asserts no auto-send path exists.

> Why: ghostwritten email sent to wrong recipient → confidentiality breach → unrecoverable.

### 5.4 Daily cost cap per workspace

`workspaces.daily_cost_cap_usd NUMERIC DEFAULT 5.00`. Every Claude API call goes through `app/ai/claude.py`, which checks today's spend for the workspace **before** the call. If the call would exceed the cap, raises `BudgetExceeded`; the worker surfaces the error in `usage_telemetry` and via a banner. Three-tier model routing enforced: Haiku for categorization, Sonnet for synthesis, Opus only on explicit deep-research requests with a separate higher cap.

> Why: 50 mailboxes × 1k emails/day at the wrong tier = $4K/month surprise.

### 5.5 Categorizer must pass test corpus before activation

`workspaces.categorizer_test_passed_at TIMESTAMPTZ`. Phase 1B's M365 connector activation endpoint refuses to enable a workspace where this is null. Test corpus = 50 hand-labeled emails per workspace covering Arabic + English + domain-specific (commodity, diplomatic, deal flow). Recall floor: 0.90. Below threshold = activation blocked, alert raised.

> Why: off-the-shelf categorizer accuracy claims (97%) collapse on Arabic + sovereign content.

### 5.6 Acceptable use policy gate before any team inbox is read

`workspaces.aup_signed_at TIMESTAMPTZ`. M365 connector activation endpoint **rejects** any workspace where this is null. Template at `docs/legal/AUP_TEMPLATE.md`, designed for UAE PDPL + DIFC alignment, intended to be reviewed by a DIFC employment lawyer before go-live.

> Why: surveilled employee files complaint → 6-week shutdown + UAE labor lawyer letter.

### 5.7 Per-thread monitoring exclusion respected

Email subject contains `[private]` OR thread is in a designated personal-label list per account → ingestion worker **skips it**. The check happens at ingestion time, not display time. Never indexed, never embedded, never categorized.

> Why: gives team a clear opt-out → reduces incentive to circumvent system via WhatsApp/personal Gmail.

### 5.8 Thread stitching is RFC 2822 only

`thread_stitcher.py` matches by `Message-ID`, `In-Reply-To`, and `References` headers exclusively. Subject-only matching is forbidden. Test `test_thread_isolation` asserts two distinct conversations with similar subjects never merge. Monthly automated audit job samples 100 threads and flags low-confidence merges for review.

> Why: cross-tenant thread merge → quote one client's content to another → catastrophic confidentiality breach.

### 5.9 Restricted domains list, hardcoded

`app/scrapers/_restricted.py` exports a frozen `RESTRICTED_DOMAINS` set: `bloomberg.com`, `reuters.com`, `wsj.com`, `ft.com`, `kpler.com` (use API), `platts.com` (use API), and others as added. Any connector attempting to fetch these via Playwright / requests **raises** `RestrictedDomainError`. CI test asserts the violation. Bypass requires a code change visible in PR review.

> Why: ToS violation → legal letter → punitive damages because intent was documented in repo.

### 5.10 Workspace must have ≥2 principals before M365 admin grant

Enforced in `workspaces.py` activation endpoint. The Azure app registration onboarding script also requires a second human as app owner. DR runbook in `docs/DR.md`.

> Why: principal disappears (illness, account lockout, partner falling-out) → entire system locked behind one identity.

### 5.11 Read-event audit log for sensitive resources

Separate `read_audit_log` table. A `@audit_read` decorator wraps every endpoint that returns email content, capital_position, audit_log, or anything tagged `confidential`. Logs `actor_email`, `target_type`, `target_id`, `created_at`. Retention: indefinite for compliance.

> Why: DIFC audit demands "who viewed which email content, when" — retrofit cost > prevention cost.

### 5.12 Telemetry-driven feature lifecycle

`usage_telemetry` records every page view per user. Weekly cron generates a "did this earn its keep?" report. Any room with <5 visits in 30 days flagged for deletion. Dashboard sentimentally retains nothing.

> Why: 14 rooms today, 6 used in 90 days, 8 atrophy and add maintenance load. Telemetry forces the decision.

### 5.13 Per-claim feedback loop on the morning brief

Every claim rendered in the morning room has a 👍/👎 button. Click logs to `briefing_feedback` with claim_id, decision, optional note. Weekly aggregate review surfaces consistently-wrong patterns. Below 70% positive over 14 days → AI synthesis auto-disables for that workspace, deterministic-only mode resumes.

> Why: closed-loop quality control. The system catches its own decay before the user gives up on it.

## 6. Connector layer

### M365 Graph (the critical one)

| Decision | Choice |
|---|---|
| Auth flow | Application permissions with **admin-grant** consent (not delegated) |
| Required scopes | `Mail.Read` (Application), `User.Read.All`, `MailboxSettings.Read` |
| Mailbox scoping | Exchange Online RBAC for Applications — `New-ManagementScope` with `RecipientRestrictionFilter`, `New-ManagementRoleAssignment`. Limit access to only the 20–50 mailboxes in scope |
| Update model | **Hybrid**: change-notification webhooks subscribe per-mailbox; webhook fires → call delta query for that mailbox to fetch only new/changed messages |
| Multi-tenant | Separate Entra ID app registration + Global Admin consent **per M365 tenant** |
| Rate limits | Global 130k req / 10s across all tenants per app, write 500/20s per tenant |
| Subscription cap | 1,000 active subscriptions per mailbox per app — well within for our use case |
| Activation gates (5.5, 5.6, 5.10) | Workspace must have AUP signed, categorizer test passed, ≥2 principals |

**Source files** (Phase 1B):
- `backend/app/connectors/m365.py` — Graph client wrapper
- `backend/app/connectors/m365_webhook.py` — webhook receiver, delta orchestration
- `backend/app/connectors/_restricted.py` — restricted-domain enforcement (5.9)
- `backend/app/connectors/__init__.py` — registry pattern

### Gmail (existing, kept for principal's personal accounts)

`backend/app/email/gmail_client.py` already implements list/get/parse/send. Will be moved under `connectors/gmail.py` for consistency. **Rotate the leaked OAuth credentials immediately.**

### RSS + Newsletter inbox (Phase 2)

Subscribe principal's email to Bloomberg, FT, Reuters free newsletters → ingest via M365 Graph → tagged as `source=newsletter` in `email_messages` → routed into `intel_feed` view. Avoids 5.9 violation entirely.

### Reuters RDP, Kpler, S&P Platts (Phase 2)

Real APIs exist. Connectors built when budget for licensed feeds is approved. Stub interfaces in `app/connectors/intel/` so wiring is ready.

### Twitter / X (Phase 2)

`tweepy>=4.14.0` already in deps. Free tier: 500K reads/month. Build `connectors/twitter.py` for handle + keyword monitoring.

### Brave Search (Phase 2)

Free 2,000 queries/month. `connectors/brave.py` for daily deep research agent.

## 7. Multi-tenant data model

Already shipped in migration `0003_workspaces.py`. The premortem rules require these **additions** in migration `0004_phase1a2.py`:

```sql
-- Premortem 5.4 — daily cost cap per workspace
ALTER TABLE workspaces ADD COLUMN daily_cost_cap_usd NUMERIC(8,2) NOT NULL DEFAULT 5.00;

-- Premortem 5.2 — AI synthesis is opt-in per workspace
ALTER TABLE workspaces ADD COLUMN enable_ai_synthesis BOOL NOT NULL DEFAULT FALSE;

-- Premortem 5.6 — AUP gate before M365 activation
ALTER TABLE workspaces ADD COLUMN aup_signed_at TIMESTAMPTZ;
ALTER TABLE workspaces ADD COLUMN aup_signed_by_email TEXT;

-- Premortem 5.5 — categorizer test gate
ALTER TABLE workspaces ADD COLUMN categorizer_test_passed_at TIMESTAMPTZ;
ALTER TABLE workspaces ADD COLUMN categorizer_test_recall NUMERIC(4,3);
ALTER TABLE workspaces ADD COLUMN categorizer_test_precision NUMERIC(4,3);

-- Premortem 5.11 — read-event audit (separate from mutation audit_log)
CREATE TABLE read_audit_log (
  id BIGSERIAL PRIMARY KEY,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  actor_email TEXT,
  target_type TEXT NOT NULL,        -- 'email_message','capital_position','audit_log',...
  target_id TEXT NOT NULL,
  ip_address INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_read_audit_workspace_target ON read_audit_log(workspace_id, target_type, created_at DESC);

-- Premortem 5.4 — daily cost summary, used to enforce the cap
CREATE TABLE daily_cost_summary (
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  cost_date DATE NOT NULL,
  model TEXT NOT NULL,
  total_input_tokens BIGINT NOT NULL DEFAULT 0,
  total_output_tokens BIGINT NOT NULL DEFAULT 0,
  total_usd NUMERIC(10,4) NOT NULL DEFAULT 0,
  call_count INT NOT NULL DEFAULT 0,
  PRIMARY KEY (workspace_id, cost_date, model)
);

-- Premortem 5.12 — telemetry-driven feature lifecycle
CREATE TABLE usage_telemetry (
  id BIGSERIAL PRIMARY KEY,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE SET NULL,
  actor_email TEXT,
  event_type TEXT NOT NULL,        -- 'page_view','room_open','feature_use'
  event_target TEXT NOT NULL,      -- 'morning','wire','comms',etc
  duration_ms INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_telemetry_workspace_event ON usage_telemetry(workspace_id, event_target, created_at DESC);

-- Premortem 5.7 — per-thread monitoring exclusion
ALTER TABLE email_threads ADD COLUMN monitoring_excluded BOOL NOT NULL DEFAULT FALSE;
ALTER TABLE email_threads ADD COLUMN excluded_reason TEXT;
```

## 8. Briefing data layer (Phase 1A.2)

The current `_seed_briefing()` hardcoded JSON gets replaced. New tables, **all source-cited per rule 5.1**:

```sql
CREATE TABLE briefing_synthesis (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id),    -- NULL = cross-portfolio aggregate
  brief_date DATE NOT NULL,
  -- Deterministic aggregation (rule 5.2 — always populated)
  three_moves JSONB NOT NULL,                     -- [{rank,move,rationale,source_refs:[...]}]
  -- AI synthesis layer (rule 5.2 — populated only if enable_ai_synthesis=TRUE)
  raymond_dispatch TEXT,
  raymond_dispatch_source_refs JSONB,             -- REQUIRED non-null if dispatch is set
  withheld TEXT,
  generated_at TIMESTAMPTZ,
  generation_mode TEXT NOT NULL CHECK (generation_mode IN ('deterministic','ai_synthesized')),
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
  workspace_id UUID REFERENCES workspaces(id),    -- NULL = aggregate across portfolio
  recorded_for DATE NOT NULL,
  deployable_usd_low BIGINT,
  deployable_usd_high BIGINT,
  committed_usd BIGINT,
  pipeline_summary TEXT,
  source TEXT NOT NULL CHECK (source IN ('manual','derived')),
  UNIQUE(workspace_id, recorded_for)
);

CREATE TABLE watchlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id),
  brief_date DATE NOT NULL,
  rank INT,
  item TEXT NOT NULL,
  source_refs JSONB NOT NULL                      -- rule 5.1 — every item must cite something
);

-- Rule 5.13 — per-claim feedback loop
CREATE TABLE briefing_feedback (
  id BIGSERIAL PRIMARY KEY,
  briefing_id UUID REFERENCES briefing_synthesis(id) ON DELETE CASCADE,
  claim_path TEXT NOT NULL,                       -- 'three_moves[0]', 'watchlist[2]'
  actor_email TEXT,
  verdict TEXT NOT NULL CHECK (verdict IN ('useful','wrong','noise')),
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Briefing job** (`backend/app/workers/briefing_generate.py`) — runs daily at 04:30 GST:

1. **Phase 1A.2 (deterministic only)**:
   - Aggregate prior 24h email/event/task signals per workspace
   - Heuristic ranks Three Moves: open loops > deal_stage advances > capital pipeline changes
   - Materialize `open_loops`, `capital_position`, `watchlist`, `briefing_synthesis(generation_mode='deterministic')`
   - Every row has `source_refs` populated

2. **Phase 2 (AI synthesis layer, gated by `enable_ai_synthesis=TRUE`)**:
   - Reads the deterministic data
   - Calls Claude with `prompts/morning_brief.md`, **enforcing per-claim citations**
   - Validates output: every produced sentence must reference an existing source_id
   - Stores with `generation_mode='ai_synthesized'`
   - Cost-capped per rule 5.4

Frontend `morning/page.tsx` already consumes `/api/briefing/today` — only the data source changes. Each rendered claim shows a small source-link icon + 👍/👎 buttons (rule 5.13).

## 9. Action layer (principal-directed comms)

When the principal clicks "Tell Ahmed to follow up by Friday" on a thread:

1. UI calls `POST /api/threads/<id>/direct` with `{assignee, due_date, message}`
2. Backend creates a `task` row (status=`pending`, owner=Ahmed, due=Friday)
3. Backend writes to `outbound_queue` with `from_account=ahmed@company.com`, `body=ghostwritten by Claude with thread context + principal's directive`, **`status=pending_approval`** (rule 5.3)
4. **Ahmed** sees a banner in his Outlook (since the inbox is monitored, the assignment-as-email lands in his inbox naturally — but the outbound to the counterparty does NOT auto-send)
5. **Marwan** sees a "Pending approval" badge in `comms` and `outbox` views. Click → diff preview → approve → send → audit_log entry
6. When the counterparty replies, M365 webhook captures it → backend updates `task.status=in_progress` → audit log entry

No tool switch for Ahmed. No login required. He sees the assignment in his normal inbox. **The principal stays in the loop on every send.**

Thread stitcher (rule 5.8): RFC 2822 headers only. Subject-only matching forbidden. Tests assert isolation.

## 10. Auth and RBAC

- **Authentication**: Microsoft SSO (since team is on M365). Users log in with their `@company.com` account. We trust the Entra tenant.
- **Authorization**: enforced at API layer. JWT issued post-MS-OAuth includes `workspace_memberships: [{workspace_id, role}, ...]`.
- **Role matrix**:

| Role | Sees | Can edit |
|---|---|---|
| Principal | All workspaces they belong to | Everything in those workspaces |
| Exec | Their workspace only | Projects, tasks, threads in workspace |
| Operator | Threads/tasks they're assigned to | Their own assignments |
| Read-only | Their workspace | Nothing |

Every workspace **must** have ≥2 `principal` members before M365 connector activation (rule 5.10).

Every mutation writes to `audit_log`. Every read of sensitive resources writes to `read_audit_log` (rule 5.11).

## 11. Cost ceiling enforcement

`app/ai/claude.py` is the sole entry point for Claude API calls. Pseudocode:

```python
async def claude_call(workspace_id: UUID, model: str, prompt: str, ...) -> ClaudeResponse:
    settings = get_settings()
    cap_usd = await get_workspace_daily_cap(workspace_id)
    spent_today = await get_workspace_spent_today(workspace_id)

    estimated_cost = estimate_cost(model, prompt)
    if spent_today + estimated_cost > cap_usd:
        record_event("budget_exceeded", workspace_id=workspace_id, requested=estimated_cost)
        raise BudgetExceeded(workspace_id, cap_usd, spent_today, estimated_cost)

    # Three-tier routing
    if model == "auto":
        model = pick_model(prompt_complexity(prompt))    # haiku|sonnet|opus

    response = await call_anthropic(model, prompt, ...)
    await record_cost(workspace_id, model, response.usage)
    return response
```

Three-tier routing defaults:
- `haiku` — categorization, classification, short summaries
- `sonnet` — morning brief synthesis, deep research, multi-step reasoning
- `opus` — only when explicitly requested by the principal for "deep dive" or white-space analysis (Phase 3), with a separate `daily_opus_cap_usd` (default $0, must be raised explicitly per workspace)

Cost dashboard at `/settings/costs` shows: today vs cap, 30-day trend, per-model breakdown, top 10 most expensive workers/threads.

## 12. Telemetry & feature lifecycle

`usage_telemetry` (see schema in §7) records every page view, room open, and feature use. Frontend instrumented via a `useTelemetry()` hook on every dashboard page; backend instrumented for every endpoint it cares about.

**Weekly cron** (`workers/feature_lifecycle.py`):
- For every `event_target` (room/feature), compute visits over last 30 days
- Write `feature_usage_report` row with verdict: `healthy` (>=20 visits), `marginal` (5-19), `dying` (<5)
- For 3 consecutive weeks of `dying` → email principal: "Should we delete `<feature>`?"

**Quarterly cron**: chaos-exercise reminder. Calendar event auto-generated.

## 13. Hosting

| Layer | Tool | Region |
|---|---|---|
| App + API | Hetzner Cloud (Frankfurt) initially | Migrate to UAE (Equinix DX1, du Cloud, or AWS Bahrain) before any sovereign-data workspace activates |
| Postgres | Hetzner managed Postgres | Same region as app |
| Redis | Hetzner Redis or Upstash | Same region |
| File storage | Cloudflare R2 (S3-compatible, no egress fees) | EU initially, with regional copy if needed |
| Background jobs | APScheduler in-process for now; migrate to RQ/Celery if scale demands | — |
| CDN | Cloudflare in front of Next.js | Global |
| Monitoring | Sentry + Better Stack (logs + uptime) | — |
| Secrets | Hetzner Vault or 1Password Connect (NOT in repo, NOT in `.env` post-Phase 1C) | — |

Estimated monthly cost: $80–200 at MVP scale, $300–600 at full Phase 1 scale (50 mailboxes flowing). UAE migration adds ~$200/mo.

## 14. Phased build plan (revised after premortem)

### Phase 0 — Foundation hardening ✅ shipped 2026-05-03 (commit 1757f47)
Auth scaffold, alembic, Pydantic schemas, lib/api.ts, error boundary, indexes, gitignore hardening.

### Phase 1A.1 — Workspace data model + CRUD UI ✅ shipped 2026-05-03 (commit 1757f47)
Migrations 0003. Multi-tenant tables, audit_log, settings/companies UI.

### Phase 1A.2 — Briefing data layer + premortem invariants (1.5 weeks)

Originally 1 week; expanded to bake in rules 5.1, 5.2, 5.4, 5.10, 5.11, 5.12, 5.13.

- Migration 0004 — `briefing_synthesis`, `open_loops`, `capital_position`, `watchlist`, `briefing_feedback`, `read_audit_log`, `daily_cost_summary`, `usage_telemetry`, plus workspace columns from §7
- `workers/briefing_generate.py` — **deterministic aggregation only** (no Claude yet); produces source-cited Three Moves heuristically
- `workers/feature_lifecycle.py` — weekly usage report
- `app/ai/claude.py` cost-cap wrapper + 3-tier routing (rule 5.4)
- `@audit_read` decorator + apply to email-content endpoints (rule 5.11)
- Frontend: workspace filter chips in header (cross-portfolio default), per-claim 👍/👎 on morning room, /settings/costs page
- Frontend: `useTelemetry()` hook applied to every room
- Migrate remaining inline-fetch pages (war-room, concierge, ledger, library, rolodex, vault, blacklist) to `apiFetcher`
- Workspace settings UI: dual-principal enforcement (rule 5.10) — workspace can't be marked `m365_ready` until 2nd principal added

### Phase 1B — M365 connector (2.5 weeks)

Originally 2 weeks; expanded to bake in rules 5.5, 5.6, 5.7, 5.8, 5.9.

- `app/connectors/m365.py` — Graph SDK + admin-grant flow
- `app/connectors/m365_webhook.py` — change notification receiver
- `app/connectors/_restricted.py` — restricted-domain enforcement (rule 5.9)
- `scripts/onboard_workspace.py` — Entra app registration + admin consent + activation gates
- AUP template at `docs/legal/AUP_TEMPLATE.md` (rule 5.6)
- Categorizer test corpus per workspace (rule 5.5) — 50 hand-labeled emails minimum
- Per-thread `monitoring_excluded` flag respected in ingest worker (rule 5.7)
- RFC 2822-only thread stitcher with `test_thread_isolation` in CI (rule 5.8)
- Outbound queue activation requires explicit approval click (rule 5.3) + diff preview + `test_no_blind_send`
- Backfill: pull last 30 days for new mailbox, re-categorize via worker
- Frontend: existing `comms/`, `wire/`, `morning/` pages now show real M365 data

### Phase 1C — Cloud deploy + multi-workspace (2 weeks)

Originally 1 week; expanded for proper hosting + retention + DR.

- Hetzner / Fly.io provisioning, secrets in vault (out of `.env`)
- Docker compose: add `backend` + `frontend` services for production
- CI on GitHub Actions: tsc, pytest, alembic dry-run
- Storage retention policies: emails > 18 months → text-only; embeddings on inactive entities → pruned
- DR runbook at `docs/DR.md` + first DR drill
- Mobile responsive testing on iPhone Safari + Android Chrome
- Sentry, Better Stack wiring
- DPIA + employment policy template (rule 5.6) finalized
- Third-party security review ($5–10K, scoped to: M365 admin grant boundary, audit_log integrity, scraper restriction, RBAC enforcement)

### Phase 2 — Intel + outbound activation (Weeks 8–11)

- RSS + newsletter ingestion (route Bloomberg/FT newsletters through principal's email)
- Twitter v2 connector
- Brave Search daily research agent (`workers/deep_research.py`)
- Topic filter UI in `settings/topics`
- AI synthesis layer enabled per-workspace (rule 5.2 lifted via `enable_ai_synthesis=TRUE` toggle in settings, with confirmation flow)
- Reuters RDP / Kpler / S&P API connectors as licensed feeds approved

### Phase 3 — White-space finder (Weeks 12+)

- Cross-reference principal's email deal flow + Kpler commodity flows + geopolitical news + tech deal signals
- Agentic research loop with per-claim source citations (rule 5.1)
- New `opportunities` table + `concierge` page upgrade

**Net timeline change**: ~2 weeks added vs the original Phase 1 plan. Phase 1 lands ~Week 8 instead of Week 6. Phase 2 starts immediately after.

## 15. Risks (post-premortem residual)

These are the risks that remain even after the §5 invariants. Most have been pushed from "likely" to "possible but mitigated"; a few are inherently outside code's reach.

| Residual risk | What § 5 addresses | What still needs human judgment |
|---|---|---|
| AI brief abandoned | 5.1, 5.2, 5.13 | Whether the deterministic version is actually useful (only Marwan can say) |
| Team revolt over monitoring | 5.6, 5.7 | The framing when announcing the platform; the actual signed AUP from a real DIFC lawyer |
| Categorizer collapse | 5.5 | Quarterly retraining decisions; expanding test corpus over time |
| Cost runaway | 5.4 | Whether the $5/day default cap is right for your workload |
| Bus factor | 5.10 | Documentation discipline; quarterly DR drill |
| Compliance audit | 5.11 | Whether DIFC accepts the audit_log + read_audit_log schema; need a DPO review |
| Bloomberg / Reuters legal exposure | 5.9 | Future engineers (or you under deadline) trying to bypass the restriction |
| Strategic obsolescence | clean LLM provider abstraction in `app/ai/claude.py` | Whether to stay custom-built when Front/Missive ship "principal mode" |
| Unknown unknowns | quarterly chaos exercise + paid 3rd-party security review (Phase 1C) | Decision to actually budget the security review |

## 16. Decisions still open

1. ~~**M365 tenant topology**~~ ✅ **Resolved 2026-05-04** — multi-tenant. Each company has its own M365 tenant. Some workspaces hold multiple projects, some hold one. Per-tenant Entra app registration + admin consent required. `workspaces.m365_tenant_id` is the canonical connector key. Onboarding is one-workspace-at-a-time via `scripts/onboard_workspace.py`. See memory key `rr-tenant-topology-2026-05-04`.
2. **DIFC DPO contact** — Do you have one or need a recommendation? *(Blocks Phase 1C go-live + AUP template review.)*
3. **Phase 2 paid feed budget** — Any of Reuters/Kpler/S&P preauthorized for $5–20K/year licensing? *(Affects Phase 2 timing.)*
4. **Daily cost cap default** — Is $5/day per workspace the right default? Will revisit after first week of real usage data in Phase 1B.
5. **AUP signing process** — Wet signature, e-signature (DocuSign / Adobe Sign), or click-through accept? Affects implementation of `aup_signed_at` capture.
6. **Per-tenant onboarding cadence** — Do you want all 5–10 tenants onboarded at once (~5 hours of admin-consent flows) or staged company-by-company over a few weeks?
