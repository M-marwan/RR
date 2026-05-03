"use client";
export default function MapRoom() {
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>Map Room</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Geopolitical overlays · global intelligence map (Phase 2)</p>
      <div className="rr-card p-8 text-center">
        <p className="rr-heading text-xl mb-2" style={{ color: "var(--rr-dim)" }}>MapLibre GL integration</p>
        <p className="text-sm" style={{ color: "var(--rr-subtle)" }}>World map with entity overlays, signal origins, and geopolitical zones loads in Phase 2.</p>
      </div>
    </div>
  );
}
