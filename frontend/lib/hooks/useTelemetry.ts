/**
 * Telemetry hook — premortem rule 5.12.
 *
 * Fires a `room_open` event on mount for the given target. Best-effort:
 * a failed POST is logged to console and otherwise ignored (telemetry
 * must never break a render). Records duration on unmount.
 *
 *   useTelemetry("morning");
 *
 * The Workspace filter is read from the zustand store and attached to the
 * event so weekly reports can break usage down by company.
 */
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useWorkspaceFilter } from "@/lib/stores/workspaceFilter";

export function useTelemetry(target: string, opts?: { enabled?: boolean }) {
  const enabled = opts?.enabled ?? true;
  const selectedId = useWorkspaceFilter((s) => s.selectedId);
  const startRef = useRef<number>(0);

  useEffect(() => {
    if (!enabled) return;
    startRef.current = performance.now();

    // Fire room_open immediately (don't wait for unmount)
    api
      .post("/api/telemetry", {
        event_type: "room_open",
        event_target: target,
        workspace_id: selectedId,
      })
      .catch((e) => {
        // eslint-disable-next-line no-console
        console.debug("telemetry room_open failed:", e);
      });

    return () => {
      const duration_ms = Math.round(performance.now() - startRef.current);
      // sendBeacon would be ideal here but it doesn't carry our auth header;
      // a regular fire-and-forget fetch is fine for unload telemetry.
      api
        .post("/api/telemetry", {
          event_type: "page_view",
          event_target: target,
          duration_ms,
          workspace_id: selectedId,
        })
        .catch(() => {
          // ignore — page is unmounting
        });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, enabled]);
}
