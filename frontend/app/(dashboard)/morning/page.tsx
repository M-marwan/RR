"use client";

import useSWR from "swr";
import { useState } from "react";
import { api, apiFetcher } from "@/lib/api";
import { useTelemetry } from "@/lib/hooks/useTelemetry";
import { useWorkspaceFilter } from "@/lib/stores/workspaceFilter";
import type {
  Briefing,
  FeedbackVerdict,
  OpenLoop,
  SourceRef,
  ThreeMove,
  WatchlistItem,
} from "@/lib/types";

export default function MorningRoom() {
  useTelemetry("morning");
  const selectedId = useWorkspaceFilter((s) => s.selectedId);
  const url = selectedId
    ? `/api/briefing/today?workspace_id=${selectedId}`
    : "/api/briefing/today";

  const { data, error, isLoading } = useSWR<Briefing>(url, apiFetcher, {
    revalidateOnFocus: false,
    refreshInterval: 300_000, // 5 min
  });

  if (isLoading) return <LoadingState />;
  if (error) return <ErrorState message="Cannot reach backend — is it running?" />;

  const briefing = data?.briefing;
  const briefingId = data?.id ?? null;
  const generationMode = briefing?.generation_mode;

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
          <ModeChip mode={generationMode} source={data?.source} />
        </div>

        {data?.stale_warning && (
          <div className="mb-6 px-4 py-3 rounded text-sm" style={{
            background: "rgba(255,153,0,0.1)",
            border: "1px solid rgba(255,153,0,0.3)",
            color: "var(--rr-warn)",
          }}>
            ⏱ {data.stale_warning}
          </div>
        )}

        {briefing ? (
          <BriefingContent briefing={briefing} briefingId={briefingId} generatedAt={data?.generated_at ?? null} />
        ) : (
          <EmptyState />
        )}
      </div>
    </div>
  );
}

// ─── content ─────────────────────────────────────────────────────────────────

function BriefingContent({
  briefing,
  briefingId,
  generatedAt,
}: {
  briefing: NonNullable<Briefing["briefing"]>;
  briefingId: string | null;
  generatedAt: string | null;
}) {
  const { raymond, open_loops, watchlist, capital_position, withheld } = briefing;

  return (
    <div className="space-y-8">
      {/* Three Moves (deterministic) — always rendered */}
      {raymond?.moves && raymond.moves.length > 0 && (
        <section className="rr-card p-6" style={{ borderLeft: "3px solid var(--rr-brass)" }}>
          <div className="flex items-center gap-2 mb-4">
            <span style={{ color: "var(--rr-brass)" }}>◉</span>
            <h2 className="rr-heading text-xl" style={{ color: "var(--rr-cream)" }}>
              Three Moves
            </h2>
            {generatedAt && (
              <span className="ml-auto rr-mono text-xs" style={{ color: "var(--rr-subtle)" }}>
                {new Date(generatedAt).toLocaleTimeString("en-AE", {
                  timeZone: "Asia/Dubai", hour: "2-digit", minute: "2-digit",
                })} GST
              </span>
            )}
          </div>

          {/* AI synthesis dispatch (only when enable_ai_synthesis=TRUE) */}
          {raymond.dispatch && (
            <div className="mb-6 pb-4 border-b" style={{ borderColor: "var(--rr-border)" }}>
              <p className="text-sm leading-relaxed mb-2" style={{ color: "var(--rr-text)" }}>
                {raymond.dispatch}
              </p>
              <SourceRefList refs={raymond.dispatch_source_refs ?? []} />
              {briefingId && (
                <FeedbackBar briefingId={briefingId} claimPath="raymond.dispatch" />
              )}
            </div>
          )}

          {/* Three moves */}
          <div className="space-y-3">
            {raymond.moves.map((move, i) => (
              <MoveRow
                key={i}
                move={move}
                briefingId={briefingId}
                claimPath={`three_moves[${i}]`}
              />
            ))}
          </div>
        </section>
      )}

      {/* Open Loops */}
      <section className="rr-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <span style={{ color: "var(--rr-slate)" }}>◈</span>
          <h2 className="text-base font-medium" style={{ color: "var(--rr-cream)" }}>Open Loops</h2>
          <span className="rr-mono text-xs" style={{ color: "var(--rr-dim)" }}>— Dembe</span>
        </div>
        {open_loops && open_loops.length > 0 ? (
          <div className="space-y-2">
            {open_loops.map((loop: OpenLoop, i) => (
              <div key={i} className="flex items-center gap-3 text-sm py-2 border-b"
                style={{ borderColor: "var(--rr-muted)" }}>
                <span style={{ color: "var(--rr-urgent)" }}>⏰</span>
                <span style={{ color: "var(--rr-text)" }}>
                  {loop.person ?? loop.person_name ?? "—"}
                </span>
                {(loop.days ?? loop.days_waiting) != null && (
                  <span className="ml-auto rr-mono text-xs" style={{ color: "var(--rr-warn)" }}>
                    {loop.days ?? loop.days_waiting}d waiting
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
        {watchlist && watchlist.length > 0 && (
          <section className="rr-card p-5">
            <div className="flex items-center gap-2 mb-4">
              <span style={{ color: "var(--rr-sage)" }}>⊕</span>
              <h2 className="text-base font-medium" style={{ color: "var(--rr-cream)" }}>Watchlist</h2>
            </div>
            <ul className="space-y-3">
              {watchlist.map((item: WatchlistItem, i) => (
                <li key={i} className="text-sm">
                  <div className="flex items-start gap-2">
                    <span style={{ color: "var(--rr-brass)", marginTop: "2px" }}>›</span>
                    <span style={{ color: "var(--rr-text)" }}>{item.item}</span>
                  </div>
                  <SourceRefList refs={item.source_refs} className="ml-4 mt-1" />
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
                <span style={{ color: "var(--rr-brass)" }}>
                  ${capital_position.deployable_usd ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span style={{ color: "var(--rr-dim)" }}>Committed</span>
                <span style={{ color: "var(--rr-text)" }}>
                  ${(capital_position.committed_usd ?? capital_position.committed ?? 0).toLocaleString()}
                </span>
              </div>
              {capital_position.pipeline_summary && (
                <div className="flex justify-between">
                  <span style={{ color: "var(--rr-dim)" }}>Pipeline</span>
                  <span className="rr-mono text-xs" style={{ color: "var(--rr-dim)" }}>
                    {capital_position.pipeline_summary}
                  </span>
                </div>
              )}
            </div>
          </section>
        )}
      </div>

      {/* Withheld (AI synthesis layer only) */}
      {withheld && (
        <section className="p-4 rounded" style={{
          background: "rgba(200,162,74,0.05)",
          border: "1px solid rgba(200,162,74,0.15)",
        }}>
          <p className="rr-mono text-xs uppercase tracking-wider mb-2" style={{ color: "var(--rr-brass)" }}>
            What Raymond Withheld
          </p>
          <p className="text-sm" style={{ color: "var(--rr-dim)" }}>{withheld}</p>
        </section>
      )}
    </div>
  );
}

// ─── move row with feedback ──────────────────────────────────────────────────

function MoveRow({
  move,
  briefingId,
  claimPath,
}: {
  move: ThreeMove;
  briefingId: string | null;
  claimPath: string;
}) {
  return (
    <div className="flex gap-4 p-3 rounded" style={{ background: "var(--rr-muted)" }}>
      <span
        className="rr-heading text-lg flex-shrink-0 w-6 text-center"
        style={{ color: "var(--rr-brass)" }}
      >
        {move.rank}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium mb-1" style={{ color: "var(--rr-cream)" }}>{move.move}</p>
        {move.rationale && (
          <p className="text-xs" style={{ color: "var(--rr-dim)" }}>{move.rationale}</p>
        )}
        <SourceRefList refs={move.source_refs ?? []} className="mt-2" />
      </div>
      {briefingId && (
        <FeedbackBar briefingId={briefingId} claimPath={claimPath} />
      )}
    </div>
  );
}

// ─── source refs (clickable chips per claim, rule 5.1) ───────────────────────

function SourceRefList({ refs, className }: { refs: SourceRef[]; className?: string }) {
  if (!refs || refs.length === 0) return null;
  return (
    <div className={`flex flex-wrap gap-1 ${className ?? ""}`}>
      {refs.map((r, i) => (
        <span
          key={i}
          className="rr-mono text-[10px] px-1.5 py-0.5 rounded"
          style={{
            background: "rgba(200,162,74,0.08)",
            border: "1px solid rgba(200,162,74,0.2)",
            color: "var(--rr-brass)",
          }}
          title={r.label || `${r.kind}:${r.id}`}
        >
          {r.kind}{r.label ? ` · ${truncate(r.label, 32)}` : ""}
        </span>
      ))}
    </div>
  );
}

function truncate(s: string, n: number) {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

// ─── per-claim feedback (rule 5.13) ──────────────────────────────────────────

function FeedbackBar({
  briefingId,
  claimPath,
}: {
  briefingId: string;
  claimPath: string;
}) {
  const [submitted, setSubmitted] = useState<FeedbackVerdict | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(verdict: FeedbackVerdict) {
    if (busy || submitted) return;
    setBusy(true);
    try {
      await api.post("/api/briefing/feedback", {
        briefing_id: briefingId,
        claim_path: claimPath,
        verdict,
      });
      setSubmitted(verdict);
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn("feedback failed:", e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-start gap-1 flex-shrink-0">
      <FeedbackButton
        active={submitted === "useful"}
        disabled={busy || !!submitted}
        onClick={() => send("useful")}
        label="👍"
        title="This was useful"
      />
      <FeedbackButton
        active={submitted === "wrong"}
        disabled={busy || !!submitted}
        onClick={() => send("wrong")}
        label="👎"
        title="This was wrong"
      />
    </div>
  );
}

function FeedbackButton({
  active,
  disabled,
  onClick,
  label,
  title,
}: {
  active: boolean;
  disabled: boolean;
  onClick: () => void;
  label: string;
  title: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className="text-xs px-1.5 py-0.5 rounded transition-opacity"
      style={{
        background: active ? "rgba(200,162,74,0.15)" : "transparent",
        border: active ? "1px solid var(--rr-brass)" : "1px solid var(--rr-border)",
        opacity: disabled && !active ? 0.3 : 1,
        cursor: disabled ? "default" : "pointer",
      }}
    >
      {label}
    </button>
  );
}

// ─── header chip showing generation mode + freshness ─────────────────────────

function ModeChip({ mode, source }: { mode?: string; source?: string }) {
  if (!source) return null;
  const text =
    source === "computed" && mode === "deterministic" ? "deterministic"
    : source === "computed" && mode === "ai_synthesized" ? "ai-synth"
    : source === "stale" ? "stale"
    : source === "empty" ? "no data"
    : source === "seed" ? "seed"
    : source;
  const color =
    source === "computed" ? "var(--rr-ok)"
    : source === "stale" ? "var(--rr-warn)"
    : source === "empty" ? "var(--rr-subtle)"
    : "var(--rr-dim)";
  return (
    <span
      className="rr-mono text-xs px-2 py-1 rounded"
      style={{
        background: `rgba(68,187,68,0.06)`,
        color,
        border: `1px solid ${color === "var(--rr-ok)" ? "rgba(68,187,68,0.3)" : "var(--rr-border)"}`,
      }}
    >
      {text}
    </span>
  );
}

// ─── states ──────────────────────────────────────────────────────────────────

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
        The morning briefing populates from real signals — open loops, action-required threads, deal stages.
        It will appear once you have email/project data flowing in.
      </p>
      <p className="text-xs mt-4 rr-mono" style={{ color: "var(--rr-subtle)" }}>
        scheduler runs daily at 04:30 GST
      </p>
    </div>
  );
}
