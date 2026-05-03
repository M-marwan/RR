"use client";
import useSWR from "swr";
const fetcher = (url: string) => fetch(url).then(r => r.json());
const STAGE_COLOR: Record<string, string> = {
  prospecting: "var(--rr-subtle)",
  first_touch: "var(--rr-slate)",
  due_diligence: "var(--rr-brass)",
  term_sheet: "var(--rr-warn)",
  closing: "var(--rr-ok)",
};
export default function ConciergePage() {
  const { data } = useSWR("/api/projects?type=deal", fetcher, { refreshInterval: 60_000 });
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Concierge</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Deal pipeline · active opportunities</p>
      <div className="space-y-3">
        {(data || []).map((deal: any) => (
          <div key={deal.id} className="rr-card p-4 flex items-center gap-4">
            <div className="rr-mono text-xs px-2 py-1 rounded" style={{ background: "var(--rr-muted)", color: "var(--rr-brass)" }}>{deal.code}</div>
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate" style={{ color: "var(--rr-cream)" }}>{deal.name}</p>
              <p className="text-xs line-clamp-1" style={{ color: "var(--rr-dim)" }}>{deal.description}</p>
            </div>
            <div className="text-xs rr-mono" style={{ color: STAGE_COLOR[deal.deal_stage] || "var(--rr-subtle)" }}>
              {(deal.deal_stage || deal.status || "").replace(/_/g, " ").toUpperCase()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
