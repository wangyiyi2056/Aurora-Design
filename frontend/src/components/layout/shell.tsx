import { useTheme } from "@/hooks/use-theme"
import { useIsMobile } from "@/hooks/use-media-query"
import { Sidebar } from "./sidebar"

interface ShellProps {
  children: React.ReactNode
}

export function Shell({ children }: ShellProps) {
  useTheme()
  const isMobile = useIsMobile()

  return (
    <div className="flex h-screen bg-bg text-text">
      {!isMobile && <Sidebar />}
      <main className={`flex-1 overflow-auto ${isMobile ? "p-3" : "p-6"}`}>{children}</main>
    </div>
  )
}
