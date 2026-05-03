"use client";

import useSWR from "swr";
import { useEffect, useRef, useState } from "react";
import { api, apiFetcher } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  confirmed: "var(--rr-ok)",
  verified: "var(--rr-sage)",
  reported: "var(--rr-brass)",
  alleged: "var(--rr-warn)",
  disputed: "var(--rr-urgent)",
  low_credibility: "var(--rr-subtle)",
};

export default function WirePage() {
  const [liveItems, setLiveItems] = useState<any[]>([]);
  const [streamError, setStreamError] = useState<string | null>(null);
  const { data, isLoading } = useSWR<any[]>(
    "/api/feed?limit=50&min_relevance=0.4",
    apiFetcher,
    { refreshInterval: 120_000 },
  );

  // SSE for real-time additions — unmounts cleanly even on Strict Mode double-invoke
  // and survives transient backend restarts via the api.stream auto-reconnect path.
  const streamRef = useRef<{ close: () => void } | null>(null);
  useEffect(() => {
    const stream = api.stream("/api/feed/stream", {
      onMessage: (item) => {
        if (item && typeof item === "object") {
          setLiveItems((prev) => [item, ...prev.slice(0, 4)]);
        }
      },
      onError: () => {
        setStreamError("Live stream interrupted — falling back to 2-min polling.");
      },
      onOpen: () => setStreamError(null),
    });
    streamRef.current = stream;
    return () => {
      stream.close();
      streamRef.current = null;
    };
  }, []);

  const items = [...liveItems, ...(data || [])];

  return (
    <div className="h-full overflow-y-auto" style={{ background: "var(--rr-obsidian)" }}>
      <div className="max-w-3xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="rr-heading text-2xl" style={{ color: "var(--rr-cream)" }}>The Wire</h1>
            <p className="text-xs mt-0.5" style={{ color: "var(--rr-dim)" }}>
              Global intelligence feed · oil &amp; gas · tech · diplomacy · white space
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="rr-mono text-xs"
              style={{ color: streamError ? "var(--rr-warn)" : "var(--rr-ok)" }}
            >
              {streamError ? "○ polling" : "● live"}
            </span>
          </div>
        </div>

        {streamError && (
          <div
            className="mb-4 px-3 py-2 rounded text-xs rr-mono"
            style={{
              background: "rgba(255,153,0,0.08)",
              border: "1px solid rgba(255,153,0,0.2)",
              color: "var(--rr-warn)",
            }}
          >
            ⏱ {streamError}
          </div>
        )}

        {isLoading && items.length === 0 ? (
          <p className="text-sm text-center py-12" style={{ color: "var(--rr-dim)" }}>
            Loading intelligence feed…
          </p>
        ) : items.length === 0 ? (
          <EmptyWire />
        ) : (
          <div className="space-y-3">
            {items.map((item: any, i: number) => (
              <WireItem key={item.id || i} item={item} isLive={i < liveItems.length} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function WireItem({ item, isLive }: { item: any; isLive: boolean }) {
  const statusColor = STATUS_COLOR[item.status] || "var(--rr-dim)";

  return (
    <div
      className="rr-card p-4 transition-all"
      style={{ borderLeft: `2px solid ${statusColor}` }}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          {/* Headline */}
          <div className="flex items-start gap-2 mb-2">
            {isLive && (
              <span className="rr-mono text-xs px-1 py-0.5 rounded flex-shrink-0" style={{ background: "rgba(68,187,68,0.1)", color: "var(--rr-ok)" }}>
                NEW
              </span>
            )}
            <p className="text-sm font-medium leading-snug" style={{ color: "var(--rr-cream)" }}>
              {item.headline}
            </p>
          </div>

          {/* Summary */}
          {item.summary && (
            <p className="text-xs mb-3 leading-relaxed" style={{ color: "var(--rr-text)" }}>
              {item.summary}
            </p>
          )}

          {/* Footer */}
          <div className="flex items-center gap-4">
            <span
              className="rr-mono text-xs"
              style={{ color: statusColor }}
            >
              {item.status || "reported"}
            </span>
            {item.source_name && (
              <span className="text-xs" style={{ color: "var(--rr-subtle)" }}>
                {item.source_name}
                {item.source_credibility && (
                  <span className="ml-1 rr-mono">({Math.round(item.source_credibility * 100)}%)</span>
                )}
              </span>
            )}
            {item.relevance_score && (
              <span className="rr-mono text-xs" style={{ color: "var(--rr-brass)" }}>
                {Math.round(item.relevance_score * 100)}% relevant
              </span>
            )}
            {item.occurred_at && (
              <span className="ml-auto rr-mono text-xs" style={{ color: "var(--rr-subtle)" }}>
                {new Date(item.occurred_at).toLocaleDateString("en-AE", {
                  timeZone: "Asia/Dubai", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
                })}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyWire() {
  return (
    <div className="rr-card p-8 text-center">
      <p className="rr-heading text-xl mb-2" style={{ color: "var(--rr-dim)" }}>No signals yet</p>
      <p className="text-sm" style={{ color: "var(--rr-subtle)" }}>
        The intelligence feed populates once ingestion workers are running.
        RSS and GDELT workers start in Phase 2.
      </p>
    </div>
  );
}
