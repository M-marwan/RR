"use client";
import useSWR from "swr";
import { apiFetcher } from "@/lib/api";
import { useTelemetry } from "@/lib/hooks/useTelemetry";
import { useWorkspaceFilter } from "@/lib/stores/workspaceFilter";
import type { Briefing } from "@/lib/types";

export default function Ledger() {
  useTelemetry("ledger");
  const selectedId = useWorkspaceFilter((s) => s.selectedId);

  // Pull deals
  const { data: projects } = useSWR<any[]>("/api/projects?status=active&limit=20", apiFetcher);

  // Pull capital_position via the briefing endpoint (avoids new endpoint)
  const briefingUrl = selectedId
    ? `/api/briefing/today?workspace_id=${selectedId}`
    : "/api/briefing/today";
  const { data: briefing } = useSWR<Briefing>(briefingUrl, apiFetcher);

  const deals = (projects || []).filter((p: any) => p.type === "deal");
  const totalCommitted = deals.reduce((acc: number, p: any) => acc + (p.deal_value_usd || 0), 0);
  const cap = briefing?.briefing?.capital_position;
  const deployable = cap?.deployable_usd
    ? `$${cap.deployable_usd}`
    : (cap?.deployable_usd_low != null && cap?.deployable_usd_high != null)
        ? `$${cap.deployable_usd_low.toLocaleString()} – $${cap.deployable_usd_high.toLocaleString()}`
        : "—";

  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Ledger</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Capital position · deal economics · Bookkeeper</p>
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Deployable", value: deployable, color: "var(--rr-brass)" },
          { label: "Committed", value: `$${totalCommitted.toLocaleString()}`, color: "var(--rr-text)" },
          { label: "Active deals", value: deals.length.toString(), color: "var(--rr-slate)" },
        ].map(stat => (
          <div key={stat.label} className="rr-card p-5">
            <p className="text-xs mb-1" style={{ color: "var(--rr-dim)" }}>{stat.label}</p>
            <p className="rr-heading text-2xl" style={{ color: stat.color }}>{stat.value}</p>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        {deals.map((deal: any) => (
          <div key={deal.id} className="rr-card p-3 flex items-center gap-4">
            <span className="rr-mono text-xs" style={{ color: "var(--rr-brass)" }}>{deal.code}</span>
            <span className="text-sm flex-1" style={{ color: "var(--rr-cream)" }}>{deal.name}</span>
            {deal.deal_value_usd && <span className="rr-mono text-xs" style={{ color: "var(--rr-ok)" }}>${deal.deal_value_usd.toLocaleString()}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
