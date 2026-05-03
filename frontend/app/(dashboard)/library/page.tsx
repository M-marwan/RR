"use client";
import useSWR from "swr";
const fetcher = (url: string) => fetch(url).then(r => r.json());
const SECTORS = [
  { label: "Oil & Gas", icon: "⛽", key: "oil" },
  { label: "Technology / AI", icon: "◉", key: "tech" },
  { label: "Diplomacy / Politics", icon: "⊕", key: "politics" },
  { label: "Finance & Capital Markets", icon: "$", key: "finance" },
  { label: "MENA Venture Capital", icon: "◇", key: "mena_vc" },
  { label: "Emerging Markets", icon: "⊛", key: "emerging" },
];
export default function Library() {
  const { data } = useSWR("/api/intelligence/synthesis?job_type=newsletter_synthesis&limit=6", fetcher);
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Library</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Sector intelligence · global synthesis from paid sources</p>
      <div className="grid grid-cols-2 gap-4">
        {SECTORS.map((sector) => {
          const latest = (data || []).find((d: any) => d.output_json?.sector === sector.key);
          return (
            <div key={sector.key} className="rr-card p-5">
              <div className="flex items-center gap-2 mb-3">
                <span style={{ color: "var(--rr-brass)" }}>{sector.icon}</span>
                <h3 className="text-sm font-medium" style={{ color: "var(--rr-cream)" }}>{sector.label}</h3>
              </div>
              {latest ? (
                <p className="text-xs leading-relaxed" style={{ color: "var(--rr-text)" }}>
                  {latest.output_json?.summary || "Synthesis available — see Intelligence Room."}
                </p>
              ) : (
                <p className="text-xs" style={{ color: "var(--rr-subtle)" }}>
                  Awaiting paid source ingestion (Phase 4).
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
