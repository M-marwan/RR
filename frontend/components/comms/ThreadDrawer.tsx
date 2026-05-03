"use client";

import { useEffect, useState } from "react";
import useSWR, { mutate } from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

type Props = {
  threadKey: string | null;
  onClose: () => void;
};

export default function ThreadDrawer({ threadKey, onClose }: Props) {
  const { data, error } = useSWR(
    threadKey ? `/api/email/threads/${threadKey}` : null,
    fetcher
  );
  const { data: team } = useSWR("/api/email/team", fetcher);
  const { data: projects } = useSWR("/api/projects", fetcher);

  const [comment, setComment] = useState("");
  const [sendAsEmail, setSendAsEmail] = useState(true);
  const [toEntityId, setToEntityId] = useState<string>("");
  const [customEmail, setCustomEmail] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<string>("");

  useEffect(() => {
    if (data?.thread?.assigned_to_entity_id) {
      setToEntityId(data.thread.assigned_to_entity_id);
    } else {
      setToEntityId("");
    }
    setComment("");
    setFeedback("");
  }, [threadKey, data?.thread?.assigned_to_entity_id]);

  if (!threadKey) return null;

  const thread = data?.thread;
  const messages = data?.messages || [];

  async function patchThread(body: any) {
    setBusy(true);
    const r = await fetch(`/api/email/threads/${threadKey}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setBusy(false);
    if (r.ok) {
      mutate(`/api/email/threads/${threadKey}`);
      mutate("/api/projects/canvas");
    }
  }

  async function submitComment() {
    if (!comment.trim()) return;
    setBusy(true);
    setFeedback("");
    const r = await fetch(`/api/email/threads/${threadKey}/comment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        body_text: comment,
        send_as_email: sendAsEmail,
        to_entity_id: sendAsEmail && toEntityId && !customEmail ? toEntityId : null,
        to_email: sendAsEmail && customEmail ? customEmail : null,
      }),
    });
    setBusy(false);
    const result = await r.json();
    if (!r.ok) {
      setFeedback(result.detail || "Failed");
      return;
    }
    if (result.saved_as === "email_draft") {
      setFeedback(`Drafted email to ${result.to}. Approve below to send.`);
    } else {
      setFeedback("Saved as internal note.");
    }
    setComment("");
    mutate(`/api/email/threads/${threadKey}`);
    mutate("/api/compose/drafts?status=draft");
    mutate("/api/projects/canvas");
  }

  return (
    <div
      className="fixed inset-0 z-50 flex"
      style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={onClose}
    >
      <div className="ml-auto h-full w-full max-w-2xl flex flex-col"
        style={{ background: "var(--rr-charcoal)", borderLeft: "1px solid var(--rr-border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b flex items-start justify-between gap-4"
          style={{ borderColor: "var(--rr-border)" }}>
          <div className="min-w-0">
            <p className="text-xs mb-1" style={{ color: "var(--rr-dim)" }}>
              {thread?.category || "uncategorized"} ·{" "}
              {thread?.message_count || 0} messages ·{" "}
              {thread?.open_loop ? "OPEN LOOP" : thread?.status}
            </p>
            <h2 className="rr-heading text-lg break-words" style={{ color: "var(--rr-cream)" }}>
              {thread?.subject || "(no subject)"}
            </h2>
            <p className="text-xs mt-1" style={{ color: "var(--rr-subtle)" }}>
              {thread?.participants?.join(", ")}
            </p>
          </div>
          <button onClick={onClose} className="rr-mono text-sm px-2 py-1"
            style={{ color: "var(--rr-dim)" }}>×</button>
        </div>

        {/* Action summary */}
        {thread?.action_summary && (
          <div className="px-6 py-3 text-sm border-b"
            style={{ background: "var(--rr-steel)", color: "var(--rr-cream)", borderColor: "var(--rr-border)" }}>
            <span style={{ color: "var(--rr-brass)" }}>Why: </span>
            {thread.action_summary}
          </div>
        )}

        {/* Controls */}
        <div className="px-6 py-3 border-b flex flex-wrap gap-3 text-xs"
          style={{ borderColor: "var(--rr-border)" }}>
          <select
            value={thread?.canvas_project_id || ""}
            onChange={(e) =>
              patchThread(
                e.target.value
                  ? { canvas_project_id: e.target.value }
                  : { clear_project: true }
              )
            }
            className="px-2 py-1 rounded"
            style={{ background: "var(--rr-steel)", color: "var(--rr-cream)", border: "1px solid var(--rr-border)" }}
          >
            <option value="">Inbox (no project)</option>
            {(projects || []).map((p: any) => (
              <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
            ))}
          </select>

          <select
            value={thread?.assigned_to_entity_id || ""}
            onChange={(e) =>
              patchThread(
                e.target.value
                  ? { assigned_to_entity_id: e.target.value }
                  : { clear_assignee: true }
              )
            }
            className="px-2 py-1 rounded"
            style={{ background: "var(--rr-steel)", color: "var(--rr-cream)", border: "1px solid var(--rr-border)" }}
          >
            <option value="">Unassigned</option>
            {(team || []).map((t: any) => (
              <option key={t.id} value={t.id}>{t.canonical_name}{t.email_address ? ` · ${t.email_address}` : ""}</option>
            ))}
          </select>

          <select
            value={thread?.status || "open"}
            onChange={(e) => patchThread({ status: e.target.value })}
            className="px-2 py-1 rounded"
            style={{ background: "var(--rr-steel)", color: "var(--rr-cream)", border: "1px solid var(--rr-border)" }}
          >
            <option value="open">Open</option>
            <option value="waiting_reply">Waiting reply</option>
            <option value="replied">Replied</option>
            <option value="resolved">Resolved</option>
            <option value="archived">Archived</option>
          </select>

          <button
            onClick={() => patchThread({ hidden_from_inbox: true })}
            className="px-2 py-1 rounded"
            style={{ background: "transparent", color: "var(--rr-dim)", border: "1px solid var(--rr-border)" }}
          >Hide from inbox</button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.map((m: any) => (
            <div key={m.id} className="rr-card p-4">
              <div className="flex items-center justify-between mb-2 text-xs">
                <span style={{ color: m.direction === "outbound" ? "var(--rr-brass)" : "var(--rr-cream)" }}>
                  {m.direction === "outbound" ? "→ " : "← "}
                  {m.from_name || m.from_address}
                </span>
                <span style={{ color: "var(--rr-subtle)" }}>
                  {m.sent_at ? new Date(m.sent_at).toLocaleString() : ""}
                </span>
              </div>
              <pre className="text-sm whitespace-pre-wrap break-words"
                style={{ color: "var(--rr-cream)", fontFamily: "inherit" }}>
                {(m.body_text || m.snippet || "").slice(0, 2000)}
              </pre>
            </div>
          ))}
          {thread?.internal_notes?.length > 0 && (
            <div className="rr-card p-4" style={{ background: "var(--rr-steel)" }}>
              <p className="text-xs mb-2" style={{ color: "var(--rr-brass)" }}>Internal notes</p>
              {thread.internal_notes.map((n: string, i: number) => (
                <p key={i} className="text-sm mb-1" style={{ color: "var(--rr-cream)" }}>· {n}</p>
              ))}
            </div>
          )}
        </div>

        {/* Comment / reply */}
        <div className="px-6 py-4 border-t" style={{ borderColor: "var(--rr-border)", background: "var(--rr-obsidian)" }}>
          <div className="flex items-center gap-3 mb-2 text-xs">
            <label className="flex items-center gap-1 cursor-pointer" style={{ color: "var(--rr-cream)" }}>
              <input type="checkbox" checked={sendAsEmail} onChange={(e) => setSendAsEmail(e.target.checked)} />
              Send as email
            </label>
            {sendAsEmail && (
              <>
                <select
                  value={toEntityId}
                  onChange={(e) => { setToEntityId(e.target.value); setCustomEmail(""); }}
                  className="px-2 py-1 rounded"
                  style={{ background: "var(--rr-steel)", color: "var(--rr-cream)", border: "1px solid var(--rr-border)" }}
                >
                  <option value="">— pick recipient —</option>
                  {(team || []).map((t: any) => (
                    <option key={t.id} value={t.id} disabled={!t.email_address}>
                      {t.canonical_name}{t.email_address ? ` · ${t.email_address}` : " (no email — type below)"}
                    </option>
                  ))}
                </select>
                <span style={{ color: "var(--rr-subtle)" }}>or</span>
                <input
                  type="email"
                  value={customEmail}
                  onChange={(e) => { setCustomEmail(e.target.value); if (e.target.value) setToEntityId(""); }}
                  placeholder="type any email"
                  className="px-2 py-1 rounded text-xs flex-1 min-w-[180px]"
                  style={{ background: "var(--rr-steel)", color: "var(--rr-cream)", border: "1px solid var(--rr-border)" }}
                />
              </>
            )}
          </div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={sendAsEmail ? "Type your reply — will be drafted, you approve before send" : "Internal note (not sent)"}
            rows={4}
            className="w-full px-3 py-2 rounded text-sm"
            style={{ background: "var(--rr-charcoal)", color: "var(--rr-cream)", border: "1px solid var(--rr-border)" }}
          />
          {feedback && (
            <p className="text-xs mt-2" style={{ color: "var(--rr-brass)" }}>{feedback}</p>
          )}
          <div className="flex justify-end gap-2 mt-2">
            <button
              disabled={busy || !comment.trim()}
              onClick={submitComment}
              className="px-3 py-1.5 rounded text-sm"
              style={{
                background: comment.trim() ? "var(--rr-brass)" : "var(--rr-steel)",
                color: comment.trim() ? "var(--rr-obsidian)" : "var(--rr-dim)",
                cursor: comment.trim() ? "pointer" : "not-allowed",
              }}
            >
              {sendAsEmail ? "Draft email" : "Save note"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
