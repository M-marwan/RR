"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

interface Props {
  onClose: () => void;
}

const quickCommands = [
  { label: "Morning Room", route: "/morning", icon: "☀" },
  { label: "Comms Hub — Canvas Board", route: "/comms", icon: "✉" },
  { label: "The Wire — Intelligence Feed", route: "/wire", icon: "⚡" },
  { label: "Deal Pipeline — Concierge", route: "/concierge", icon: "⊞" },
  { label: "Opportunity Radar", route: "/intelligence", icon: "◉" },
  { label: "War Room — Tasks", route: "/war-room", icon: "⊡" },
  { label: "Network — Rolodex", route: "/rolodex", icon: "⊛" },
  { label: "Capital — Ledger", route: "/ledger", icon: "$" },
];

export default function CommandBar({ onClose }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<typeof quickCommands>([]);
  const [agentResponse, setAgentResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!query) {
      setResults(quickCommands);
      return;
    }
    const q = query.toLowerCase();
    setResults(
      quickCommands.filter(
        (c) => c.label.toLowerCase().includes(q) || c.route.includes(q)
      )
    );
  }, [query]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") onClose();
    if (e.key === "Enter" && results.length > 0 && query) {
      // If it's a navigation command, go there
      if (results.length === 1) {
        router.push(results[0].route);
        onClose();
      }
    }
  };

  const handleAgentAsk = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setAgentResponse("Raymond is thinking…");
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
      const data = await res.json();
      if (data.total > 0) {
        const items = [
          ...data.entities.slice(0, 2).map((e: any) => `[${e.type}] ${e.canonical_name}`),
          ...data.projects.slice(0, 2).map((p: any) => `[project] ${p.canonical_name}`),
          ...data.events.slice(0, 2).map((ev: any) => `[event] ${ev.canonical_name}`),
        ];
        setAgentResponse(`Found ${data.total} matches:\n${items.join("\n")}`);
      } else {
        setAgentResponse("No matches found in current data. Try the Wire for live intelligence.");
      }
    } catch {
      setAgentResponse("Search unavailable — check backend connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24"
      style={{ background: "rgba(0,0,0,0.75)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-xl rounded-lg shadow-2xl"
        style={{ background: "var(--rr-steel)", border: "1px solid var(--rr-brass)" }}
      >
        {/* Input */}
        <div className="flex items-center px-4 py-3 border-b" style={{ borderColor: "var(--rr-border)" }}>
          <span style={{ color: "var(--rr-brass)", marginRight: "10px" }}>⌘</span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Raymond, tell me… or navigate to a room"
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: "var(--rr-text)" }}
          />
          {query && (
            <button
              onClick={handleAgentAsk}
              disabled={loading}
              className="text-xs px-3 py-1 rounded"
              style={{
                background: "var(--rr-brass)",
                color: "var(--rr-obsidian)",
              }}
            >
              Ask
            </button>
          )}
        </div>

        {/* Agent response */}
        {agentResponse && (
          <div className="px-4 py-3 border-b text-sm" style={{ borderColor: "var(--rr-border)", color: "var(--rr-text)", whiteSpace: "pre-wrap" }}>
            {agentResponse}
          </div>
        )}

        {/* Quick nav results */}
        <div className="py-2 max-h-80 overflow-y-auto">
          {results.map((item) => (
            <button
              key={item.route}
              onClick={() => { router.push(item.route); onClose(); }}
              className="flex items-center gap-3 w-full px-4 py-2 text-sm text-left transition-colors hover:bg-opacity-50"
              style={{ color: "var(--rr-dim)" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--rr-muted)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span style={{ color: "var(--rr-brass)", width: "20px", textAlign: "center" }}>{item.icon}</span>
              <span style={{ color: "var(--rr-text)" }}>{item.label}</span>
              <span className="ml-auto rr-mono text-xs" style={{ color: "var(--rr-subtle)" }}>{item.route}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
