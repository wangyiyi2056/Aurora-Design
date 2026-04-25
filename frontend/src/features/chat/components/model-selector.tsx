import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useModelsStore } from "@/stores/models-store"

interface ModelSelectorProps {
  value: string
  onChange: (value: string) => void
}

const builtinModels = [
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "gpt-4o", label: "GPT-4o" },
]

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const { models } = useModelsStore()
  const customModels = models
    .filter((m) => (m.type === "llm" || m.type === "anthropic") && m.status === "available")
    .map((m) => ({
      value: m.name,
      label: m.type === "anthropic" ? `${m.name} (Anthropic)` : m.name
    }))

  const options = [...customModels, ...builtinModels]

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="min-w-[140px] h-8">
        <SelectValue placeholder="Select model" />
      </SelectTrigger>
      <SelectContent>
        {options.map((opt) => (
          <SelectItem key={opt.value} value={opt.value}>
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}