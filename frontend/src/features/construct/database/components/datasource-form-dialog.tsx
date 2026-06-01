import { useCallback, useEffect, useMemo, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import type { DatasourceConfig, DatasourceItem, DatasourceTypeInfo } from "@/services/database"
import { DatasourceDynamicForm } from "./datasource-dynamic-form"
import { DatasourceTypeGrid } from "./datasource-type-grid"

interface DatasourceFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  types: DatasourceTypeInfo[]
  editItem?: DatasourceItem | null
  editConfig?: DatasourceConfig | null
  onSubmit: (config: DatasourceConfig) => void
  onTestConnection: (config: DatasourceConfig) => Promise<boolean>
  submitting?: boolean
}

export function DatasourceFormDialog({
  open,
  onOpenChange,
  types,
  editItem,
  editConfig,
  onSubmit,
  onTestConnection,
  submitting = false,
}: DatasourceFormDialogProps) {
  const isEdit = !!editItem
  const [step, setStep] = useState<"type" | "form">(isEdit ? "form" : "type")
  const [selectedType, setSelectedType] = useState<string | null>(editItem?.db_type ?? null)
  const [name, setName] = useState(editItem?.name ?? "")
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; error?: string } | null>(null)

  const typeInfo = useMemo(
    () => types.find((t) => t.name === selectedType),
    [types, selectedType],
  )

  useEffect(() => {
    if (open) {
      if (editItem && editConfig) {
        setStep("form")
        setSelectedType(editItem.db_type)
        setName(editItem.name)
        const v: Record<string, unknown> = {}
        const raw = editConfig as unknown as Record<string, unknown>
        for (const key of Object.keys(raw)) {
          if (key !== "name" && key !== "db_type") {
            v[key] = raw[key]
          }
        }
        setValues(v)
      } else {
        setStep("type")
        setSelectedType(null)
        setName("")
        setValues({})
      }
      setTestResult(null)
    }
  }, [open, editItem, editConfig])

  const handleSelectType = useCallback((typeName: string) => {
    setSelectedType(typeName)
    setValues({})
    setTestResult(null)
  }, [])

  const handleNextStep = useCallback(() => {
    if (selectedType) setStep("form")
  }, [selectedType])

  const handleFieldChange = useCallback((fieldName: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [fieldName]: value }))
    setTestResult(null)
  }, [])

  const buildConfig = useCallback((): DatasourceConfig | null => {
    if (!selectedType || !name.trim()) return null
    const config: DatasourceConfig = {
      name: name.trim(),
      db_type: selectedType,
    }
    for (const [k, v] of Object.entries(values)) {
      if (v !== undefined && v !== "") {
        ;(config as unknown as Record<string, unknown>)[k] = v
      }
    }
    return config
  }, [selectedType, name, values])

  const handleTest = useCallback(async () => {
    const config = buildConfig()
    if (!config) return
    setTesting(true)
    setTestResult(null)
    try {
      const ok = await onTestConnection(config)
      setTestResult({ ok })
    } catch (err) {
      setTestResult({ ok: false, error: err instanceof Error ? err.message : "Connection failed" })
    } finally {
      setTesting(false)
    }
  }, [buildConfig, onTestConnection])

  const handleSubmit = useCallback(() => {
    const config = buildConfig()
    if (config) onSubmit(config)
  }, [buildConfig, onSubmit])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[540px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Datasource" : "Add Datasource"}</DialogTitle>
          <DialogDescription>
            {step === "type"
              ? "Select a database type to get started."
              : `Configure your ${typeInfo?.label ?? selectedType} connection.`}
          </DialogDescription>
        </DialogHeader>

        {step === "type" ? (
          <>
            <DatasourceTypeGrid
              types={types}
              selected={selectedType}
              onSelect={handleSelectType}
            />
            <DialogFooter>
              <Button onClick={handleNextStep} disabled={!selectedType}>
                Next
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium mb-1 block">
                  Name <span className="text-destructive">*</span>
                </label>
                <Input
                  placeholder="my-database"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isEdit}
                />
              </div>
              {typeInfo && (
                <DatasourceDynamicForm
                  parameters={typeInfo.parameters}
                  values={values}
                  onChange={handleFieldChange}
                />
              )}
            </div>

            {testResult && (
              <div
                className={`rounded-md px-3 py-2 text-sm ${
                  testResult.ok
                    ? "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
                    : "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
                }`}
              >
                {testResult.ok ? "Connection successful!" : testResult.error ?? "Connection failed"}
              </div>
            )}

            <DialogFooter className="gap-2 sm:gap-0">
              {!isEdit && (
                <Button variant="ghost" onClick={() => setStep("type")}>
                  Back
                </Button>
              )}
              <Button variant="outline" onClick={handleTest} disabled={testing || !name.trim()}>
                {testing ? "Testing..." : "Test Connection"}
              </Button>
              <Button onClick={handleSubmit} disabled={submitting || !name.trim()}>
                {submitting ? "Saving..." : isEdit ? "Save" : "Create"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
