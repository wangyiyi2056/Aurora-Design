import { QueryClientProvider } from "@tanstack/react-query"
import { ConfigProvider } from "antd"
import { queryClient } from "@/lib/query-client"
import { getAntdTheme } from "@/styles/antd-theme"
import { useGlobalStore } from "@/stores/global-store"

interface AppProvidersProps {
  children: React.ReactNode
}

export function AppProviders({ children }: AppProvidersProps) {
  const { theme } = useGlobalStore()
  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider theme={getAntdTheme(theme)}>{children}</ConfigProvider>
    </QueryClientProvider>
  )
}
