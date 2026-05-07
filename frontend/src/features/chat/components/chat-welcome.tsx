import { Database, BookOpen, Bot, ArrowUpRight } from "lucide-react"
import { useTranslation } from "react-i18next"
import { BrandLogo } from "@/components/brand/brand-logo"

interface ChatWelcomeProps {
  onSelect: (prompt: string) => void
}

export function ChatWelcome({ onSelect }: ChatWelcomeProps) {
  const { t } = useTranslation("chat")

  const examples = [
    { icon: Database, label: t("explore.datasource"), prompt: "Show me total sales by region" },
    { icon: BookOpen, label: t("explore.knowledge"), prompt: "What does our privacy policy say about cookies?" },
    { icon: Bot, label: t("explore.agent"), prompt: "Analyze the dataset and generate insights" },
  ]

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 text-center animate-message-fade-in px-4">
      {/* Hero icon with layered glow */}
      <div className="relative hero-aura">
        <div className="absolute inset-0 bg-primary/25 blur-[80px] rounded-full scale-[2.5]" />
        <div className="absolute inset-0 bg-[#00c6ff]/20 blur-[50px] rounded-full scale-150 animate-pulse-glow" />
        <div className="relative flex h-[72px] w-[72px] items-center justify-center rounded-[22px] bg-card shadow-xl shadow-blue-500/30 ring-1 ring-white/20">
          <BrandLogo className="h-12 w-12" />
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="text-[2rem] font-semibold m-0 tracking-tight leading-tight">
          {t("chat.welcomeTitle")}
        </h3>
        <p className="text-muted-foreground m-0 text-base max-w-sm mx-auto leading-relaxed">
          {t("chat.welcomeDesc")}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-xl">
        {examples.map((ex) => (
          <button
            key={ex.label}
            onClick={() => onSelect(ex.prompt)}
            className="flex flex-col items-center gap-3 p-5 rounded-2xl welcome-card group cursor-pointer"
            aria-label={ex.label}
          >
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 text-primary ring-1 ring-primary/15 group-hover:ring-primary/30 group-hover:from-primary/25 group-hover:to-primary/10 transition-all">
              <ex.icon className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="flex items-center gap-1">
              <span className="font-medium text-sm">{ex.label}</span>
              <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 -translate-y-0.5 translate-x-0.5 group-hover:opacity-100 group-hover:translate-y-0 group-hover:translate-x-0 transition-all duration-300" />
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
