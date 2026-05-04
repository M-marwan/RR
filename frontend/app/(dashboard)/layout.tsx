"use client";

import { useState } from "react";
import Rail from "@/components/layout/Rail";
import CommandBar from "@/components/layout/CommandBar";
import ErrorBoundary from "@/components/layout/ErrorBoundary";
import WorkspaceFilter from "@/components/layout/WorkspaceFilter";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [commandOpen, setCommandOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--rr-obsidian)" }}>
      {/* Left rail navigation */}
      <Rail />

      {/* Main viewport */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Top bar */}
        <header
          className="flex items-center justify-between px-4 border-b"
          style={{
            height: "44px",
            background: "var(--rr-charcoal)",
            borderColor: "var(--rr-border)",
            flexShrink: 0,
          }}
        >
          <div className="flex items-center min-w-0">
            <button
              onClick={() => setCommandOpen(true)}
              className="flex items-center gap-2 px-3 py-1 rounded text-sm transition-colors flex-shrink-0"
              style={{
                background: "var(--rr-steel)",
                border: "1px solid var(--rr-border)",
                color: "var(--rr-dim)",
              }}
            >
              <span style={{ color: "var(--rr-brass)" }}>⌘</span>
              <span>Raymond, tell me…</span>
              <span className="ml-4 text-xs" style={{ color: "var(--rr-subtle)" }}>⌘K</span>
            </button>
            <WorkspaceFilter />
          </div>

          <div className="flex items-center gap-4 rr-mono text-xs flex-shrink-0" style={{ color: "var(--rr-dim)" }}>
            <span id="ticker-brent">BRENT —</span>
            <span id="ticker-dxy">DXY —</span>
            <span style={{ color: "var(--rr-subtle)" }}>
              {new Date().toLocaleDateString("en-AE", {
                timeZone: "Asia/Dubai",
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <ErrorBoundary>{children}</ErrorBoundary>
        </main>
      </div>

      {/* Command bar overlay */}
      {commandOpen && (
        <CommandBar onClose={() => setCommandOpen(false)} />
      )}
    </div>
  );
}
