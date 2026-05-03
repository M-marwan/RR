/**
 * Cross-page workspace filter.
 *
 * The principal sees data from ALL workspaces by default (selectedId = null).
 * They can filter to a single company via the header chip selector. Selection
 * persists to localStorage so refresh doesn't lose the focus.
 *
 * Pages query data with the filter:
 *
 *   const { selectedId } = useWorkspaceFilter();
 *   const url = selectedId
 *     ? `/api/projects?workspace_id=${selectedId}`
 *     : `/api/projects`;
 *
 * Phase 1A.2 will wire this into all pages. For Phase 1A.1 the store exists
 * but only the settings UI uses it.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface WorkspaceFilterState {
  /** Currently focused workspace id; null = "All companies" (cross-portfolio view). */
  selectedId: string | null;
  setSelected: (id: string | null) => void;
  clear: () => void;
}

export const useWorkspaceFilter = create<WorkspaceFilterState>()(
  persist(
    (set) => ({
      selectedId: null,
      setSelected: (id) => set({ selectedId: id }),
      clear: () => set({ selectedId: null }),
    }),
    {
      name: "rr-workspace-filter",
      // Only persist the field we care about — avoid storing function refs.
      partialize: (state) => ({ selectedId: state.selectedId }),
    },
  ),
);
