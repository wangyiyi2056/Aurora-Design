import { useTranslation } from "react-i18next"
import { ModelSelector } from "./model-selector"

interface ChatHeaderProps {
  model: string
  onModelChange: (model: string) => void
}

export function ChatHeader({ model, onModelChange }: ChatHeaderProps) {
  const { t } = useTranslation("chat")
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-xl font-semibold m-0">{t("chat.title")}</h2>
      <ModelSelector value={model} onChange={onModelChange} />
    </div>
  )
}
