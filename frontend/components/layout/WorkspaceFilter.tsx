"use client";

import useSWR from "swr";
import { apiFetcher } from "@/lib/api";
import { useWorkspaceFilter } from "@/lib/stores/workspaceFilter";
import type { Me, Workspace } from "@/lib/types";

/**
 * Header chip selector — flips between "All companies" (cross-portfolio) and
 * any single workspace the user belongs to. Persists selection via the
 * useWorkspaceFilter zustand store (localStorage-backed).
 *
 * Hidden when the user has zero workspaces (empty state) or only one
 * (no point showing chips for a single option).
 */
export default function WorkspaceFilter() {
  const { selectedId, setSelected } = useWorkspaceFilter();
  const { data: me } = useSWR<Me>("/api/me", apiFetcher, { revalidateOnFocus: false });

  const workspaces: Workspace[] = me?.workspaces ?? [];

  if (workspaces.length === 0) return null;

  return (
    <div className="flex items-center gap-1 ml-4 overflow-x-auto" style={{ maxWidth: "60vw" }}>
      <Chip
        active={selectedId === null}
        accent={undefined}
        onClick={() => setSelected(null)}
        label="All"
        sublabel={`${workspaces.length} cos`}
      />
      {workspaces.map((ws) => (
        <Chip
          key={ws.id}
          active={selectedId === ws.id}
          accent={ws.primary_color || undefined}
          onClick={() => setSelected(ws.id)}
          label={ws.display_name}
          sublabel={ws.slug}
        />
      ))}
    </div>
  );
}

function Chip({
  active,
  accent,
  label,
  sublabel,
  onClick,
}: {
  active: boolean;
  accent?: string;
  label: string;
  sublabel?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="rr-mono text-[11px] uppercase tracking-wider px-2.5 py-1 rounded transition-colors flex-shrink-0"
      style={{
        background: active ? "var(--rr-steel)" : "transparent",
        border: active
          ? `1px solid ${accent || "var(--rr-brass)"}`
          : "1px solid var(--rr-border)",
        color: active ? "var(--rr-cream)" : "var(--rr-dim)",
        cursor: "pointer",
        whiteSpace: "nowrap",
      }}
      title={sublabel}
    >
      {accent && (
        <span
          style={{
            display: "inline-block",
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            background: accent,
            marginRight: "6px",
            verticalAlign: "middle",
          }}
        />
      )}
      {label}
    </button>
  );
}
