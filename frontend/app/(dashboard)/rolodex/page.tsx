"use client";
import useSWR from "swr";
const fetcher = (url: string) => fetch(url).then(r => r.json());
export default function Rolodex() {
  const { data } = useSWR("/api/entities?type=person&limit=50", fetcher);
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Rolodex</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Network · relationships · Five Coffees</p>
      <div className="grid grid-cols-3 gap-3">
        {(data || []).map((person: any) => (
          <div key={person.id} className="rr-card p-4 cursor-pointer" style={{ transition: "border-color 0.15s" }}>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-8 h-8 rounded-full flex items-center justify-center rr-heading" style={{ background: "var(--rr-muted)", color: "var(--rr-brass)", fontSize: "16px" }}>
                {person.canonical_name?.[0] || "?"}
              </div>
              <p className="font-medium" style={{ color: "var(--rr-cream)" }}>{person.canonical_name}</p>
            </div>
            <p className="text-xs" style={{ color: "var(--rr-dim)" }}>{person.profile?.role || "—"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
