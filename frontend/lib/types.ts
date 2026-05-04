/**
 * Frontend types mirroring backend Pydantic schemas.
 *
 * Source of truth is `backend/app/api/schemas.py`. When you add a field
 * there, mirror it here. (Future: generate this from FastAPI's OpenAPI.)
 */

export interface Workspace {
  id: string;
  slug: string;
  display_name: string;
  industry?: string | null;
  primary_color?: string | null;
  m365_tenant_id?: string | null;
  m365_consent_granted_at?: string | null;
  archived_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  member_count?: number | null;
  project_count?: number | null;
}

export interface WorkspaceMember {
  id: string;
  workspace_id: string;
  entity_id?: string | null;
  email: string;
  role: "principal" | "exec" | "operator" | "readonly";
  joined_at?: string | null;
  name?: string | null;
}

export interface Me {
  sub?: string | null;
  name?: string | null;
  email?: string | null;
  roles: string[];
  dev_mode: boolean;
  workspaces: Workspace[];
}

// ─── briefing (Phase 1A.2) ──────────────────────────────────────────────────

export interface SourceRef {
  kind: string;       // 'email' | 'thread' | 'task' | 'project' | 'event' | 'document' | 'url' | 'open_loop'
  id: string;
  label?: string | null;
}

export interface ThreeMove {
  rank: number;
  move: string;
  rationale?: string | null;
  source_refs: SourceRef[];
}

export interface OpenLoop {
  person?: string | null;
  person_name?: string | null;
  days?: number | null;
  days_waiting?: number | null;
  thread_id?: string | null;
}

export interface WatchlistItem {
  rank?: number | null;
  item: string;
  source_refs: SourceRef[];
}

export interface CapitalPosition {
  deployable_usd?: string | null;
  deployable_usd_low?: number | null;
  deployable_usd_high?: number | null;
  committed?: number | null;
  committed_usd?: number | null;
  pipeline?: string | null;
  pipeline_summary?: string | null;
}

export interface BriefingPayload {
  date?: string;
  raymond?: {
    dispatch?: string | null;
    dispatch_source_refs: SourceRef[];
    moves: ThreeMove[];
  };
  open_loops: OpenLoop[];
  watchlist: WatchlistItem[];
  capital_position?: CapitalPosition | null;
  withheld?: string | null;
  generation_mode?: "deterministic" | "ai_synthesized";
}

export interface Briefing {
  id?: string | null;
  source?: "computed" | "stale" | "seed" | "empty" | string;
  stale_warning?: string | null;
  briefing?: BriefingPayload | null;
  generated_at?: string | null;
  workspace_id?: string | null;
}

export type FeedbackVerdict = "useful" | "wrong" | "noise";

export const INDUSTRIES = [
  "Oil & Gas — Upstream",
  "Oil & Gas — Midstream",
  "Oil & Gas — Downstream",
  "Oil & Gas — Trading",
  "Tech / SaaS / VC",
  "Real Estate",
  "Diplomacy / Sovereign",
  "Family Office",
  "Hospitality",
  "Other",
] as const;

export type Industry = (typeof INDUSTRIES)[number];
