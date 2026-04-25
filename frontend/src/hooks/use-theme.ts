import { useEffect } from "react"
import { useGlobalStore } from "@/stores/global-store"

export function useTheme() {
  const { theme } = useGlobalStore()

  useEffect(() => {
    // Support both data-theme (for custom CSS) and class (for shadcn/Tailwind)
    document.documentElement.setAttribute("data-theme", theme)
    if (theme === "dark") {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }, [theme])

  return theme
}