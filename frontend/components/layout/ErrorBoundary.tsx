"use client";

import React from "react";

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: React.ErrorInfo;
}

interface Props {
  children: React.ReactNode;
  /** Optional override of the fallback UI. */
  fallback?: (error: Error, reset: () => void) => React.ReactNode;
}

/**
 * Top-level error boundary.
 *
 * Catches render-time errors anywhere in the tree, shows a brand-consistent
 * fallback ("◉ Something broke"), and logs the error + component stack to the
 * browser console. Wraps the dashboard layout so a single page failure doesn't
 * blank the whole shell.
 *
 * Network/API errors thrown from SWR/useEffect aren't caught here — those are
 * handled at the page level via SWR's `error` state. This boundary catches
 * actual JavaScript exceptions during rendering.
 */
export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("RR ErrorBoundary caught:", error, errorInfo);
    this.setState({ errorInfo });
    // TODO Phase 1C: pipe to Sentry via Sentry.captureException(error)
  }

  reset = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }
      return <DefaultFallback error={this.state.error} onReset={this.reset} />;
    }
    return this.props.children;
  }
}

function DefaultFallback({ error, onReset }: { error: Error; onReset: () => void }) {
  const isDev = process.env.NODE_ENV !== "production";
  return (
    <div
      className="h-full flex items-center justify-center p-8"
      style={{ background: "var(--rr-obsidian)" }}
    >
      <div className="rr-card p-8 max-w-lg w-full text-center">
        <div className="rr-heading text-3xl mb-3" style={{ color: "var(--rr-urgent)" }}>
          ◉
        </div>
        <h1 className="rr-heading text-xl mb-2" style={{ color: "var(--rr-cream)" }}>
          Something broke in the room
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--rr-dim)" }}>
          A render error stopped this view. The rest of the dashboard is still alive — try the
          button below or use the rail to switch rooms.
        </p>

        {isDev && (
          <details
            className="text-left mb-6 p-3 rounded"
            style={{ background: "var(--rr-muted)", border: "1px solid var(--rr-border)" }}
          >
            <summary
              className="rr-mono text-xs cursor-pointer mb-2"
              style={{ color: "var(--rr-warn)" }}
            >
              {error.name}: {error.message}
            </summary>
            <pre
              className="rr-mono text-[11px] overflow-auto whitespace-pre-wrap mt-2"
              style={{ color: "var(--rr-subtle)", maxHeight: "200px" }}
            >
              {error.stack}
            </pre>
          </details>
        )}

        <button
          onClick={onReset}
          className="rr-mono text-xs uppercase tracking-wider px-4 py-2 rounded transition-colors"
          style={{
            background: "var(--rr-brass)",
            color: "var(--rr-obsidian)",
            border: "none",
            cursor: "pointer",
          }}
        >
          Reload this room
        </button>
      </div>
    </div>
  );
}

export default ErrorBoundary;
