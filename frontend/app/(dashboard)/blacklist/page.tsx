"use client";
import useSWR from "swr";
import { useState } from "react";
import { apiFetcher } from "@/lib/api";
import { useTelemetry } from "@/lib/hooks/useTelemetry";

export default function Blacklist() {
  useTelemetry("blacklist");
  const [q, setQ] = useState("");
  const { data } = useSWR<any[]>(`/api/entities?q=${encodeURIComponent(q)}&limit=30`, apiFetcher);
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Blacklist</h1>
      <p className="text-xs mb-4" style={{ color: "var(--rr-dim)" }}>Entity dossiers · people · companies · countries</p>
      <input
        value={q}
        onChange={e => setQ(e.target.value)}
        placeholder="Search entities…"
        className="w-full px-4 py-2 rounded text-sm mb-6 outline-none"
        style={{ background: "var(--rr-steel)", border: "1px solid var(--rr-border)", color: "var(--rr-text)" }}
      />
      <div className="space-y-2">
        {(data || []).map((e: any) => (
          <div key={e.id} className="rr-card p-4 flex items-center gap-4">
            <span className="rr-mono text-xs px-2 py-1 rounded" style={{ background: "var(--rr-muted)", color: "var(--rr-brass)", minWidth: "60px", textAlign: "center" }}>{e.type}</span>
            <div>
              <p className="font-medium" style={{ color: "var(--rr-cream)" }}>{e.canonical_name}</p>
              {e.country_code && <p className="text-xs" style={{ color: "var(--rr-dim)" }}>{e.country_code}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
