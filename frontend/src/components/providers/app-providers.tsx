import { QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "sonner"
import { queryClient } from "@/lib/query-client"
import { useTheme } from "@/hooks/use-theme"
import { I18nProvider } from "@/i18n"
import { normalizeLanguage } from "@/lib/i18n"
import { useGlobalStore } from "@/stores/global-store"

interface AppProvidersProps {
  children: React.ReactNode
}

export function AppProviders({ children }: AppProvidersProps) {
  // Initialize theme class on mount
  useTheme()
  const language = useGlobalStore((state) => state.language)

  return (
    <QueryClientProvider client={queryClient}>
      <I18nProvider initial={normalizeLanguage(language)}>
        {children}
      </I18nProvider>
      <Toaster richColors position="top-center" />
    </QueryClientProvider>
  )
}
