# 数据源功能全面重构计划

基于 DB-GPT 的数据源模块，为 Aurora-Design 构建完整的数据源管理功能（CRUD + 测试连接 + 刷新 + 多数据库类型支持），并在聊天 Composer 中集成数据源选择器实现数据分析闭环。

---

## 现状分析

### Aurora 当前状态

- **后端**: 基础 CRUD API + SQLAgent（仅 4 种 DB 类型: SQLite/PG/MySQL/DuckDB）
- **前端**: 简陋的 `database-list-page.tsx`，仅能添加/列表/手动查询
- **聊天集成**: `ChatService._run_datasource_analysis()` 通过 `ext_info.database_name` 调用 SQLAgent，但前端 Composer **没有数据源选择 UI**

### DB-GPT 参考功能

- 卡片式 DB 类型列表 + 按类型分组的连接管理 Drawer
- 动态表单（每种 DB 类型有不同参数字段）
- 测试连接 → 保存 → 异步 Schema 摘要嵌入
- 连接器缓存（TTL 30min + 线程安全）
- 支持 15+ 数据库类型

---

## Phase 1: 后端 — 扩展连接器与 API（预估 3-4 步）

### 1.1 新增数据库连接器

在 `aurora-core/datasource/rdbms/` 下增加连接器：

| 连接器     | 文件            | 连接串模板                  |
| ---------- | --------------- | --------------------------- |
| ClickHouse | `clickhouse.py` | `clickhouse+native://`      |
| MSSQL      | `mssql.py`      | `mssql+pymssql://`          |
| Oracle     | `oracle.py`     | `oracle+oracledb://`        |
| StarRocks  | `starrocks.py`  | `starrocks://` (MySQL 协议) |
| Vertica    | `vertica.py`    | `vertica+vertica_python://` |
| Hive       | `hive.py`       | `hive://`                   |

每个连接器继承 `RDBMSConnector`，复用 SQLAlchemy inspect 能力。

**同时更新**:

- `DatasourceService._build_connector()` — 增加新类型的分支
- `DBConfig.db_type` 的校验扩展

### 1.2 增强 DatasourceService

参考 DB-GPT `ConnectorManager` 补齐能力：

- **连接器缓存**: TTL 策略（30min），线程安全 `_connector_cache` + invalidate
- **动态参数注册**: 每种 DB 类型定义自己的参数 schema（host/port/user/pwd/database/extra）
- **`get_supported_types()` API**: 返回所有支持的 DB 类型 + 每种类型需要的参数定义
- **`test_connection(config)` 优化**: 不保存，只验证连接
- **`refresh(name)` API**: 清缓存 + 重新获取表结构
- **`get_database_summary(name)` API**: 返回完整数据库摘要（表、列、索引、外键、行数）

### 1.3 增强 API 端点

更新 `aurora_serve/datasource/api.py`：

```
GET    /datasource/types          → 支持的 DB 类型列表 + 参数 schema
POST   /datasource                → 创建（已有，增强验证）
PUT    /datasource/{name}         → 更新（已有）
DELETE /datasource/{name}         → 删除（已有）
GET    /datasource                → 列表（已有，增强返回字段）
GET    /datasource/{name}         → 详情（已有）
POST   /datasource/test-connection → 测试连接（已有，优化）
POST   /datasource/{name}/refresh → 刷新 Schema 缓存（新增）
GET    /datasource/{name}/summary → 数据库完整摘要（新增）
GET    /datasource/{name}/tables  → 表列表（已有）
GET    /datasource/{name}/schema/{table} → 表 Schema（已有）
POST   /datasource/{name}/query   → 执行 SQL（已有）
```

### 1.4 Schema 更新

- `DatasourceResponse` 增加: `id`, `description`, `created_at`, `updated_at`
- `DatasourceEntity` 增加 `description` 字段
- 新增 `DatasourceTypeInfo` schema（类型名、标签、参数定义列表）

---

## Phase 2: 前端 — 数据源管理页面（预估 4-5 步）

### 2.1 更新 API Service 层

`services/database.ts` 新增：

```ts
getDatasourceTypes(); // GET /datasource/types
testConnection(config); // POST /datasource/test-connection
refreshDatasource(name); // POST /datasource/{name}/refresh
getDatasourceSummary(name); // GET /datasource/{name}/summary
```

### 2.2 重构数据源管理页（shadcn/ui 风格）

替换现有 `database-list-page.tsx`，新 UI 结构：

1. **顶部操作栏**: "添加数据源" 按钮 + 搜索/过滤
2. **数据源卡片网格**: 每个连接显示为 Card（图标 + 名称 + 类型 + 状态 Badge）
   - 卡片操作: 编辑 / 删除 / 刷新 / 查看详情
3. **新增/编辑 Dialog**:
   - Step 1: 选择数据库类型（卡片网格，每种类型一个带图标的选项）
   - Step 2: 动态表单（根据 `/datasource/types` 返回的参数定义动态渲染字段）
   - "测试连接" 按钮（提交前验证）
   - 描述字段
4. **详情 Sheet/Drawer**:
   - 连接信息摘要
   - 表列表 + 点击查看 Schema
   - 内嵌 SQL 查询面板

### 2.3 新建组件

```
features/construct/database/
├── pages/
│   └── database-list-page.tsx      ← 重写
├── components/
│   ├── datasource-card.tsx          ← 单个数据源卡片
│   ├── datasource-type-grid.tsx     ← DB 类型选择网格
│   ├── datasource-form-dialog.tsx   ← 创建/编辑 Dialog
│   ├── datasource-dynamic-form.tsx  ← 动态参数表单
│   ├── datasource-detail-sheet.tsx  ← 详情侧边栏
│   └── datasource-sql-panel.tsx     ← SQL 查询面板
├── hooks/
│   └── use-datasources.ts          ← 增强 hooks
└── constants/
    └── db-type-icons.ts            ← 数据库类型图标/颜色映射
```

### 2.4 React Query Hooks 补齐

在 `use-datasources.ts` 增加：

- `useDatasourceTypes()` — 加载支持的类型
- `useDeleteDatasource()`
- `useUpdateDatasource()`
- `useTestConnection()`
- `useRefreshDatasource()`
- `useDatasourceSummary(name)`
- `useDatasourceTables(name)`

---

## Phase 3: 聊天 Composer 集成数据源选择（预估 2-3 步）

### 3.1 Composer 添加数据源 Picker

参考现有 Design Skill Picker 的模式，在 `chat-composer.tsx` 中：

- 新增 `datasourcePickerOpen` 状态
- 在 `composer-import-wrap` 菜单中添加 "数据源" 选项
- 弹出 Popover 展示已连接的数据源列表（名称 + 类型 + 状态）
- 选中后在 Composer 底部显示 chip（类似 Design Skill chip）
- 数据绑定: `selectedDatasourceName` state

### 3.2 传递数据源上下文到后端

- `ChatPage.sendFromPane()` 的 `extInfo` 中增加 `database_name` 字段
- `ChatComposer.Props` 增加 datasource 相关 props
- `ChatPane` 透传 datasource props

### 3.3 后端聊天 Pipeline 增强

`ChatService._run_datasource_analysis()` 已存在基础逻辑，需增强：

- 自动注入数据库 Schema 摘要到 system prompt
- SQLAgent 增强: 支持更多 DB 方言的 SQL 生成
- 查询结果格式化（JSON → 可读表格 markdown）

---

## Phase 4: 测试与完善（预估 1-2 步）

### 4.1 后端测试

- `tests/serve/test_datasource_*.py` — Service / API 单元测试
- 覆盖: CRUD, test-connection, 连接器缓存 TTL, refresh

### 4.2 前端 E2E

- 更新 `e2e/construct.spec.ts` — 数据源 CRUD 流程
- 聊天中选择数据源并发送消息

### 4.3 i18n

- 中/英文翻译 keys: 所有新增 UI 文案

---

## 文件变更范围概要

### 后端新建/修改

| 文件                                         | 操作                                    |
| -------------------------------------------- | --------------------------------------- |
| `aurora-core/datasource/rdbms/clickhouse.py` | 新建                                    |
| `aurora-core/datasource/rdbms/mssql.py`      | 新建                                    |
| `aurora-core/datasource/rdbms/oracle.py`     | 新建                                    |
| `aurora-core/datasource/rdbms/starrocks.py`  | 新建                                    |
| `aurora-core/datasource/rdbms/vertica.py`    | 新建                                    |
| `aurora-core/datasource/rdbms/hive.py`       | 新建                                    |
| `aurora-serve/datasource/service.py`         | 修改（缓存、新类型）                    |
| `aurora-serve/datasource/api.py`             | 修改（新端点）                          |
| `aurora-serve/datasource/schema.py`          | 修改（新 schema）                       |
| `aurora-serve/metadata.py`                   | 修改（DatasourceEntity 加 description） |
| `aurora-serve/agent/sql_agent.py`            | 修改（多方言支持）                      |
| `aurora-serve/chat/service.py`               | 修改（增强 datasource 分析）            |

### 前端新建/修改

| 文件                                                       | 操作                          |
| ---------------------------------------------------------- | ----------------------------- |
| `services/database.ts`                                     | 修改（新 API 函数）           |
| `features/construct/database/pages/database-list-page.tsx` | 重写                          |
| `features/construct/database/components/*.tsx`             | 新建（6 个组件）              |
| `features/construct/database/hooks/use-datasources.ts`     | 修改（新 hooks）              |
| `features/construct/database/constants/db-type-icons.ts`   | 新建                          |
| `features/chat/components/chat-composer.tsx`               | 修改（加 datasource picker）  |
| `features/chat/pages/chat-page.tsx`                        | 修改（传递 datasource state） |
| `features/chat/components/chat-pane.tsx`                   | 修改（透传 props）            |
| `i18n/` 相关文件                                           | 修改                          |

---

## 执行顺序建议

1. **Phase 1.1** → 新增连接器（可独立完成，无依赖）
2. **Phase 1.2-1.4** → 增强 Service + API + Schema
3. **Phase 2.1-2.4** → 前端管理页面重构
4. **Phase 3.1-3.3** → Chat Composer 集成
5. **Phase 4** → 测试与 i18n

每个 Phase 完成后都可以独立验证，不会出现"迁移一半"的情况。
