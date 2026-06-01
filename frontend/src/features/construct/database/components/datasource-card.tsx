import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { DatasourceItem } from "@/services/database"
import { getDbTypeDisplay } from "../constants/db-type-icons"

interface DatasourceCardProps {
  item: DatasourceItem
  onEdit: (item: DatasourceItem) => void
  onDelete: (name: string) => void
  onRefresh: (name: string) => void
  onDetail: (item: DatasourceItem) => void
}

export function DatasourceCard({
  item,
  onEdit,
  onDelete,
  onRefresh,
  onDetail,
}: DatasourceCardProps) {
  const display = getDbTypeDisplay(item.db_type)

  return (
    <div
      className="group relative rounded-lg border bg-card p-4 hover:shadow-md transition-shadow cursor-pointer"
      onClick={() => onDetail(item)}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-lg text-lg ${display.bgColor}`}
          >
            {display.icon}
          </div>
          <div>
            <h3 className="font-medium text-sm leading-tight">{item.name}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{display.label}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge
            variant={item.connected ? "default" : "destructive"}
            className="text-[10px] px-1.5 py-0"
          >
            {item.connected ? "Connected" : "Error"}
          </Badge>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="sm" className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100">
                ⋮
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onEdit(item) }}>
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onRefresh(item.name) }}>
                Refresh
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-destructive"
                onClick={(e) => { e.stopPropagation(); onDelete(item.name) }}
              >
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      {item.description && (
        <p className="text-xs text-muted-foreground mt-2 line-clamp-2">{item.description}</p>
      )}
      {item.tables && (
        <p className="text-xs text-muted-foreground mt-2">
          {item.tables.length} table{item.tables.length !== 1 ? "s" : ""}
        </p>
      )}
      {item.error && (
        <p className="text-xs text-destructive mt-2 line-clamp-1" title={item.error}>
          {item.error}
        </p>
      )}
    </div>
  )
}
