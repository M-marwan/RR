"use client";
import useSWR, { mutate } from "swr";
import { useState } from "react";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function OutboxPanel() {
  const { data: drafts } = useSWR("/api/compose/drafts?status=draft", fetcher, { refreshInterval: 5000 });
  const { data: queued } = useSWR("/api/compose/drafts?status=approved", fetcher, { refreshInterval: 5000 });
  const { data: sent } = useSWR("/api/compose/drafts?status=sent", fetcher, { refreshInterval: 10000 });
  const [open, setOpen] = useState(true);

  async function approve(id: string) {
    await fetch(`/api/compose/approve/${id}`, { method: "POST" });
    mutate("/api/compose/drafts?status=draft");
    mutate("/api/compose/drafts?status=approved");
  }

  async function sendNow() {
    await fetch("/api/admin/email/send-approved", { method: "POST" });
    mutate("/api/compose/drafts?status=approved");
    mutate("/api/compose/drafts?status=sent");
  }

  const draftCount = drafts?.length || 0;
  const queuedCount = queued?.length || 0;

  if (!open) {
    return (
      <button onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-30 rr-card px-4 py-2 text-sm flex items-center gap-2"
        style={{ color: "var(--rr-cream)" }}>
        <span style={{ color: "var(--rr-brass)" }}>Outbox</span>
        {draftCount > 0 && <span style={{ color: "var(--rr-urgent)" }}>{draftCount} drafts</span>}
        {queuedCount > 0 && <span style={{ color: "var(--rr-ok)" }}>{queuedCount} queued</span>}
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-30 rr-card p-3 w-96 max-h-[60vh] overflow-y-auto"
      style={{ background: "var(--rr-charcoal)", border: "1px solid var(--rr-border)" }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="rr-heading text-sm" style={{ color: "var(--rr-cream)" }}>Outbox</h3>
        <button onClick={() => setOpen(false)} className="text-sm" style={{ color: "var(--rr-dim)" }}>−</button>
      </div>

      {draftCount === 0 && queuedCount === 0 && (
        <p className="text-xs" style={{ color: "var(--rr-subtle)" }}>No pending emails.</p>
      )}

      {drafts?.map((d: any) => (
        <div key={d.id} className="mb-3 p-2 rounded" style={{ background: "var(--rr-steel)", border: "1px solid var(--rr-border)" }}>
          <p className="text-xs mb-1" style={{ color: "var(--rr-brass)" }}>DRAFT → {d.to_addresses?.join(", ")}</p>
          <p className="text-sm mb-1" style={{ color: "var(--rr-cream)" }}>{d.subject}</p>
          <p className="text-xs mb-2" style={{ color: "var(--rr-dim)" }}>{d.body_text?.slice(0, 200)}</p>
          <button
            onClick={() => approve(d.id)}
            className="text-xs px-2 py-1 rounded"
            style={{ background: "var(--rr-brass)", color: "var(--rr-obsidian)" }}
          >Approve & queue</button>
        </div>
      ))}

      {queued?.map((d: any) => (
        <div key={d.id} className="mb-2 p-2 rounded" style={{ background: "var(--rr-steel)", border: "1px solid var(--rr-ok)" }}>
          <p className="text-xs" style={{ color: "var(--rr-ok)" }}>QUEUED → {d.to_addresses?.join(", ")}</p>
          <p className="text-xs" style={{ color: "var(--rr-cream)" }}>{d.subject}</p>
        </div>
      ))}

      {(queuedCount > 0) && (
        <button onClick={sendNow}
          className="w-full text-xs px-2 py-2 rounded mt-2"
          style={{ background: "var(--rr-ok)", color: "var(--rr-obsidian)" }}>
          Send {queuedCount} queued now
        </button>
      )}

      {sent?.length > 0 && (
        <details className="mt-3">
          <summary className="text-xs cursor-pointer" style={{ color: "var(--rr-dim)" }}>
            Recently sent ({sent.length})
          </summary>
          {sent.slice(0, 5).map((d: any) => (
            <p key={d.id} className="text-xs mt-1" style={{ color: "var(--rr-subtle)" }}>
              ✓ {d.subject?.slice(0, 50)}
            </p>
          ))}
        </details>
      )}
    </div>
  );
}
