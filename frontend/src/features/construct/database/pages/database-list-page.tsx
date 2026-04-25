import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { ConstructShell } from "@/features/construct/components/construct-shell"
import {
  useDatasources,
  useCreateDatasource,
  useRunQuery,
} from "@/features/construct/database/hooks/use-datasources"

export default function DatabaseListPage() {
  const { t } = useTranslation("construct")
  const [name, setName] = useState("")
  const [dbType, setDbType] = useState("sqlite")
  const [database, setDatabase] = useState(":memory:")
  const [selected, setSelected] = useState("")
  const [sql, setSql] = useState("SELECT 1+1 as result")
  const [result, setResult] = useState<unknown>(null)

  const { data, isLoading } = useDatasources()
  const create = useCreateDatasource()
  const runner = useRunQuery()

  const items = data?.items || []

  const add = async () => {
    await create.mutateAsync({ name, db_type: dbType, database })
    setName("")
    setDatabase(":memory:")
  }

  const run = async () => {
    const data = await runner.mutateAsync({ name: selected, sql })
    setResult(data)
  }

  return (
    <ConstructShell>
      <div className="flex gap-3 mb-6 flex-wrap">
        <Input
          placeholder={t("database.name")}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Select value={dbType} onValueChange={setDbType}>
          <SelectTrigger className="w-[120px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="sqlite">SQLite</SelectItem>
            <SelectItem value="postgresql">PostgreSQL</SelectItem>
            <SelectItem value="mysql">MySQL</SelectItem>
            <SelectItem value="duckdb">DuckDB</SelectItem>
          </SelectContent>
        </Select>
        <Input
          placeholder="Database"
          value={database}
          onChange={(e) => setDatabase(e.target.value)}
          className="flex-1 min-w-[150px]"
        />
        <Button onClick={add} disabled={create.isPending}>
          {create.isPending ? "Adding..." : t("database.add")}
        </Button>
      </div>

      <div className="rounded-lg border border-border mb-8">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("database.name")}</TableHead>
              <TableHead>{t("database.type")}</TableHead>
              <TableHead>{t("database.connected")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((it) => (
              <TableRow key={it.name}>
                <TableCell className="font-medium">{it.name}</TableCell>
                <TableCell>{it.db_type}</TableCell>
                <TableCell>{it.connected ? "Yes" : "No"}</TableCell>
              </TableRow>
            ))}
            {items.length === 0 && !isLoading && (
              <TableRow>
                <TableCell colSpan={3} className="text-center text-muted-foreground py-8">
                  {t("database.empty") || "暂无数据源"}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <h3 className="text-lg font-medium mt-8 mb-4">{t("database.query")}</h3>
      <div className="flex gap-3 mb-3">
        <Select value={selected} onValueChange={setSelected}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder={t("database.selectDatasource")} />
          </SelectTrigger>
          <SelectContent>
            {items.map((it) => (
              <SelectItem key={it.name} value={it.name}>
                {it.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Textarea
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        rows={4}
        className="mb-3"
      />
      <Button onClick={run} disabled={runner.isPending}>
        {runner.isPending ? "Running..." : t("database.runSql")}
      </Button>
      {result !== null && (
        <pre className="bg-card mt-4 p-3 rounded-lg text-xs overflow-auto max-h-96 border border-border">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </ConstructShell>
  )
}
