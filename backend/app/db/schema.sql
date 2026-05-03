-- RR Command Center — Full Database Schema
-- Includes Geo plan tables + email + projects + tasks + contacts + synthesis layers

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ─── ENUMS ───────────────────────────────────────────────────────────────────

CREATE TYPE entity_type AS ENUM (
    'person', 'company', 'country', 'sector', 'product', 'tech',
    'event', 'treaty', 'sanction', 'org', 'deal', 'venture'
);

CREATE TYPE claim_status AS ENUM (
    'confirmed', 'verified', 'reported', 'alleged', 'disputed', 'low_credibility'
);

CREATE TYPE rel_type AS ENUM (
    'employs', 'owns', 'leads', 'partners_with', 'competes_with',
    'sanctions', 'allies_with', 'opposes', 'trades_with', 'invests_in',
    'advises', 'founded', 'member_of'
);

CREATE TYPE email_direction AS ENUM ('inbound', 'outbound');
CREATE TYPE email_category AS ENUM (
    'action_required', 'project', 'deal', 'intelligence',
    'admin', 'newsletter', 'noise'
);
CREATE TYPE thread_status AS ENUM ('open', 'waiting_reply', 'replied', 'resolved', 'archived');
CREATE TYPE outbound_status AS ENUM ('draft', 'approved', 'sending', 'sent', 'failed');
CREATE TYPE project_type AS ENUM ('deal', 'venture', 'internal', 'relationship');
CREATE TYPE project_status AS ENUM ('prospecting', 'active', 'on_hold', 'closed', 'dead');
CREATE TYPE deal_stage AS ENUM ('prospecting', 'first_touch', 'due_diligence', 'term_sheet', 'closing', 'closed_won', 'closed_lost');
CREATE TYPE task_status AS ENUM ('open', 'in_progress', 'done', 'cancelled');
CREATE TYPE social_platform AS ENUM ('twitter', 'linkedin_rss', 'brave_search', 'reddit');
CREATE TYPE monitor_type AS ENUM ('account', 'keyword', 'hashtag', 'search_query');
CREATE TYPE ingestion_method AS ENUM ('email_forward', 'rss', 'pdf_attachment', 'playwright', 'api');


-- ═══════════════════════════════════════════════════════════════════════════════
-- GEO PLAN TABLES (core entity graph)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE entities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            entity_type NOT NULL,
    canonical_name  TEXT NOT NULL,
    aliases         TEXT[] DEFAULT '{}',
    wikidata_id     TEXT,
    country_code    TEXT,
    profile         JSONB DEFAULT '{}',
    embedding       VECTOR(384),
    first_seen      TIMESTAMPTZ DEFAULT now(),
    last_updated    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON entities(type);
CREATE INDEX ON entities(canonical_name);
CREATE INDEX ON entities USING GIN(aliases);
CREATE INDEX ON entities USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE sources (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    url             TEXT,
    credibility_score NUMERIC(3,2) DEFAULT 0.70,
    bias_label      TEXT,
    country         TEXT,
    type            TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url             TEXT UNIQUE,
    source_id       UUID REFERENCES sources(id),
    fetched_at      TIMESTAMPTZ DEFAULT now(),
    content_hash    TEXT,
    raw_path        TEXT,
    parsed_text     TEXT,
    entity_ids      UUID[] DEFAULT '{}',
    embedding       VECTOR(384),
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON documents(url);
CREATE INDEX ON documents(fetched_at DESC);
CREATE INDEX ON documents USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE claims (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id      UUID REFERENCES entities(id),
    predicate       TEXT NOT NULL,
    object_id       UUID REFERENCES entities(id),
    object_value    JSONB,
    valid_from      DATE,
    valid_to        DATE,
    status          claim_status NOT NULL DEFAULT 'reported',
    confidence      NUMERIC(3,2) DEFAULT 0.50,
    source_ids      UUID[] DEFAULT '{}',
    evidence_count  INT DEFAULT 1,
    extracted_at    TIMESTAMPTZ DEFAULT now(),
    last_corroborated TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON claims(subject_id);
CREATE INDEX ON claims(status);

CREATE TABLE events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type            TEXT,
    headline        TEXT NOT NULL,
    summary         TEXT,
    occurred_at     TIMESTAMPTZ,
    location        JSONB,
    entity_ids      UUID[] DEFAULT '{}',
    status          claim_status NOT NULL DEFAULT 'reported',
    source_ids      UUID[] DEFAULT '{}',
    impact_score    NUMERIC,
    relevance_score NUMERIC(3,2) DEFAULT 0.50,
    embedding       VECTOR(384),
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON events(occurred_at DESC);
CREATE INDEX ON events(relevance_score DESC);
CREATE INDEX ON events USING GIN(entity_ids);
CREATE INDEX ON events USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE relationships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id      UUID REFERENCES entities(id) NOT NULL,
    type            rel_type NOT NULL,
    object_id       UUID REFERENCES entities(id) NOT NULL,
    strength        NUMERIC(3,2) DEFAULT 0.50,
    valid_from      DATE,
    valid_to        DATE,
    evidence_count  INT DEFAULT 1,
    status          claim_status DEFAULT 'reported',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(subject_id, type, object_id)
);
CREATE INDEX ON relationships(subject_id);
CREATE INDEX ON relationships(object_id);


-- ═══════════════════════════════════════════════════════════════════════════════
-- EMAIL LAYER
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE email_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_name      TEXT NOT NULL,
    email_address   TEXT UNIQUE NOT NULL,
    provider        TEXT NOT NULL,           -- 'gmail' | 'outlook' | 'imap'
    auth_type       TEXT NOT NULL,           -- 'oauth2' | 'imap_password' | 'app_password'
    auth_credential_ref TEXT,               -- key name in secrets file
    last_sync_at    TIMESTAMPTZ,
    sync_enabled    BOOLEAN DEFAULT true,
    is_primary      BOOLEAN DEFAULT false,
    display_color   TEXT DEFAULT '#C8A24A',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Named contacts: maps names → one or more email addresses
-- Used for disambiguation when Marwan types a name in Composer
CREATE TABLE contacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id       UUID REFERENCES entities(id),
    display_name    TEXT NOT NULL,
    email_address   TEXT NOT NULL,
    domain          TEXT GENERATED ALWAYS AS (split_part(email_address, '@', 2)) STORED,
    label           TEXT,                    -- 'TFA work', 'personal', 'Gia'
    is_primary      BOOLEAN DEFAULT false,
    added_by        TEXT DEFAULT 'user',     -- 'user' | 'auto_detected'
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(entity_id, email_address)
);
CREATE INDEX ON contacts(display_name);
CREATE INDEX ON contacts(email_address);
CREATE INDEX ON contacts(entity_id);

CREATE TABLE email_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      TEXT UNIQUE NOT NULL,    -- RFC 2822 Message-ID
    account_id      UUID REFERENCES email_accounts(id),
    thread_id       TEXT,
    in_reply_to     TEXT,
    direction       email_direction NOT NULL,
    from_address    TEXT NOT NULL,
    from_name       TEXT,
    to_addresses    TEXT[] NOT NULL,
    cc_addresses    TEXT[] DEFAULT '{}',
    bcc_addresses   TEXT[] DEFAULT '{}',
    subject         TEXT,
    body_text       TEXT,
    body_html       TEXT,
    snippet         TEXT,
    sent_at         TIMESTAMPTZ NOT NULL,
    received_at     TIMESTAMPTZ,
    is_read         BOOLEAN DEFAULT false,
    is_starred      BOOLEAN DEFAULT false,
    labels          TEXT[] DEFAULT '{}',
    has_attachments BOOLEAN DEFAULT false,
    -- Claude classification
    category        email_category,
    priority        INTEGER CHECK (priority BETWEEN 1 AND 5),
    sentiment       TEXT,
    action_required BOOLEAN DEFAULT false,
    action_summary  TEXT,
    -- Entity + project links
    entity_ids      UUID[] DEFAULT '{}',
    project_ids     UUID[] DEFAULT '{}',
    task_ids        UUID[] DEFAULT '{}',
    -- Embedding
    embedding       VECTOR(384),
    -- Processing state
    processed_at    TIMESTAMPTZ,
    enriched_at     TIMESTAMPTZ,
    raw_path        TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON email_messages(thread_id);
CREATE INDEX ON email_messages(from_address);
CREATE INDEX ON email_messages(sent_at DESC);
CREATE INDEX ON email_messages(category);
CREATE INDEX ON email_messages(action_required) WHERE action_required = true;
CREATE INDEX ON email_messages USING GIN(entity_ids);
CREATE INDEX ON email_messages USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE email_threads (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id       TEXT UNIQUE NOT NULL,
    account_ids     UUID[] DEFAULT '{}',
    subject         TEXT,
    participants    TEXT[] DEFAULT '{}',
    message_count   INTEGER DEFAULT 0,
    first_message_at TIMESTAMPTZ,
    last_message_at  TIMESTAMPTZ,
    -- Classification
    category        email_category,
    status          thread_status DEFAULT 'open',
    open_loop       BOOLEAN DEFAULT false,
    open_loop_since TIMESTAMPTZ,
    days_without_reply INTEGER,
    -- Entity connections
    entity_ids      UUID[] DEFAULT '{}',
    project_ids     UUID[] DEFAULT '{}',
    deal_ids        UUID[] DEFAULT '{}',
    -- Canvas board column (project_id of column, null = Inbox)
    canvas_project_id UUID,
    canvas_position  INTEGER DEFAULT 0,
    -- Claude-generated summary (updated nightly)
    summary         TEXT,
    key_decisions   TEXT[] DEFAULT '{}',
    pending_actions TEXT[] DEFAULT '{}',
    -- New intel signal matched to this thread (for canvas card badge)
    unread_intel_count INTEGER DEFAULT 0,
    embedding       VECTOR(384),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON email_threads(status);
CREATE INDEX ON email_threads(open_loop) WHERE open_loop = true;
CREATE INDEX ON email_threads(canvas_project_id);
CREATE INDEX ON email_threads(last_message_at DESC);

CREATE TABLE email_attachments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id      UUID REFERENCES email_messages(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    mime_type       TEXT,
    size_bytes      INTEGER,
    storage_path    TEXT,
    parsed_text     TEXT,
    embedding       VECTOR(384),
    processed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);


-- ═══════════════════════════════════════════════════════════════════════════════
-- PROJECT MANAGEMENT LAYER
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE projects (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                    TEXT UNIQUE NOT NULL,   -- 'OPP-001', 'GIA-001', 'TFA-Q2'
    name                    TEXT NOT NULL,
    type                    project_type NOT NULL,
    status                  project_status NOT NULL DEFAULT 'active',
    priority                INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    owner_entity_id         UUID REFERENCES entities(id),
    counterparty_entity_ids UUID[] DEFAULT '{}',
    description             TEXT,
    -- Deal-specific (nullable for non-deals)
    deal_stage              deal_stage,
    deal_value_usd          NUMERIC,
    deal_currency           TEXT DEFAULT 'USD',
    -- Timeline
    started_at              TIMESTAMPTZ DEFAULT now(),
    target_close_at         TIMESTAMPTZ,
    closed_at               TIMESTAMPTZ,
    -- Activity tracking
    last_email_at           TIMESTAMPTZ,
    last_activity_at        TIMESTAMPTZ DEFAULT now(),
    open_task_count         INTEGER DEFAULT 0,
    -- Link to legacy RR markdown system
    reddington_ref          TEXT,
    -- Canvas board ordering
    canvas_order            INTEGER DEFAULT 0,
    -- Embedding for project-aware intelligence matching
    embedding               VECTOR(384),
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON projects(type);
CREATE INDEX ON projects(status);
CREATE INDEX ON projects(code);
CREATE INDEX ON projects USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

CREATE TABLE tasks (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID REFERENCES projects(id),
    title                   TEXT NOT NULL,
    description             TEXT,
    status                  task_status NOT NULL DEFAULT 'open',
    priority                INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    -- Assignment
    assigned_to_entity_id   UUID REFERENCES entities(id),
    assigned_by_entity_id   UUID REFERENCES entities(id),
    -- Source tracing
    source_type             TEXT,   -- 'email' | 'manual' | 'briefing' | 'agent'
    source_email_id         UUID REFERENCES email_messages(id),
    source_agent            TEXT,
    -- Dates
    due_at                  TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ,
    -- Delegation tracking
    delegation_email_id     UUID REFERENCES email_messages(id),
    awaiting_reply_from     TEXT,
    -- Metadata
    tags                    TEXT[] DEFAULT '{}',
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON tasks(status) WHERE status != 'done';
CREATE INDEX ON tasks(due_at) WHERE due_at IS NOT NULL;
CREATE INDEX ON tasks(assigned_to_entity_id);
CREATE INDEX ON tasks(project_id);

CREATE TABLE outbound_queue (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_account_id     UUID REFERENCES email_accounts(id),
    from_address        TEXT NOT NULL,
    to_addresses        TEXT[] NOT NULL,
    cc_addresses        TEXT[] DEFAULT '{}',
    bcc_addresses       TEXT[] DEFAULT '{}',
    subject             TEXT NOT NULL,
    body_text           TEXT NOT NULL,
    body_html           TEXT,
    reply_to_message_id TEXT,
    thread_id           TEXT,
    -- Draft metadata
    drafted_by          TEXT DEFAULT 'user',   -- 'postmaster' | 'user' | 'agent'
    draft_prompt        TEXT,
    agent_context       TEXT,
    -- Send control
    status              outbound_status DEFAULT 'draft',
    approved_at         TIMESTAMPTZ,
    scheduled_send_at   TIMESTAMPTZ,
    send_attempts       INTEGER DEFAULT 0,
    last_error          TEXT,
    sent_at             TIMESTAMPTZ,
    sent_message_id     TEXT,
    -- Links
    task_id             UUID REFERENCES tasks(id),
    project_id          UUID REFERENCES projects(id),
    created_at          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON outbound_queue(status) WHERE status IN ('approved', 'sending');


-- ═══════════════════════════════════════════════════════════════════════════════
-- INTELLIGENCE SOURCES
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE newsletter_sources (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    provider            TEXT NOT NULL,   -- 'kpler' | 'platts' | 'bloomberg' | 'sp_global' | 'reuters' | 'other'
    ingestion_method    ingestion_method NOT NULL,
    -- Email forwarding config
    from_address_pattern TEXT,           -- regex matching sender
    forward_to_address  TEXT,
    -- RSS config
    rss_url             TEXT,
    -- Playwright config
    portal_url          TEXT,
    credential_key      TEXT,            -- key in .env (e.g. 'KPLER')
    -- Processing
    last_ingested_at    TIMESTAMPTZ,
    total_ingested      INTEGER DEFAULT 0,
    last_scrape_status  TEXT,            -- 'success' | 'failed' | 'captcha'
    active              BOOLEAN DEFAULT true,
    -- Weighting
    credibility_score   NUMERIC(3,2) DEFAULT 0.80,
    bias_label          TEXT,
    subject_domains     TEXT[] DEFAULT '{}',
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE social_monitors (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        social_platform NOT NULL,
    monitor_type    monitor_type NOT NULL,
    target          TEXT NOT NULL,
    entity_id       UUID REFERENCES entities(id),
    priority        INTEGER DEFAULT 3,
    last_checked_at TIMESTAMPTZ,
    active          BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(platform, monitor_type, target)
);

-- Project-intelligence matching: when an intel item is matched to a project
CREATE TABLE intel_project_matches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID REFERENCES events(id),
    document_id     UUID REFERENCES documents(id),
    project_id      UUID REFERENCES projects(id) NOT NULL,
    thread_id       UUID REFERENCES email_threads(id),
    relevance_score NUMERIC(3,2) NOT NULL,
    match_reason    TEXT,
    surfaced_at     TIMESTAMPTZ DEFAULT now(),
    dismissed_at    TIMESTAMPTZ,
    clicked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ON intel_project_matches(project_id);
CREATE INDEX ON intel_project_matches(relevance_score DESC);
CREATE INDEX ON intel_project_matches(surfaced_at DESC);


-- ═══════════════════════════════════════════════════════════════════════════════
-- AI SYNTHESIS CACHE & USAGE
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE synthesis_cache (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type        TEXT NOT NULL,   -- 'morning_brief' | 'thread_summary' | 'newsletter_synthesis' | 'opportunity_scan' | 'hidden_truth' | 'white_space'
    input_hash      TEXT NOT NULL,   -- SHA256 of input batch
    output_json     JSONB NOT NULL,
    model_used      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    UNIQUE(job_type, input_hash)
);
CREATE INDEX ON synthesis_cache(job_type);
CREATE INDEX ON synthesis_cache(created_at DESC);

CREATE TABLE claude_usage (
    id                      UUID NOT NULL DEFAULT gen_random_uuid(),
    job_type                TEXT NOT NULL,
    called_at               TIMESTAMPTZ DEFAULT now() NOT NULL,
    duration_ms             INTEGER,
    estimated_input_tokens  INTEGER,
    job_source              TEXT,
    success                 BOOLEAN DEFAULT true,
    error_message           TEXT,
    PRIMARY KEY (id, called_at)
);
SELECT create_hypertable('claude_usage', 'called_at', if_not_exists => TRUE);


-- ═══════════════════════════════════════════════════════════════════════════════
-- ECONOMIC TIME-SERIES (from Geo plan)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE economic_indicators (
    entity_id       UUID REFERENCES entities(id) NOT NULL,
    indicator       TEXT NOT NULL,
    value           NUMERIC NOT NULL,
    unit            TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL,
    source_id       UUID REFERENCES sources(id),
    PRIMARY KEY (entity_id, indicator, recorded_at)
);
SELECT create_hypertable('economic_indicators', 'recorded_at', if_not_exists => TRUE);
CREATE INDEX ON economic_indicators(entity_id, indicator, recorded_at DESC);

CREATE TABLE commodity_prices (
    commodity       TEXT NOT NULL,
    price           NUMERIC NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    unit            TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL,
    source_id       UUID REFERENCES sources(id),
    PRIMARY KEY (commodity, recorded_at)
);
SELECT create_hypertable('commodity_prices', 'recorded_at', if_not_exists => TRUE);
CREATE INDEX ON commodity_prices(commodity, recorded_at DESC);


-- ═══════════════════════════════════════════════════════════════════════════════
-- SEED DATA
-- ═══════════════════════════════════════════════════════════════════════════════

-- Marwan's primary email account
INSERT INTO email_accounts (owner_name, email_address, provider, auth_type, is_primary, display_color)
VALUES ('marwan', '014.marwan@gmail.com', 'gmail', 'oauth2', true, '#C8A24A')
ON CONFLICT (email_address) DO NOTHING;

-- Seed newsletter sources (paid + free)
INSERT INTO newsletter_sources (name, provider, ingestion_method, rss_url, credibility_score, bias_label, subject_domains) VALUES
('Reuters World News', 'reuters', 'rss', 'https://feeds.reuters.com/reuters/topNews', 0.90, 'wire', ARRAY['global', 'politics', 'business']),
('Reuters Energy', 'reuters', 'rss', 'https://feeds.reuters.com/reuters/energy', 0.90, 'wire', ARRAY['oil', 'gas', 'energy']),
('Reuters Tech', 'reuters', 'reuters', 'https://feeds.reuters.com/reuters/technologyNews', 0.90, 'wire', ARRAY['tech', 'AI']),
('Al Jazeera English', 'aljazeera', 'rss', 'https://www.aljazeera.com/xml/rss/all.xml', 0.80, 'qatari_state', ARRAY['MENA', 'global', 'politics']),
('BBC News World', 'bbc', 'rss', 'https://feeds.bbci.co.uk/news/world/rss.xml', 0.88, 'british_public', ARRAY['global', 'politics']),
('HackerNews', 'ycombinator', 'rss', 'https://hnrss.org/frontpage', 0.75, 'tech_community', ARRAY['tech', 'AI', 'startup']),
('Kpler Intelligence', 'kpler', 'playwright', NULL, 0.95, 'commodity_data', ARRAY['oil', 'tanker', 'shipping', 'cargo']),
('Platts Oilgram News', 'platts', 'playwright', NULL, 0.95, 'commodity_data', ARRAY['oil', 'gas', 'energy', 'pricing']),
('Bloomberg Energy', 'bloomberg', 'playwright', NULL, 0.92, 'financial_news', ARRAY['oil', 'energy', 'finance', 'markets']),
('S&P Global Commodity Insights', 'sp_global', 'playwright', NULL, 0.93, 'commodity_data', ARRAY['oil', 'gas', 'metals', 'shipping'])
ON CONFLICT DO NOTHING;

-- Seed default social monitors
INSERT INTO social_monitors (platform, monitor_type, target, priority) VALUES
('twitter', 'account', '@kpler_trade', 1),
('twitter', 'account', '@SPGCIoil', 1),
('twitter', 'account', '@pif_en', 1),
('twitter', 'keyword', 'UAE OPEC exit', 1),
('twitter', 'keyword', 'Saudi RHQ', 2),
('twitter', 'keyword', 'Jordan startup', 2),
('twitter', 'keyword', 'MENA venture capital', 2),
('twitter', 'keyword', 'Brent crude', 1),
('twitter', 'keyword', 'ADNOC', 1),
('twitter', 'keyword', 'East Africa oil', 2),
('brave_search', 'search_query', 'UAE oil gas regulatory 2026', 1),
('brave_search', 'search_query', 'Saudi Arabia RHQ operational challenges', 2),
('brave_search', 'search_query', 'Kenya petroleum logistics 2026', 2),
('brave_search', 'search_query', 'Antigua citizenship investment program 2026', 2),
('brave_search', 'search_query', 'MENA fintech funding 2026', 2)
ON CONFLICT (platform, monitor_type, target) DO NOTHING;
