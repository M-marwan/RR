"use client";
import useSWR from "swr";
import { apiFetcher } from "@/lib/api";
import { useTelemetry } from "@/lib/hooks/useTelemetry";
export default function IntelligencePage() {
  useTelemetry("intelligence");
  const { data, isLoading } = useSWR<any[]>("/api/intelligence/synthesis?job_type=hidden_truth&limit=10", apiFetcher, { refreshInterval: 300_000 });
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Intelligence Room</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Hidden Truth Engine · Opportunity Radar · Cross-source patterns</p>
      {isLoading ? (
        <p className="text-sm" style={{ color: "var(--rr-dim)" }}>Loading synthesis…</p>
      ) : (data || []).length === 0 ? (
        <div className="rr-card p-8 text-center">
          <p className="rr-heading text-xl mb-2" style={{ color: "var(--rr-dim)" }}>No synthesis yet</p>
          <p className="text-sm" style={{ color: "var(--rr-subtle)" }}>Hidden Truth Engine runs nightly at 02:00 GST after Phase 2 ingestion workers are active.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {(data || []).map((item: any) => (
            <div key={item.id} className="rr-card p-5" style={{ borderLeft: "2px solid var(--rr-brass)" }}>
              <p className="rr-mono text-xs mb-3" style={{ color: "var(--rr-dim)" }}>
                {new Date(item.created_at).toLocaleDateString("en-AE", { timeZone: "Asia/Dubai", month: "short", day: "numeric" })}
                {" · "}hidden truth synthesis
              </p>
              {item.output_json?.hidden_observations?.map((obs: string, i: number) => (
                <div key={i} className="mb-3 p-3 rounded" style={{ background: "var(--rr-muted)" }}>
                  <p className="text-sm" style={{ color: "var(--rr-text)" }}>{obs}</p>
                </div>
              ))}
              {item.output_json?.marwan_specific_translations?.map((t: string, i: number) => (
                <div key={i} className="mb-2 pl-3" style={{ borderLeft: "2px solid var(--rr-brass)" }}>
                  <p className="text-sm" style={{ color: "var(--rr-cream)" }}>{t}</p>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
