"use client";
import useSWR from "swr";
const fetcher = (url: string) => fetch(url).then(r => r.json());
export default function Vault() {
  const { data } = useSWR("/api/projects?type=venture", fetcher);
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Vault</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Active ventures · Gia portfolio · venture ideas</p>
      <div className="grid grid-cols-2 gap-4">
        {(data || []).map((v: any) => (
          <div key={v.id} className="rr-card p-5" style={{ borderTop: "2px solid var(--rr-brass)" }}>
            <div className="flex items-center gap-2 mb-2">
              <span className="rr-mono text-xs" style={{ color: "var(--rr-brass)" }}>{v.code}</span>
              <span className="text-xs" style={{ color: "var(--rr-dim)" }}>{v.status}</span>
            </div>
            <p className="font-medium mb-2" style={{ color: "var(--rr-cream)" }}>{v.name}</p>
            <p className="text-xs leading-relaxed" style={{ color: "var(--rr-dim)" }}>{v.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
