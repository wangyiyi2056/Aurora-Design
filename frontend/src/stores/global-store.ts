import { create } from "zustand"
import { persist } from "zustand/middleware"

type ThemeMode = "dark" | "light"
type Language = "zh" | "en"

interface GlobalState {
  theme: ThemeMode
  language: Language
  sidebarCollapsed: boolean
  setTheme: (theme: ThemeMode) => void
  setLanguage: (lang: Language) => void
  toggleSidebar: () => void
}

export const useGlobalStore = create<GlobalState>()(
  persist(
    (set) => ({
      theme: "dark",
      language: "zh",
      sidebarCollapsed: false,
      setTheme: (theme) => set({ theme }),
      setLanguage: (language) => set({ language }),
      toggleSidebar: () =>
        set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
    }),
    { name: "chatbi-global-store" }
  )
)
