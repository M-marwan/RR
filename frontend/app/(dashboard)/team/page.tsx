"use client";
import useSWR from "swr";
import { apiFetcher } from "@/lib/api";
import { useTelemetry } from "@/lib/hooks/useTelemetry";
export default function TeamView() {
  useTelemetry("team");
  const { data } = useSWR<any[]>("/api/entities?type=person&limit=20", apiFetcher);
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Team View</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Delegations · open asks · recent activity per person</p>
      <div className="grid grid-cols-2 gap-4">
        {(data || []).filter((e: any) => e.canonical_name !== "Marwan").map((person: any) => (
          <div key={person.id} className="rr-card p-4">
            <p className="font-medium mb-1" style={{ color: "var(--rr-cream)" }}>{person.canonical_name}</p>
            <p className="text-xs" style={{ color: "var(--rr-dim)" }}>{person.profile?.role || "—"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
