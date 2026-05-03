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
