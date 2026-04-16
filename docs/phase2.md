# Phase 2 完成记录：数据连接 — 数据源抽象 + SQL 生成与执行

**完成日期**：2026-04-15

## 已交付模块

### 1. 数据源核心抽象（`chatbi_core.datasource`）

#### BaseConnector

```python
class BaseConnector(ABC):
    @property
    def db_type(self) -> str: ...
    def get_table_names(self) -> List[str]: ...
    def get_table_schema(self, table: str) -> str: ...
    def query(self, sql: str) -> List[Dict]: ...
    def run(self, sql: str) -> Tuple[bool, str]: ...
```

实现：
- `RDBMSConnector` — 基于 SQLAlchemy 2.x 的统一关系型数据库连接基类
- `SQLiteConnector` — SQLite 支持（含内存数据库特殊处理）
- `PostgreSQLConnector` — PostgreSQL 支持（psycopg2）
- `MySQLConnector` — MySQL 支持（pymysql）
- `DuckDBConnector` — DuckDB 支持

### 2. 数据源管理 API（`chatbi_serve.datasource`）

- `POST /api/v1/datasource` — 创建数据源连接
- `GET /api/v1/datasource` — 列出所有数据源
- `DELETE /api/v1/datasource/{name}` — 删除数据源
- `POST /api/v1/datasource/{name}/test` — 测试数据源连通性
- `GET /api/v1/datasource/{name}/tables` — 获取表列表
- `GET /api/v1/datasource/{name}/schema/{table}` — 获取表结构 DDL
- `POST /api/v1/datasource/{name}/query` — 执行 SQL 查询
- `POST /api/v1/datasource/test-connection` — 测试任意配置连通性

### 3. SQL 生成服务

#### Prompt 模板

- `chatbi_serve.prompt.sql_prompt.build_sql_prompt(schema, question)`
- 生成 OpenAI 风格的 SQL 生成 Prompt，含 Schema 注入和只读安全约束

#### SQLAgent

- 自动识别 SQL 相关问题（基于关键词意图判断）
- 从数据源获取表结构并注入 Prompt
- 调用 LLM 生成 SQL → 执行 → 失败时自动 Retry（默认最多 2 轮）
- 支持提取 Markdown 代码块中的 SQL

#### ChatService 增强

- 用户提问若被识别为 SQL 意图，自动路由到 SQLAgent
- 否则走普通 LLM 对话流程

### 4. 配置扩展

`configs/chatbi.toml` 新增数据源配置区块：

```toml
default_datasource = "default-sqlite"
[[datasource_configs]]
name = "default-sqlite"
db_type = "sqlite"
database = ":memory:"
```

### 5. 测试覆盖

新增 5 个测试：
- `tests/core/test_datasource.py` — SQLite connector 单元测试
- `tests/serve/test_datasource_api.py` — Datasource API 集成测试
- `tests/serve/test_sql_agent.py` — SQLAgent 单元测试

**总计 17 个测试全部通过**

## API 使用示例

### 创建数据源

```bash
curl -X POST http://localhost:8000/api/v1/datasource \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "name": "my-db",
      "db_type": "sqlite",
      "database": ":memory:"
    }
  }'
```

### 查询

```bash
curl -X POST http://localhost:8000/api/v1/datasource/my-db/query \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT * FROM users"}'
```

### 自然语言转 SQL（通过 Chat API）

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "查询用户表的前10条记录"}]
  }'
```

## 安全约束

- Prompt 中强制要求只生成 `SELECT` 语句
- 后续可在 connector 层增加 SQL 白名单过滤
