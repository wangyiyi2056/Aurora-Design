import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useQuery } from "@tanstack/react-query"
import { listModelConfigs } from "@/services/models"

interface ModelSelectorProps {
  value: string
  onChange: (value: string) => void
}

const builtinModels = [
  { value: "gpt-4o-mini", label: "GPT-4o Mini" },
  { value: "gpt-4o", label: "GPT-4o" },
]

export function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const { data } = useQuery({
    queryKey: ["models", "list"],
    queryFn: listModelConfigs,
    staleTime: 30_000,
  })
  const models = data?.items || []
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
