"use client";

import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function MorningRoom() {
  const { data, error, isLoading } = useSWR("/api/briefing/today", fetcher, {
    revalidateOnFocus: false,
    refreshInterval: 300_000, // refresh every 5 min
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message="Cannot reach backend — is it running?" />;

  const { briefing, source, stale_warning, generated_at } = data || {};

  return (
    <div className="h-full overflow-y-auto" style={{ background: "var(--rr-obsidian)" }}>
      <div className="max-w-4xl mx-auto px-6 py-8">

        {/* Header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="rr-heading text-3xl mb-1" style={{ color: "var(--rr-cream)" }}>
              Morning Room
            </h1>
            <p className="text-sm" style={{ color: "var(--rr-dim)" }}>
              {new Date().toLocaleDateString("en-AE", {
                timeZone: "Asia/Dubai",
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>
          {source && (
            <span
              className="rr-mono text-xs px-2 py-1 rounded"
              style={{
                background: source === "cache" ? "rgba(68,187,68,0.1)" : "rgba(255,153,0,0.1)",
                color: source === "cache" ? "var(--rr-ok)" : "var(--rr-warn)",
                border: `1px solid ${source === "cache" ? "rgba(68,187,68,0.3)" : "rgba(255,153,0,0.3)"}`,
              }}
            >
              {source === "cache" ? "✓ live" : source === "seed" ? "seed data" : "stale"}
            </span>
          )}
        </div>

        {stale_warning && (
          <div className="mb-6 px-4 py-3 rounded text-sm" style={{
            background: "rgba(255,153,0,0.1)", border: "1px solid rgba(255,153,0,0.3)", color: "var(--rr-warn)"
          }}>
            ⏱ {stale_warning}
          </div>
        )}

        {briefing ? (
          <BriefingContent briefing={briefing} generatedAt={generated_at} />
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  );
}

function BriefingContent({ briefing, generatedAt }: { briefing: any; generatedAt: string | null }) {
  const { raymond, open_loops, watchlist, capital_position, withheld } = briefing;

  return (
    <div className="space-y-8">
      {/* Raymond's Dispatch */}
      {raymond && (
        <section className="rr-card p-6" style={{ borderLeft: "3px solid var(--rr-brass)" }}>
          <div className="flex items-center gap-2 mb-4">
            <span style={{ color: "var(--rr-brass)" }}>◉</span>
            <h2 className="rr-heading text-xl" style={{ color: "var(--rr-cream)" }}>Raymond</h2>
            {generatedAt && (
              <span className="ml-auto rr-mono text-xs" style={{ color: "var(--rr-subtle)" }}>
                {new Date(generatedAt).toLocaleTimeString("en-AE", { timeZone: "Asia/Dubai", hour: "2-digit", minute: "2-digit" })} GST
              </span>
            )}
          </div>
          <p className="text-sm leading-relaxed mb-6" style={{ color: "var(--rr-text)" }}>
            {raymond.dispatch}
          </p>

          {/* Three Moves */}
          {raymond.moves && (
            <div className="space-y-3">
              <p className="rr-mono text-xs uppercase tracking-wider" style={{ color: "var(--rr-dim)" }}>
                Three Moves
              </p>
              {raymond.moves.map((move: any, i: number) => (
                <div key={i} className="flex gap-4 p-3 rounded" style={{ background: "var(--rr-muted)" }}>
                  <span
                    className="rr-heading text-lg flex-shrink-0 w-6 text-center"
                    style={{ color: "var(--rr-brass)" }}
                  >
                    {move.rank}
                  </span>
                  <div>
                    <p className="text-sm font-medium mb-1" style={{ color: "var(--rr-cream)" }}>{move.move}</p>
                    <p className="text-xs" style={{ color: "var(--rr-dim)" }}>{move.rationale}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Open Loops (Dembe) */}
      <section className="rr-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <span style={{ color: "var(--rr-slate)" }}>◈</span>
          <h2 className="text-base font-medium" style={{ color: "var(--rr-cream)" }}>Open Loops</h2>
          <span className="rr-mono text-xs" style={{ color: "var(--rr-dim)" }}>— Dembe</span>
        </div>
        {open_loops && open_loops.length > 0 ? (
          <div className="space-y-2">
            {open_loops.map((loop: any, i: number) => (
              <div key={i} className="flex items-center gap-3 text-sm py-2 border-b" style={{ borderColor: "var(--rr-muted)" }}>
                <span style={{ color: "var(--rr-urgent)" }}>⏰</span>
                <span style={{ color: "var(--rr-text)" }}>{loop.person || loop}</span>
                {loop.days && (
                  <span className="ml-auto rr-mono text-xs" style={{ color: "var(--rr-warn)" }}>
                    {loop.days}d waiting
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm" style={{ color: "var(--rr-subtle)" }}>No open loops. Clean slate.</p>
        )}
      </section>

      <div className="grid grid-cols-2 gap-6">
        {/* Watchlist */}
        {watchlist && (
          <section className="rr-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <span style={{ color: "var(--rr-sage)" }}>⊕</span>
              <h2 className="text-base font-medium" style={{ color: "var(--rr-cream)" }}>Watchlist</h2>
            </div>
            <ul className="space-y-2">
              {watchlist.map((item: string, i: number) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span style={{ color: "var(--rr-brass)", marginTop: "2px" }}>›</span>
                  <span style={{ color: "var(--rr-text)" }}>{item}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Capital Position */}
        {capital_position && (
          <section className="rr-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <span style={{ color: "var(--rr-brass)" }}>$</span>
              <h2 className="text-base font-medium" style={{ color: "var(--rr-cream)" }}>Capital</h2>
              <span className="rr-mono text-xs" style={{ color: "var(--rr-dim)" }}>— Bookkeeper</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span style={{ color: "var(--rr-dim)" }}>Deployable</span>
                <span style={{ color: "var(--rr-brass)" }}>${capital_position.deployable_usd}</span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: "var(--rr-dim)" }}>Committed</span>
                <span style={{ color: "var(--rr-text)" }}>${capital_position.committed?.toLocaleString() ?? 0}</span>
              </div>
              {capital_position.pipeline && (
                <div className="flex justify-between">
                  <span style={{ color: "var(--rr-dim)" }}>Pipeline</span>
                  <span className="rr-mono text-xs" style={{ color: "var(--rr-dim)" }}>{capital_position.pipeline}</span>
                </div>
              )}
            </div>
          </section>
        )}
      </div>

      {/* What Raymond Withheld */}
      {withheld && (
        <section className="p-4 rounded" style={{ background: "rgba(200,162,74,0.05)", border: "1px solid rgba(200,162,74,0.15)" }}>
          <p className="rr-mono text-xs uppercase tracking-wider mb-2" style={{ color: "var(--rr-brass)" }}>
            What Raymond Withheld
          </p>
          <p className="text-sm" style={{ color: "var(--rr-dim)" }}>{withheld}</p>
        </section>
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="h-full flex items-center justify-center">
      <div className="text-center">
        <div className="rr-heading text-2xl mb-2" style={{ color: "var(--rr-brass)" }}>◉</div>
        <p className="text-sm" style={{ color: "var(--rr-dim)" }}>Retrieving morning dispatch…</p>
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="h-full flex items-center justify-center p-8">
      <div className="rr-card p-6 max-w-md text-center">
        <p className="rr-mono text-xs uppercase mb-2" style={{ color: "var(--rr-urgent)" }}>Connection Error</p>
        <p className="text-sm" style={{ color: "var(--rr-dim)" }}>{message}</p>
        <p className="text-xs mt-4" style={{ color: "var(--rr-subtle)" }}>
          Start backend: <code className="rr-mono">uvicorn app.main:app --reload</code>
        </p>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rr-card p-8 text-center">
      <p className="rr-heading text-xl mb-2" style={{ color: "var(--rr-dim)" }}>No briefing yet</p>
      <p className="text-sm" style={{ color: "var(--rr-subtle)" }}>
        The morning briefing generates at 05:30 GST. First run requires seeding the database.
      </p>
      <p className="text-xs mt-4 rr-mono" style={{ color: "var(--rr-subtle)" }}>
        python scripts/seed_from_rr.py
      </p>
    </div>
  );
}
