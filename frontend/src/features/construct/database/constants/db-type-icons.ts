export interface DbTypeDisplay {
  name: string
  label: string
  icon: string
  color: string
  bgColor: string
}

export const DB_TYPE_DISPLAY: Record<string, DbTypeDisplay> = {
  sqlite: {
    name: "sqlite",
    label: "SQLite",
    icon: "💾",
    color: "text-blue-600",
    bgColor: "bg-blue-50 dark:bg-blue-950",
  },
  duckdb: {
    name: "duckdb",
    label: "DuckDB",
    icon: "🦆",
    color: "text-yellow-600",
    bgColor: "bg-yellow-50 dark:bg-yellow-950",
  },
  postgresql: {
    name: "postgresql",
    label: "PostgreSQL",
    icon: "🐘",
    color: "text-indigo-600",
    bgColor: "bg-indigo-50 dark:bg-indigo-950",
  },
  mysql: {
    name: "mysql",
    label: "MySQL",
    icon: "🐬",
    color: "text-orange-600",
    bgColor: "bg-orange-50 dark:bg-orange-950",
  },
  clickhouse: {
    name: "clickhouse",
    label: "ClickHouse",
    icon: "📊",
    color: "text-red-600",
    bgColor: "bg-red-50 dark:bg-red-950",
  },
  mssql: {
    name: "mssql",
    label: "SQL Server",
    icon: "🏢",
    color: "text-sky-600",
    bgColor: "bg-sky-50 dark:bg-sky-950",
  },
  oracle: {
    name: "oracle",
    label: "Oracle",
    icon: "🔴",
    color: "text-red-700",
    bgColor: "bg-red-50 dark:bg-red-950",
  },
  starrocks: {
    name: "starrocks",
    label: "StarRocks",
    icon: "⭐",
    color: "text-purple-600",
    bgColor: "bg-purple-50 dark:bg-purple-950",
  },
  vertica: {
    name: "vertica",
    label: "Vertica",
    icon: "📐",
    color: "text-teal-600",
    bgColor: "bg-teal-50 dark:bg-teal-950",
  },
  hive: {
    name: "hive",
    label: "Hive",
    icon: "🐝",
    color: "text-amber-600",
    bgColor: "bg-amber-50 dark:bg-amber-950",
  },
}

export function getDbTypeDisplay(dbType: string): DbTypeDisplay {
  return DB_TYPE_DISPLAY[dbType] ?? {
    name: dbType,
    label: dbType,
    icon: "🗄️",
    color: "text-gray-600",
    bgColor: "bg-gray-50 dark:bg-gray-950",
  }
}
