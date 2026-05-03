"use client";

import { useState } from "react";
import useSWR from "swr";
import * as Dialog from "@radix-ui/react-dialog";
import { api, apiFetcher, ApiError } from "@/lib/api";
import { INDUSTRIES, type Workspace } from "@/lib/types";

const PRESET_COLORS = [
  "#c8a24a", // brass
  "#7a99a3", // sage
  "#a37a99", // dusk
  "#9aa37a", // olive
  "#a3947a", // sand
  "#7aa39d", // teal
  "#a37a7a", // rose
  "#7a7aa3", // ink
];

export default function CompaniesPage() {
  const { data: workspaces, error, isLoading, mutate } = useSWR<Workspace[]>(
    "/api/workspaces",
    apiFetcher,
  );

  const [editing, setEditing] = useState<Workspace | "new" | null>(null);

  return (
    <div className="h-full overflow-y-auto" style={{ background: "var(--rr-obsidian)" }}>
      <div className="max-w-5xl mx-auto px-8 py-8">
        {/* Header */}
        <div className="flex items-end justify-between mb-2">
          <div>
            <h1 className="rr-heading text-3xl" style={{ color: "var(--rr-cream)" }}>
              Companies
            </h1>
            <p className="text-sm mt-1" style={{ color: "var(--rr-dim)" }}>
              Add a workspace per company you run. Members and email connectors get attached
              to each workspace separately.
            </p>
          </div>
          <button
            onClick={() => setEditing("new")}
            className="rr-mono text-xs uppercase tracking-wider px-4 py-2 rounded transition-colors"
            style={{
              background: "var(--rr-brass)",
              color: "var(--rr-obsidian)",
              border: "none",
              cursor: "pointer",
            }}
          >
            + Add Company
          </button>
        </div>

        <div
          className="rr-mono text-xs mt-4 mb-8 px-3 py-2 rounded"
          style={{
            background: "rgba(200,162,74,0.05)",
            border: "1px solid rgba(200,162,74,0.15)",
            color: "var(--rr-dim)",
          }}
        >
          🏛 Tip — Create one workspace for each legal entity. Mixing entities into one
          workspace makes audit and compliance harder later.
        </div>

        {/* Loading / error / list */}
        {error && <ErrorState error={error} />}
        {isLoading && !workspaces && <LoadingState />}

        {workspaces && workspaces.length === 0 && !error && (
          <EmptyState onAdd={() => setEditing("new")} />
        )}

        {workspaces && workspaces.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {workspaces.map((ws) => (
              <CompanyCard
                key={ws.id}
                workspace={ws}
                onEdit={() => setEditing(ws)}
                onDelete={async () => {
                  if (!confirm(`Archive "${ws.display_name}"? This soft-deletes — data is preserved.`)) return;
                  try {
                    await api.delete(`/api/workspaces/${ws.id}`);
                    mutate();
                  } catch (e: any) {
                    alert(`Failed: ${e.message ?? e}`);
                  }
                }}
              />
            ))}
          </div>
        )}

        {/* Create/edit dialog */}
        <CompanyDialog
          open={editing !== null}
          onClose={() => setEditing(null)}
          mode={editing === "new" ? "create" : editing ? "edit" : "create"}
          workspace={typeof editing === "object" && editing !== null ? editing : undefined}
          onSaved={() => {
            mutate();
            setEditing(null);
          }}
        />
      </div>
    </div>
  );
}

// ─── card ────────────────────────────────────────────────────────────────────

function CompanyCard({
  workspace,
  onEdit,
  onDelete,
}: {
  workspace: Workspace;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const accent = workspace.primary_color || "var(--rr-brass)";
  return (
    <div
      className="rr-card p-5 transition-all hover:shadow-lg cursor-pointer"
      style={{ borderLeft: `3px solid ${accent}` }}
      onClick={onEdit}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3
              className="rr-heading text-lg truncate"
              style={{ color: "var(--rr-cream)" }}
            >
              {workspace.display_name}
            </h3>
            <span className="rr-mono text-xs" style={{ color: "var(--rr-subtle)" }}>
              · {workspace.slug}
            </span>
          </div>
          {workspace.industry && (
            <p className="text-xs" style={{ color: "var(--rr-dim)" }}>
              {workspace.industry}
            </p>
          )}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="rr-mono text-[10px] uppercase tracking-wider px-2 py-1 rounded opacity-50 hover:opacity-100 transition-opacity"
          style={{ color: "var(--rr-urgent)", background: "transparent", border: "1px solid var(--rr-border)" }}
        >
          Archive
        </button>
      </div>

      <div className="flex items-center gap-4 text-xs">
        <span style={{ color: "var(--rr-dim)" }}>
          <span className="rr-mono" style={{ color: "var(--rr-cream)" }}>
            {workspace.member_count ?? 0}
          </span>{" "}
          members
        </span>
        <span style={{ color: "var(--rr-dim)" }}>
          <span className="rr-mono" style={{ color: "var(--rr-cream)" }}>
            {workspace.project_count ?? 0}
          </span>{" "}
          projects
        </span>
        <span className="ml-auto rr-mono text-xs" style={{ color: workspace.m365_tenant_id ? "var(--rr-ok)" : "var(--rr-subtle)" }}>
          {workspace.m365_tenant_id ? "● M365 connected" : "○ M365 not connected"}
        </span>
      </div>
    </div>
  );
}

// ─── dialog ──────────────────────────────────────────────────────────────────

function CompanyDialog({
  open,
  onClose,
  mode,
  workspace,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  mode: "create" | "edit";
  workspace?: Workspace;
  onSaved: () => void;
}) {
  const [slug, setSlug] = useState(workspace?.slug ?? "");
  const [displayName, setDisplayName] = useState(workspace?.display_name ?? "");
  const [industry, setIndustry] = useState(workspace?.industry ?? "");
  const [color, setColor] = useState(workspace?.primary_color ?? PRESET_COLORS[0]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Sync state when the workspace prop changes (e.g. opening a different card)
  // This is intentional — we don't useEffect because Dialog mounts fresh each open.
  if (open && workspace && workspace.id !== undefined && slug !== workspace.slug && !busy) {
    setSlug(workspace.slug);
    setDisplayName(workspace.display_name);
    setIndustry(workspace.industry ?? "");
    setColor(workspace.primary_color ?? PRESET_COLORS[0]);
    setErr(null);
  }

  async function handleSave() {
    setBusy(true);
    setErr(null);
    try {
      if (mode === "create") {
        await api.post<Workspace>("/api/workspaces", {
          slug: slug.toLowerCase().trim(),
          display_name: displayName.trim(),
          industry: industry || undefined,
          primary_color: color,
        });
      } else if (workspace) {
        await api.patch<Workspace>(`/api/workspaces/${workspace.id}`, {
          display_name: displayName.trim(),
          industry: industry || undefined,
          primary_color: color,
        });
      }
      // Reset and close
      setSlug("");
      setDisplayName("");
      setIndustry("");
      setColor(PRESET_COLORS[0]);
      onSaved();
    } catch (e: any) {
      const msg = e instanceof ApiError ? e.detail : (e?.message ?? "Failed to save");
      setErr(msg);
    } finally {
      setBusy(false);
    }
  }

  const slugIsValid = /^[a-z0-9][a-z0-9-]*[a-z0-9]$/.test(slug);
  const canSubmit = displayName.trim().length > 0 && (mode === "edit" || slugIsValid);

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-50"
          style={{ background: "rgba(0,0,0,0.7)" }}
        />
        <Dialog.Content
          className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md p-6 rounded"
          style={{
            background: "var(--rr-charcoal)",
            border: "1px solid var(--rr-border)",
            color: "var(--rr-cream)",
          }}
        >
          <Dialog.Title
            className="rr-heading text-xl mb-1"
            style={{ color: "var(--rr-cream)" }}
          >
            {mode === "create" ? "Add Company" : `Edit ${workspace?.display_name ?? "Company"}`}
          </Dialog.Title>
          <Dialog.Description
            className="text-sm mb-5"
            style={{ color: "var(--rr-dim)" }}
          >
            {mode === "create"
              ? "Create a new workspace. You can add members and connect their email after."
              : "Update workspace metadata. Slug cannot be changed once set."}
          </Dialog.Description>

          <div className="space-y-4">
            <Field
              label="Display name"
              hint="Shown across the dashboard. Use the legal-ish name."
            >
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Gia Industries Holdings"
                className="rr-input w-full"
                disabled={busy}
              />
            </Field>

            <Field
              label="Slug"
              hint={mode === "edit" ? "Permanent. Used in URLs and the API." : "Short ID. Lowercase, hyphens. e.g. 'gia', 'opp-trading'."}
            >
              <input
                value={slug}
                onChange={(e) =>
                  setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))
                }
                placeholder="gia"
                className="rr-input w-full"
                disabled={busy || mode === "edit"}
                style={mode === "edit" ? { opacity: 0.5, cursor: "not-allowed" } : {}}
              />
              {slug && !slugIsValid && mode === "create" && (
                <p className="text-xs mt-1" style={{ color: "var(--rr-warn)" }}>
                  Slug must be lowercase letters/digits with optional hyphens (not at start or end).
                </p>
              )}
            </Field>

            <Field label="Industry">
              <select
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="rr-input w-full"
                disabled={busy}
              >
                <option value="">— Select —</option>
                {INDUSTRIES.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="Accent color" hint="Used as the left border on cards and headers.">
              <div className="flex items-center gap-2 flex-wrap">
                {PRESET_COLORS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    aria-label={`Color ${c}`}
                    style={{
                      background: c,
                      width: "28px",
                      height: "28px",
                      borderRadius: "4px",
                      border: c === color ? "2px solid var(--rr-cream)" : "2px solid transparent",
                      cursor: "pointer",
                    }}
                    disabled={busy}
                  />
                ))}
              </div>
            </Field>

            {err && (
              <div
                className="px-3 py-2 rounded text-sm rr-mono"
                style={{
                  background: "rgba(200,80,80,0.08)",
                  border: "1px solid rgba(200,80,80,0.3)",
                  color: "var(--rr-urgent)",
                }}
              >
                {err}
              </div>
            )}
          </div>

          <div className="flex items-center justify-end gap-2 mt-6">
            <button
              onClick={onClose}
              disabled={busy}
              className="rr-mono text-xs uppercase tracking-wider px-4 py-2 rounded"
              style={{
                background: "transparent",
                border: "1px solid var(--rr-border)",
                color: "var(--rr-dim)",
                cursor: busy ? "not-allowed" : "pointer",
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!canSubmit || busy}
              className="rr-mono text-xs uppercase tracking-wider px-4 py-2 rounded transition-colors"
              style={{
                background: canSubmit && !busy ? "var(--rr-brass)" : "var(--rr-steel)",
                color: canSubmit && !busy ? "var(--rr-obsidian)" : "var(--rr-subtle)",
                border: "none",
                cursor: canSubmit && !busy ? "pointer" : "not-allowed",
              }}
            >
              {busy ? "Saving…" : mode === "create" ? "Create" : "Save"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        className="rr-mono text-[11px] uppercase tracking-wider block mb-1.5"
        style={{ color: "var(--rr-dim)" }}
      >
        {label}
      </label>
      {children}
      {hint && (
        <p className="text-xs mt-1" style={{ color: "var(--rr-subtle)" }}>
          {hint}
        </p>
      )}
    </div>
  );
}

// ─── empty / loading / error ─────────────────────────────────────────────────

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="rr-card p-12 text-center">
      <div
        className="rr-heading text-4xl mb-3"
        style={{ color: "var(--rr-brass)" }}
      >
        ◉
      </div>
      <h2 className="rr-heading text-xl mb-2" style={{ color: "var(--rr-cream)" }}>
        No companies yet
      </h2>
      <p className="text-sm mb-6 max-w-md mx-auto" style={{ color: "var(--rr-dim)" }}>
        Add a workspace for each company you run. The morning brief, comms, and intel will
        aggregate across all of them. You can always filter to one later.
      </p>
      <button
        onClick={onAdd}
        className="rr-mono text-xs uppercase tracking-wider px-6 py-3 rounded"
        style={{
          background: "var(--rr-brass)",
          color: "var(--rr-obsidian)",
          border: "none",
          cursor: "pointer",
        }}
      >
        + Add your first company
      </button>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="text-center py-16">
      <div className="rr-heading text-2xl mb-2" style={{ color: "var(--rr-brass)" }}>◉</div>
      <p className="text-sm" style={{ color: "var(--rr-dim)" }}>Loading workspaces…</p>
    </div>
  );
}

function ErrorState({ error }: { error: any }) {
  const msg =
    error instanceof ApiError
      ? `${error.status} — ${error.detail}`
      : error?.message ?? "Failed to load";
  return (
    <div className="rr-card p-6 text-center">
      <p className="rr-mono text-xs uppercase mb-2" style={{ color: "var(--rr-urgent)" }}>
        Couldn’t load companies
      </p>
      <p className="text-sm" style={{ color: "var(--rr-dim)" }}>{msg}</p>
      <p className="text-xs mt-4" style={{ color: "var(--rr-subtle)" }}>
        Check that the backend is running and that you’ve applied alembic migration 0003.
      </p>
    </div>
  );
}
