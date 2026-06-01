import type { DatasourceTypeInfo } from "@/services/database"
import { getDbTypeDisplay } from "../constants/db-type-icons"

interface DatasourceTypeGridProps {
  types: DatasourceTypeInfo[]
  selected: string | null
  onSelect: (typeName: string) => void
}

export function DatasourceTypeGrid({ types, selected, onSelect }: DatasourceTypeGridProps) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
      {types.map((type) => {
        const display = getDbTypeDisplay(type.name)
        const isSelected = selected === type.name
        return (
          <button
            key={type.name}
            type="button"
            className={`flex flex-col items-center gap-1.5 rounded-lg border p-3 transition-colors hover:bg-accent ${
              isSelected
                ? "border-primary bg-primary/5 ring-1 ring-primary"
                : "border-border"
            }`}
            onClick={() => onSelect(type.name)}
          >
            <span className="text-2xl">{display.icon}</span>
            <span className="text-xs font-medium">{type.label}</span>
          </button>
        )
      })}
    </div>
  )
}
