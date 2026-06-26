import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { Page, AppSettings, HistoryEntry, Theme, Language, ModelType } from "../types"

interface AppState {
  currentPage: Page
  sidebarOpen: boolean
  settings: AppSettings
  history: HistoryEntry[]
  // actions
  setPage: (page: Page) => void
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  updateSettings: (settings: Partial<AppSettings>) => void
  addHistory: (entry: HistoryEntry) => void
  clearHistory: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentPage: "dashboard",
      sidebarOpen: true,
      settings: {
        theme: "dark",
        language: "es",
        default_sims: 10_000,
        default_model: "hybrid",
        animations: true,
      },
      history: [],

      setPage: (page) => set({ currentPage: page }),
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      updateSettings: (settings) =>
        set((s) => ({ settings: { ...s.settings, ...settings } })),
      addHistory: (entry) =>
        set((s) => ({
          history: [entry, ...s.history].slice(0, 100),
        })),
      clearHistory: () => set({ history: [] }),
    }),
    { name: "football-ai-store", partialize: (s) => ({ settings: s.settings, history: s.history }) }
  )
)
