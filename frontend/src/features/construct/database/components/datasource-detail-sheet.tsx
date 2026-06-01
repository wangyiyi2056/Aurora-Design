import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { DatasourceItem } from "@/services/database"
import { getDbTypeDisplay } from "../constants/db-type-icons"
import { useDatasourceTables } from "../hooks/use-datasources"
import { DatasourceSqlPanel } from "./datasource-sql-panel"

interface DatasourceDetailSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  item: DatasourceItem | null
}

export function DatasourceDetailSheet({ open, onOpenChange, item }: DatasourceDetailSheetProps) {
  const tables = useDatasourceTables(item?.name ?? null)

  if (!item) return null

  const display = getDbTypeDisplay(item.db_type)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <span className="text-2xl">{display.icon}</span>
            <div>
              <DialogTitle>{item.name}</DialogTitle>
              <DialogDescription>
                {display.label}
                {item.description ? ` — ${item.description}` : ""}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="flex gap-2 flex-wrap">
          <Badge variant={item.connected ? "default" : "destructive"}>
            {item.connected ? "Connected" : "Disconnected"}
          </Badge>
          {item.tables && (
            <Badge variant="secondary">{item.tables.length} tables</Badge>
          )}
        </div>

        <Tabs defaultValue="tables" className="mt-2">
          <TabsList>
            <TabsTrigger value="tables">Tables</TabsTrigger>
            <TabsTrigger value="query">SQL Query</TabsTrigger>
          </TabsList>

          <TabsContent value="tables" className="mt-3">
            {tables.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading tables...</p>
            ) : tables.data?.tables && tables.data.tables.length > 0 ? (
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {tables.data.tables.map((table) => (
                  <div
                    key={table}
                    className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                  >
                    <span className="text-muted-foreground">📋</span>
                    <span className="font-mono text-xs">{table}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No tables found.</p>
            )}
          </TabsContent>

          <TabsContent value="query" className="mt-3">
            <DatasourceSqlPanel name={item.name} />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
