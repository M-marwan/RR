"use client";
import useSWR from "swr";
const fetcher = (url: string) => fetch(url).then(r => r.json());
export default function Ledger() {
  const { data } = useSWR("/api/projects?status=active&limit=20", fetcher);
  const totalCommitted = (data || []).reduce((acc: number, p: any) => acc + (p.deal_value_usd || 0), 0);
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Ledger</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Capital position · deal economics · Bookkeeper</p>
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Deployable", value: "$5K – $50K", color: "var(--rr-brass)" },
          { label: "Committed", value: `$${(totalCommitted || 0).toLocaleString()}`, color: "var(--rr-text)" },
          { label: "Active deals", value: (data || []).filter((p: any) => p.type === "deal").length.toString(), color: "var(--rr-slate)" },
        ].map(stat => (
          <div key={stat.label} className="rr-card p-5">
            <p className="text-xs mb-1" style={{ color: "var(--rr-dim)" }}>{stat.label}</p>
            <p className="rr-heading text-2xl" style={{ color: stat.color }}>{stat.value}</p>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        {(data || []).filter((p: any) => p.type === "deal").map((deal: any) => (
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
