"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import ThreadDrawer from "@/components/comms/ThreadDrawer";
import OutboxPanel from "@/components/comms/OutboxPanel";
import { api, apiFetcher } from "@/lib/api";

type Thread = {
  id: string;
  thread_id: string;
  subject: string;
  participants: string[];
  category: string | null;
  status: string;
  open_loop: boolean;
  message_count: number;
  last_message_at: string | null;
  action_summary: string | null;
  assigned_to_name: string | null;
  pending_outbound?: number;
};

type ColumnData = {
  project: any;
  threads: Thread[];
};

const CATEGORY_COLOR: Record<string, string> = {
  action_required: "var(--rr-urgent)",
  project: "var(--rr-brass)",
  deal: "var(--rr-ok)",
  intelligence: "var(--rr-intel)",
  admin: "var(--rr-dim)",
  newsletter: "var(--rr-subtle)",
  noise: "var(--rr-subtle)",
};

function ThreadCard({ thread, onClick }: { thread: Thread; onClick: () => void }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: thread.thread_id,
    data: { thread },
  });

  const style: React.CSSProperties = {
    transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="rr-card p-3 mb-2 relative">
      {/* Drag handle: small grip in top-right */}
      <div
        {...listeners}
        {...attributes}
        className="absolute top-2 right-2 cursor-grab active:cursor-grabbing px-1"
        style={{ color: "var(--rr-subtle)", fontSize: "14px", lineHeight: 1 }}
        title="Drag to move"
      >
        ⋮⋮
      </div>

      <div onClick={onClick} className="cursor-pointer pr-5">
        <div className="flex items-center gap-2 mb-1 text-[10px] rr-mono">
          {thread.category && (
            <span style={{ color: CATEGORY_COLOR[thread.category] || "var(--rr-dim)" }}>
              {thread.category.toUpperCase().replace("_", " ")}
            </span>
          )}
          {thread.open_loop && <span style={{ color: "var(--rr-urgent)" }}>OPEN LOOP</span>}
          {thread.pending_outbound && thread.pending_outbound > 0 ? (
            <span style={{ color: "var(--rr-brass)" }}>DRAFT</span>
          ) : null}
        </div>
        <p className="text-sm font-medium leading-tight mb-1" style={{ color: "var(--rr-cream)" }}>
          {thread.subject || "(no subject)"}
        </p>
        {thread.action_summary && (
          <p className="text-xs mb-2" style={{
            color: "var(--rr-dim)",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            overflow: "hidden",
          }}>
            {thread.action_summary}
          </p>
        )}
        <div className="flex items-center justify-between text-[10px]" style={{ color: "var(--rr-subtle)" }}>
          <span className="truncate" style={{ maxWidth: "160px" }}>
            {thread.participants?.[0] || "—"}
            {thread.participants?.length > 1 && ` +${thread.participants.length - 1}`}
          </span>
          <span>
            {thread.assigned_to_name ? `→ ${thread.assigned_to_name} · ` : ""}
            {thread.message_count} msg
          </span>
        </div>
      </div>
    </div>
  );
}

function Column({
  id,
  label,
  subtitle,
  threads,
  onCardClick,
  isOver,
  accent,
}: {
  id: string;
  label: string;
  subtitle?: string;
  threads: Thread[];
  onCardClick: (key: string) => void;
  isOver?: boolean;
  accent?: string;
}) {
  const { setNodeRef } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      className="flex-shrink-0 w-72 flex flex-col rounded"
      style={{
        background: isOver ? "rgba(200,162,74,0.08)" : "var(--rr-charcoal)",
        border: isOver ? "1px dashed var(--rr-brass)" : "1px solid var(--rr-border)",
        height: "calc(100vh - 140px)",
      }}
    >
      <div className="px-3 py-2 border-b flex items-center justify-between"
        style={{ borderColor: "var(--rr-border)", borderTop: `2px solid ${accent || "var(--rr-border)"}` }}>
        <div className="min-w-0">
          <p className="rr-mono text-[10px] tracking-wider" style={{ color: accent || "var(--rr-brass)" }}>{label}</p>
          {subtitle && (
            <p className="text-xs truncate" style={{ color: "var(--rr-cream)" }}>{subtitle}</p>
          )}
        </div>
        <span className="rr-mono text-xs" style={{ color: "var(--rr-dim)" }}>{threads.length}</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {threads.length === 0 ? (
          <p className="text-xs text-center mt-8" style={{ color: "var(--rr-subtle)" }}>
            (drag threads here)
          </p>
        ) : (
          threads.map((t) => (
            <ThreadCard key={t.thread_id} thread={t} onClick={() => onCardClick(t.thread_id)} />
          ))
        )}
      </div>
    </div>
  );
}

export default function CommsHub() {
  const [showNoise, setShowNoise] = useState(false);
  const url = `/api/projects/canvas?show_noise=${showNoise}`;
  const { data, isLoading } = useSWR<any>(url, apiFetcher, { refreshInterval: 15000 });
  const [openThread, setOpenThread] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  function onDragStart(e: DragStartEvent) {
    setActiveId(String(e.active.id));
  }
  function onDragOver(e: any) {
    setOverId(e.over?.id ? String(e.over.id) : null);
  }
  async function onDragEnd(e: DragEndEvent) {
    setActiveId(null);
    setOverId(null);
    if (!e.over) return;
    const threadKey = String(e.active.id);
    const targetId = String(e.over.id);

    const body =
      targetId === "inbox"
        ? { clear_project: true }
        : { canvas_project_id: targetId };

    try {
      await api.patch(`/api/email/threads/${threadKey}`, body);
      mutate(url);
    } catch (e: any) {
      console.error("Failed to move thread:", e);
      // SWR will retry on next refresh tick; surface to user via UI in 1A.2
    }
  }

  if (isLoading || !data) {
    return <div className="p-6" style={{ color: "var(--rr-dim)" }}>Loading…</div>;
  }

  const inbox = data.inbox;
  const columns: ColumnData[] = data.columns;
  const allThreads = [...(inbox?.threads || []), ...columns.flatMap((c) => c.threads)];
  const activeThread = allThreads.find((t) => t.thread_id === activeId) || null;

  return (
    <div className="h-full flex flex-col" style={{ background: "var(--rr-obsidian)" }}>
      <div className="px-6 py-3 flex items-center justify-between border-b"
        style={{ borderColor: "var(--rr-border)" }}>
        <div>
          <h1 className="rr-heading text-2xl" style={{ color: "var(--rr-cream)" }}>Comms Hub</h1>
          <p className="text-xs" style={{ color: "var(--rr-dim)" }}>
            Drag threads between columns · click any card to read &amp; reply
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs cursor-pointer"
          style={{ color: "var(--rr-cream)" }}>
          <input type="checkbox" checked={showNoise} onChange={(e) => setShowNoise(e.target.checked)} />
          Show noise / admin / newsletter
        </label>
      </div>

      <DndContext sensors={sensors} onDragStart={onDragStart} onDragOver={onDragOver} onDragEnd={onDragEnd}>
        <div className="flex-1 overflow-x-auto px-4 py-4 flex gap-3">
          <Column
            id="inbox"
            label="INBOX"
            subtitle={showNoise ? "Everything unassigned" : "Action required + unsorted"}
            threads={inbox.threads}
            onCardClick={setOpenThread}
            isOver={overId === "inbox"}
            accent="var(--rr-urgent)"
          />
          {columns.map((col) => (
            <Column
              key={col.project.id}
              id={col.project.id}
              label={col.project.code}
              subtitle={col.project.name}
              threads={col.threads}
              onCardClick={setOpenThread}
              isOver={overId === col.project.id}
              accent="var(--rr-brass)"
            />
          ))}
        </div>

        <DragOverlay>
          {activeThread && (
            <div className="rr-card p-3 w-72" style={{
              background: "var(--rr-charcoal)",
              border: "1px solid var(--rr-brass)",
              boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
            }}>
              <p className="text-sm" style={{ color: "var(--rr-cream)" }}>{activeThread.subject}</p>
            </div>
          )}
        </DragOverlay>
      </DndContext>

      <ThreadDrawer threadKey={openThread} onClose={() => setOpenThread(null)} />
      <OutboxPanel />
    </div>
  );
}
