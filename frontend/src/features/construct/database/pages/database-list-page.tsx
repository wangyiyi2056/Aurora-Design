import { useCallback, useState } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import type { DatasourceConfig, DatasourceItem } from "@/services/database"
import { getDatasource } from "@/services/database"
import { DatasourceCard } from "../components/datasource-card"
import { DatasourceDetailSheet } from "../components/datasource-detail-sheet"
import { DatasourceFormDialog } from "../components/datasource-form-dialog"
import {
  useDatasources,
  useDatasourceTypes,
  useCreateDatasource,
  useUpdateDatasource,
  useDeleteDatasource,
  useRefreshDatasource,
  useTestConnection,
} from "@/features/construct/database/hooks/use-datasources"

export default function DatabaseListPage() {
  const { t } = useTranslation("construct")
  const { data, isLoading } = useDatasources()
  const { data: typesData } = useDatasourceTypes()
  const create = useCreateDatasource()
  const update = useUpdateDatasource()
  const remove = useDeleteDatasource()
  const refresh = useRefreshDatasource()
  const testConn = useTestConnection()

  const [search, setSearch] = useState("")
  const [formOpen, setFormOpen] = useState(false)
  const [editItem, setEditItem] = useState<DatasourceItem | null>(null)
  const [editConfig, setEditConfig] = useState<DatasourceConfig | null>(null)
  const [detailItem, setDetailItem] = useState<DatasourceItem | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const items = data?.items ?? []
  const types = typesData?.types ?? []

  const filtered = search.trim()
    ? items.filter(
        (i) =>
          i.name.toLowerCase().includes(search.toLowerCase()) ||
          i.db_type.toLowerCase().includes(search.toLowerCase()),
      )
    : items

  const handleAdd = useCallback(() => {
    setEditItem(null)
    setEditConfig(null)
    setFormOpen(true)
  }, [])

  const handleEdit = useCallback(async (item: DatasourceItem) => {
    try {
      const detail = await getDatasource(item.name)
      setEditItem(item)
      setEditConfig(detail.config)
      setFormOpen(true)
    } catch {
      setEditItem(item)
      setEditConfig({ name: item.name, db_type: item.db_type })
      setFormOpen(true)
    }
  }, [])

  const handleSubmit = useCallback(
    (config: DatasourceConfig) => {
      if (editItem) {
        update.mutate(
          { name: editItem.name, config },
          { onSuccess: () => setFormOpen(false) },
        )
      } else {
        create.mutate(config, { onSuccess: () => setFormOpen(false) })
      }
    },
    [editItem, create, update],
  )

  const handleTestConnection = useCallback(
    async (config: DatasourceConfig): Promise<boolean> => {
      const result = await testConn.mutateAsync(config)
      return result.connected
    },
    [testConn],
  )

  const handleDelete = useCallback(
    (name: string) => {
      if (window.confirm(`Delete datasource "${name}"?`)) {
        remove.mutate(name)
      }
    },
    [remove],
  )

  const handleRefresh = useCallback(
    (name: string) => {
      refresh.mutate(name)
    },
    [refresh],
  )

  const handleDetail = useCallback((item: DatasourceItem) => {
    setDetailItem(item)
    setDetailOpen(true)
  }, [])

  return (
    <ConstructShell>
      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-6">
        <Input
          placeholder="Search datasources..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <div className="flex-1" />
        <Button onClick={handleAdd}>
          + {t("database.add")}
        </Button>
      </div>

      {/* Cards grid */}
      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground mb-4">{t("database.empty")}</p>
          <Button variant="outline" onClick={handleAdd}>
            Add your first datasource
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((item) => (
            <DatasourceCard
              key={item.name}
              item={item}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onRefresh={handleRefresh}
              onDetail={handleDetail}
            />
          ))}
        </div>
      )}

      {/* Form Dialog */}
      <DatasourceFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        types={types}
        editItem={editItem}
        editConfig={editConfig}
        onSubmit={handleSubmit}
        onTestConnection={handleTestConnection}
        submitting={create.isPending || update.isPending}
      />

      {/* Detail Sheet */}
      <DatasourceDetailSheet
        open={detailOpen}
        onOpenChange={setDetailOpen}
        item={detailItem}
      />
    </ConstructShell>
  )
}
