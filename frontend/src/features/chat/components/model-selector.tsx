import { Select } from "antd"
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
    .filter((m) => m.type === "llm" && m.status === "available")
    .map((m) => ({ value: m.name, label: m.name }))

  const options = [...customModels, ...builtinModels]

  return (
    <Select
      value={value}
      onChange={onChange}
      options={options}
      className="min-w-[140px]"
    />
  )
}
