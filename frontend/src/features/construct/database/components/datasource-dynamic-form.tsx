import { Input } from "@/components/ui/input"
import type { ParameterDefinition } from "@/services/database"

interface DatasourceDynamicFormProps {
  parameters: ParameterDefinition[]
  values: Record<string, unknown>
  onChange: (name: string, value: unknown) => void
}

export function DatasourceDynamicForm({ parameters, values, onChange }: DatasourceDynamicFormProps) {
  return (
    <div className="space-y-3">
      {parameters.map((param) => (
        <div key={param.name}>
          <label className="text-sm font-medium mb-1 block">
            {param.label}
            {param.required && <span className="text-destructive ml-0.5">*</span>}
          </label>
          <Input
            type={param.type === "password" ? "password" : param.type === "number" ? "number" : "text"}
            placeholder={param.placeholder || param.description || ""}
            value={String(values[param.name] ?? param.default ?? "")}
            onChange={(e) => {
              const v = param.type === "number" ? Number(e.target.value) || undefined : e.target.value
              onChange(param.name, v)
            }}
          />
          {param.description && (
            <p className="text-xs text-muted-foreground mt-0.5">{param.description}</p>
          )}
        </div>
      ))}
    </div>
  )
}
