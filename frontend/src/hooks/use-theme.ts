import { useEffect } from "react"
import { useGlobalStore } from "@/stores/global-store"

export function useTheme() {
  const { theme } = useGlobalStore()

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
  }, [theme])

  return theme
}
