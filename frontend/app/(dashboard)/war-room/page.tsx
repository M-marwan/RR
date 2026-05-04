"use client";
import useSWR from "swr";
import { apiFetcher } from "@/lib/api";
import { useTelemetry } from "@/lib/hooks/useTelemetry";

const COLS = [
  { key: "open", label: "OPEN", color: "var(--rr-brass)" },
  { key: "in_progress", label: "IN PROGRESS", color: "var(--rr-slate)" },
  { key: "done", label: "DONE", color: "var(--rr-ok)" },
];

export default function WarRoom() {
  useTelemetry("war-room");
  const { data } = useSWR<any[]>("/api/tasks", apiFetcher, { refreshInterval: 60_000 });
  const tasks: any[] = data || [];
  return (
    <div className="h-full overflow-y-auto p-6" style={{ background: "var(--rr-obsidian)" }}>
      <h1 className="rr-heading text-2xl mb-1" style={{ color: "var(--rr-cream)" }}>War Room</h1>
      <p className="text-xs mb-6" style={{ color: "var(--rr-dim)" }}>Tasks · delegations · open loops</p>
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLS.map(col => (
          <div key={col.key} className="flex-shrink-0" style={{ width: "280px" }}>
            <div className="flex items-center gap-2 mb-3">
              <div className="h-0.5 flex-1" style={{ background: col.color, opacity: 0.4 }} />
              <span className="rr-mono text-xs" style={{ color: col.color }}>{col.label}</span>
              <div className="h-0.5 flex-1" style={{ background: col.color, opacity: 0.4 }} />
            </div>
            <div className="space-y-2">
              {tasks.filter(t => t.status === col.key).map(task => (
                <div key={task.id} className="rr-card p-3">
                  <p className="text-sm" style={{ color: "var(--rr-cream)" }}>{task.title}</p>
                  {task.project_code && <p className="rr-mono text-xs mt-1" style={{ color: "var(--rr-brass)" }}>{task.project_code}</p>}
                  {task.due_at && <p className="text-xs mt-1" style={{ color: task.status !== "done" && new Date(task.due_at) < new Date() ? "var(--rr-urgent)" : "var(--rr-dim)" }}>Due {new Date(task.due_at).toLocaleDateString("en-AE", { month: "short", day: "numeric" })}</p>}
                </div>
              ))}
              {tasks.filter(t => t.status === col.key).length === 0 && (
                <p className="text-xs text-center py-6" style={{ color: "var(--rr-subtle)" }}>Empty</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
