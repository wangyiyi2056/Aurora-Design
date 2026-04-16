import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Button, Input, Select, Table } from "antd"
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

  const columns = [
    { title: t("database.name"), dataIndex: "name", key: "name" },
    { title: t("database.type"), dataIndex: "db_type", key: "db_type" },
    {
      title: t("database.connected"),
      dataIndex: "connected",
      key: "connected",
      render: (v: boolean) => (v ? "Yes" : "No"),
    },
  ]

  return (
    <ConstructShell>
      <div className="flex gap-3 mb-6">
        <Input
          placeholder={t("database.name")}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Select
          value={dbType}
          onChange={setDbType}
          options={[
            { value: "sqlite", label: "SQLite" },
            { value: "postgresql", label: "PostgreSQL" },
            { value: "mysql", label: "MySQL" },
            { value: "duckdb", label: "DuckDB" },
          ]}
          className="min-w-[120px]"
        />
        <Input
          placeholder="Database"
          value={database}
          onChange={(e) => setDatabase(e.target.value)}
          className="flex-1"
        />
        <Button type="primary" onClick={add} loading={create.isPending}>
          {t("database.add")}
        </Button>
      </div>

      <Table
        dataSource={items}
        columns={columns}
        rowKey="name"
        pagination={false}
        loading={isLoading}
        className="mb-8"
      />

      <h3 className="text-lg font-medium mt-8 mb-4">{t("database.query")}</h3>
      <div className="flex gap-3 mb-3">
        <Select
          value={selected}
          onChange={setSelected}
          placeholder={t("database.selectDatasource")}
          className="min-w-[180px]"
        >
          <Select.Option value="">{t("database.selectDatasource")}</Select.Option>
          {items.map((it) => (
            <Select.Option key={it.name} value={it.name}>
              {it.name}
            </Select.Option>
          ))}
        </Select>
      </div>
      <Input.TextArea
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        rows={4}
        className="mb-3"
      />
      <Button type="primary" onClick={run} loading={runner.isPending}>
        {t("database.runSql")}
      </Button>
      {result !== null && (
        <pre className="bg-surface mt-4 p-3 rounded-lg text-xs overflow-auto max-h-96">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </ConstructShell>
  )
}
