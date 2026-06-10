# Aurora 知识库 vs LightRAG 差异补齐计划

> 基于 2026-06-01 对两个项目的深度对比分析，本计划列出所有未对齐功能的详细实施步骤。
> 按 P0 → P1 → P2 优先级分阶段执行，每个阶段内的任务按依赖关系排序。

---

## 总览

| 阶段 | 主题 | 任务数 | 预估工期 |
|------|------|--------|---------|
| **P0** | 生产存储后端 + 认证 | 6 大任务 | 4-6 周 |
| **P1** | LLM 路由 + 缓存 + Reranking + 查询调优 | 8 大任务 | 3-5 周 |
| **P2** | 多模态 + 高级解析 + 评估 + 部署 | 7 大任务 | 4-6 周 |

---

## P0 — 生产可用性（阻塞上线）

### P0-1: PostgreSQL 存储后端（KV + DocStatus）

**目标**：替代 JSON 文件存储，支持并发读写和持久化

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/rag/storage/postgres_kv.py`
- 新增：`packages/aurora-ext/src/aurora_ext/rag/storage/postgres_doc_status.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/storage/__init__.py`（注册新后端）
- 修改：`configs/aurora.toml`（添加 PostgreSQL 配置项）

**实施步骤**：

- [ ] 1.1 安装依赖：`asyncpg`, `psycopg[binary,pool]` 添加到 `aurora-ext` 的 `pyproject.toml`
- [ ] 1.2 实现 `PostgresKVStorage(BaseKVStorage)`
  - 表结构：`aurora_kv(namespace TEXT, key TEXT, value JSONB, updated_at TIMESTAMP)`
  - 复合主键：`(namespace, key)`
  - `all_keys()`: `SELECT key FROM aurora_kv WHERE namespace = $1`
  - `get_by_id()`: 单条 SELECT
  - `get_by_ids()`: `WHERE key = ANY($1)` 批量查询
  - `get_by_field()`: JSONB 操作符 `value->>$1 = $2`
  - `upsert()`: `INSERT ... ON CONFLICT DO UPDATE`
  - `delete()`: `DELETE WHERE namespace = $1 AND key = ANY($2)`
  - `drop()`: `DELETE WHERE namespace = $1`
  - 连接池：使用 `psycopg_pool.AsyncConnectionPool`
- [ ] 1.3 实现 `PostgresDocStatusStorage(BaseDocStatusStorage)`
  - 表结构：`aurora_doc_status(namespace TEXT, doc_id TEXT, status TEXT, file_path TEXT, content_summary TEXT, content_length INT, chunks_count INT, error_msg TEXT, track_id TEXT, kb_name TEXT, metadata JSONB, created_at TIMESTAMP, updated_at TIMESTAMP)`
  - 索引：`(namespace, kb_name, status)`, `(namespace, track_id)`
  - 实现所有抽象方法，特别注意分页查询和 status_counts 聚合
- [ ] 1.4 编写测试 `tests/test_postgres_storage.py`
  - 使用 `pytest-asyncio` + 测试数据库
  - 覆盖 CRUD、并发读写、分页、状态流转
- [ ] 1.5 在 `storage/__init__.py` 注册新后端：`register_storage("postgres_kv", PostgresKVStorage)`
- [ ] 1.6 添加配置到 `aurora.toml`：
  ```toml
  [knowledge.storage]
  kv_backend = "postgres_kv"
  doc_status_backend = "postgres_doc_status"
  postgres_uri = "postgresql://user:pass@localhost:5432/aurora"
  ```
- [ ] 1.7 编写数据迁移脚本：从 JSON 文件导入到 PostgreSQL

---

### P0-2: Neo4j 图存储后端

**目标**：替代 NetworkX 内存图，支持大规模知识图谱的生产部署

**前置条件**：P0-1 可选（图存储独立于 KV 存储）

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/rag/storage/neo4j_graph.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/storage/__init__.py`
- 修改：`configs/aurora.toml`

**实施步骤**：

- [ ] 2.1 安装依赖：`neo4j` (官方 Python driver)
- [ ] 2.2 实现 `Neo4jGraphStorage(BaseGraphStorage)`
  - 节点模型：`(:Entity {id, label, entity_type, description, weight, source_ids, file_paths, keywords, metadata})`
  - 边模型：`(:Entity)-[:RELATED {description, weight, keywords, source_ids}]->(:Entity)`
  - `has_node()`: `MATCH (n:Entity {id: $id}) RETURN count(n) > 0`
  - `upsert_node()`: `MERGE (n:Entity {id: $id}) SET n += $props`
  - `delete_node()`: `MATCH (n:Entity {id: $id}) DETACH DELETE n`
  - `node_degree()`: `MATCH (n:Entity {id: $id})--() RETURN count(*)`
  - `get_all_labels()`: `MATCH (n:Entity) RETURN DISTINCT n.label`
  - `get_popular_labels()`: 按 degree 排序的 Cypher 查询
  - `search_labels()`: `WHERE n.label CONTAINS $query`
  - `get_connected_subgraph()`: BFS via Cypher `MATCH path = (start)-[*1..N]-(connected)`
  - `get_node_edges()`: `MATCH (n:Entity {id: $id})-[r]-(m) RETURN ...`
  - 批量操作：`UNWIND $batch AS row MERGE ...`
- [ ] 2.3 索引优化：为 `Entity.id`, `Entity.label` 创建唯一索引和全文索引
- [ ] 2.4 编写测试 `tests/test_neo4j_storage.py`
- [ ] 2.5 注册后端 + 配置：
  ```toml
  [knowledge.storage]
  graph_backend = "neo4j"
  neo4j_uri = "bolt://localhost:7687"
  neo4j_user = "neo4j"
  neo4j_password = "password"
  ```
- [ ] 2.6 编写 NetworkX → Neo4j 数据迁移脚本

---

### P0-3: Milvus / Qdrant 向量存储后端

**目标**：替代 ChromaDB 单节点限制，支持分布式向量检索

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/rag/storage/milvus_vector.py`
- 新增（可选）：`packages/aurora-ext/src/aurora_ext/rag/storage/qdrant_vector.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/storage/__init__.py`

**实施步骤**：

- [ ] 3.1 安装依赖：`pymilvus` 和/或 `qdrant-client`
- [ ] 3.2 实现 `MilvusVectorStorage(BaseVectorStorage)`
  - Collection 命名：`aurora_{namespace_sanitized}`
  - Schema：`id VARCHAR(128) PK, embedding FLOAT_VECTOR(dim), content VARCHAR(65535), metadata JSON`
  - Index：IVF_FLAT 或 HNSW (cosine)
  - `upsert()`: `collection.upsert(data)`
  - `query()`: `collection.search(data=[query_embedding], anns_field="embedding", param={"metric_type": "COSINE"}, limit=top_k)`
  - `delete()`: `collection.delete(expr="id in [...]")`
  - `drop()`: `utility.drop_collection(name)`
  - 过滤：`cosine_threshold` 转化为 score 截断
- [ ] 3.3 实现 `QdrantVectorStorage(BaseVectorStorage)`（可选）
  - Collection 命名 + payload schema
  - `upsert()`: `client.upsert(collection_name, points)`
  - `query()`: `client.query_points(collection_name, query=query_embedding, limit=top_k)`
- [ ] 3.4 编写测试 `tests/test_milvus_storage.py`
- [ ] 3.5 注册后端 + 配置：
  ```toml
  [knowledge.storage]
  vector_backend = "milvus"
  milvus_uri = "http://localhost:19530"
  milvus_token = ""
  ```

---

### P0-4: JWT + API Key 认证

**目标**：保护所有 API 端点，支持 Token 和 API Key 两种认证方式

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-serve/src/aurora_serve/auth/__init__.py`
- 新增：`packages/aurora-serve/src/aurora_serve/auth/jwt_handler.py`
- 新增：`packages/aurora-serve/src/aurora_serve/auth/middleware.py`
- 新增：`packages/aurora-serve/src/aurora_serve/auth/api_key.py`
- 修改：`packages/aurora-serve/src/aurora_serve/server.py`（挂载中间件）
- 修改：`configs/aurora.toml`（认证配置）

**实施步骤**：

- [ ] 4.1 安装依赖：`PyJWT`, `passlib[bcrypt]`
- [ ] 4.2 实现 JWT Handler
  - `create_token(user_id, role, expires_delta)` → JWT string
  - `verify_token(token)` → payload dict
  - Token 刷新机制：`X-New-Token` response header
  - Secret 从环境变量 `AURORA_JWT_SECRET` 读取
- [ ] 4.3 实现 API Key Handler
  - API Key 存储在配置或数据库中
  - 支持 `Authorization: Bearer <api_key>` header
  - Key 使用 SHA-256 哈希存储，明文仅在创建时返回一次
- [ ] 4.4 实现认证中间件
  - FastAPI Depends：`get_current_user(request)` → `User` 对象
  - 公开端点白名单：`/health`, `/api/v1/auth/login`, `/docs`
  - Guest 模式：未认证时返回受限 token
- [ ] 4.5 添加登录端点
  - `POST /api/v1/auth/login` — OAuth2 password flow
  - `POST /api/v1/auth/api-keys` — 创建 API Key
  - `GET /api/v1/auth/status` — 认证状态检查
- [ ] 4.6 挂载到现有路由：所有 `/api/v1/knowledge/*` 等端点添加认证依赖
- [ ] 4.7 编写测试 `tests/test_auth.py`
- [ ] 4.8 CLI 密码哈希工具：`packages/aurora-serve/src/aurora_serve/auth/hash_password.py`

---

### P0-5: 存储后端工厂 + 运行时切换

**目标**：统一管理所有存储后端的注册、实例化和切换

**前置条件**：P0-1, P0-2, P0-3 至少一个完成

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/rag/storage/factory.py`
- 修改：`packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`（使用工厂）

**实施步骤**：

- [ ] 5.1 实现存储工厂 `StorageFactory`
  ```python
  class StorageFactory:
      _registry: dict[str, type] = {}

      @classmethod
      def register(cls, name: str, storage_cls: type): ...

      @classmethod
      def create_kv(cls, backend: str, namespace: str, config: dict) -> BaseKVStorage: ...

      @classmethod
      def create_vector(cls, backend: str, namespace: str, config: dict) -> BaseVectorStorage: ...

      @classmethod
      def create_graph(cls, backend: str, namespace: str, config: dict) -> BaseGraphStorage: ...

      @classmethod
      def create_doc_status(cls, backend: str, namespace: str, config: dict) -> BaseDocStatusStorage: ...
  ```
- [ ] 5.2 自动注册所有内置后端（JSON, Chroma, NetworkX, Postgres, Neo4j, Milvus）
- [ ] 5.3 修改 `KnowledgeV2Service.__init__` 从配置读取 backend 名称，通过工厂实例化
- [ ] 5.4 添加环境变量覆盖：`AURORA_KV_BACKEND`, `AURORA_VECTOR_BACKEND`, `AURORA_GRAPH_BACKEND`
- [ ] 5.5 编写测试：工厂创建、注册、未知后端报错

---

### P0-6: 跨进程锁 + 工作空间隔离

**目标**：支持多进程/多实例部署时的数据安全

**前置条件**：P0-5

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/rag/storage/shared_lock.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/storage/base.py`（添加 workspace 概念）

**实施步骤**：

- [ ] 6.1 实现 `SharedLock` 抽象
  - 本地模式：`asyncio.Lock` + `threading.Lock`
  - PostgreSQL 模式：`SELECT ... FOR UPDATE` 或 advisory lock
  - Redis 模式：`redis.lock.Lock`（如果 P1 实现了 Redis 后端）
- [ ] 6.2 在 `StorageNameSpace` 中添加 `workspace` 字段
  - 所有存储 key 前缀化：`{workspace}:{namespace}:{key}`
- [ ] 6.3 在 `KnowledgeV2Service` 中支持 `workspace` 参数
- [ ] 6.4 编写并发测试：多 worker 同时 upsert 同一 entity

---

## P1 — 成本与性能优化

### P1-1: 角色级 LLM 路由

**目标**：4 个 LLM 角色（extract, keyword, query, vlm）可独立绑定不同模型

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-core/src/aurora_core/model/roles.py`
- 修改：`packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`（使用角色路由）
- 修改：`packages/aurora-ext/src/aurora_ext/rag/extraction/extractor.py`（使用 extract 角色）
- 修改：`packages/aurora-ext/src/aurora_ext/rag/retrieval/keyword_extractor.py`（使用 keyword 角色）
- 修改：`packages/aurora-ext/src/aurora_ext/rag/retrieval/query_engine.py`（使用 query 角色）

**实施步骤**：

- [ ] 1.1 定义角色枚举和配置
  ```python
  class LLMRole(str, Enum):
      EXTRACT = "extract"    # 实体/关系抽取
      KEYWORD = "keyword"    # 查询关键词提取
      QUERY = "query"        # 最终 RAG 回答生成
      VLM = "vlm"           # 视觉语言模型（P2 多模态用）

  @dataclass
  class RoleLLMConfig:
      model_name: str
      model_type: str = "openai"
      max_async: int = 4
      timeout: int = 180
      kwargs: dict = field(default_factory=dict)
  ```
- [ ] 1.2 实现 `LLMRoleRegistry`
  - 每个角色独立 `BaseLLM` 实例
  - 默认所有角色使用 `default_llm`
  - 支持运行时热切换：`update_role_config(role, new_config)`
  - 并发队列隔离：每个角色独立 `asyncio.Semaphore`
- [ ] 1.3 修改 extractor 使用 `role_registry.get_llm(LLMRole.EXTRACT)`
- [ ] 1.4 修改 keyword_extractor 使用 `role_registry.get_llm(LLMRole.KEYWORD)`
- [ ] 1.5 修改 query_engine 使用 `role_registry.get_llm(LLMRole.QUERY)`
- [ ] 1.6 添加队列状态监控 API：`GET /api/v1/models/queue-status`
- [ ] 1.7 配置扩展：
  ```toml
  [knowledge.llm_roles]
  extract_model = "gpt-4o-mini"      # 便宜模型做抽取
  keyword_model = "gpt-4o-mini"      # 快速模型做关键词
  query_model = "gpt-4o"             # 强模型做回答
  ```
- [ ] 1.8 编写测试：角色路由、热切换、并发隔离

---

### P1-2: Embedding 缓存系统

**目标**：避免重复计算 embedding，降低成本 50%+

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-core/src/aurora_core/rag/utils/embedding_cache.py`
- 修改：`packages/aurora-core/src/aurora_core/rag/utils/embedding.py`（集成缓存）

**实施步骤**：

- [ ] 2.1 实现 `EmbeddingCache`
  ```python
  @dataclass
  class EmbeddingCacheConfig:
      enabled: bool = False
      similarity_threshold: float = 0.95  # 余弦相似度 ≥ 此值时复用
      use_llm_check: bool = False          # 用 LLM 验证缓存正确性
      storage_backend: str = "json"        # 缓存存储后端
  ```
- [ ] 2.2 缓存查找流程
  1. 计算查询文本的 hash
  2. 精确匹配：hash 相同直接返回
  3. 近似匹配：从缓存中检索相似 embedding，余弦相似度 ≥ threshold 时复用
  4. LLM 验证（可选）：让 LLM 判断缓存结果是否等价
  5. 未命中：计算新 embedding，写入缓存
- [ ] 2.3 修改 `EmbeddingFunc.__call__` 在调用前检查缓存
- [ ] 2.4 添加配置项：
  ```toml
  [knowledge.embedding_cache]
  enabled = true
  similarity_threshold = 0.95
  use_llm_check = false
  ```
- [ ] 2.5 编写测试：缓存命中、近似匹配、LLM 验证

---

### P1-3: Azure OpenAI + Ollama 原生 LLM 绑定

**目标**：扩展 LLM 提供商支持，覆盖企业常用场景

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-core/src/aurora_core/model/adapter/azure_openai_adapter.py`
- 新增：`packages/aurora-core/src/aurora_core/model/adapter/ollama_adapter.py`

**实施步骤**：

- [ ] 3.1 实现 Azure OpenAI Adapter
  - 继承 `BaseLLM`
  - 使用 `azure-openai` SDK 或 `openai` 的 Azure 配置
  - 支持 `api_version`, `deployment_name`, `azure_endpoint`
  - 配置示例：
    ```toml
    [[llm_configs]]
    model_name = "gpt-4o"
    model_type = "azure_openai"
    azure_endpoint = "https://my-resource.openai.azure.com"
    api_version = "2024-02-15-preview"
    deployment_name = "gpt-4o-deployment"
    ```
- [ ] 3.2 实现 Ollama 原生 Adapter
  - 继承 `BaseLLM`
  - 使用 `ollama` Python SDK 或 HTTP API
  - 支持 `base_url`（默认 `http://localhost:11434`）
  - 支持 streaming
  - 支持 embedding 函数（`/api/embed`）
  - 配置示例：
    ```toml
    [[llm_configs]]
    model_name = "llama3"
    model_type = "ollama"
    api_base = "http://localhost:11434"
    ```
- [ ] 3.3 在 `ModelRegistry` 中注册新 adapter
- [ ] 3.4 编写测试：Azure 连接、Ollama 本地模型调用

---

### P1-4: Reranking 增强

**目标**：补齐 Aliyun DashScope 支持 + 高级重排策略

**前置条件**：无

**涉及文件**：
- 修改：`packages/aurora-ext/src/aurora_ext/rag/retrieval/reranker.py`

**实施步骤**：

- [ ] 4.1 实现 `AliyunReranker(RerankerBase)`
  - 端点：`https://dashscope.aliyuncs.com/api/v1/services/rerank`
  - 模型：`gte-rerank-v2`
  - 认证：`DASHSCOPE_API_KEY` 环境变量
  - 响应格式适配（与 Cohere/Jina 不同）
- [ ] 4.2 添加长文分块重排
  ```python
  @dataclass
  class RerankOptions:
      enable_chunking: bool = False     # 对超长文档分块后分别评分
      max_tokens_per_doc: int = 4096    # 每块最大 token
      score_aggregation: str = "max"    # max / mean / first
      min_score: float = 0.0           # 最低分数阈值
  ```
- [ ] 4.3 实现分数聚合策略
  - `max`: 取所有块中最高分
  - `mean`: 取平均分
  - `first`: 取第一块分数
- [ ] 4.4 实现指数退避重试（3 次, min 4s, max 60s）
- [ ] 4.5 在 `query_engine.py` 中集成 `RerankOptions`
- [ ] 4.6 添加配置：
  ```toml
  [knowledge.rerank]
  provider = "cohere"           # cohere / jina / aliyun
  min_score = 0.3
  score_aggregation = "max"
  ```
- [ ] 4.7 编写测试：三种 provider、聚合策略、分块重排

---

### P1-5: 实体抽取调优参数

**目标**：补齐 LightRAG 中全部抽取调优参数

**前置条件**：无

**涉及文件**：
- 修改：`packages/aurora-ext/src/aurora_ext/rag/extraction/extractor.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/extraction/merger.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/extraction/summarizer.py`
- 修改：`packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`

**实施步骤**：

- [ ] 5.1 添加缺失的抽取参数
  ```python
  @dataclass
  class ExtractionConfig:
      # 已有
      max_gleaning: int = 1
      max_total_records: int = 100
      max_entity_records: int = 40
      use_json: bool = True
      language: str = "Chinese"
      # 新增
      force_llm_summary_on_merge: int = 8      # 描述超过 N 段时触发 LLM 摘要
      summary_max_tokens: int = 1200            # 摘要最大 token 数
      summary_context_size: int = 12000         # 摘要上下文大小
      source_ids_limit_method: str = "FIFO"     # FIFO / KEEP
      max_source_ids_per_entity: int = 300      # 每个实体最大 source ID 数
      max_source_ids_per_relation: int = 300    # 每个关系最大 source ID 数
      max_file_paths: int = 100                 # 每个实体最大文件路径数
  ```
- [ ] 5.2 在 merger 中实现 `force_llm_summary_on_merge`
  - 当描述片段数 ≥ threshold 时，调用 summarizer 进行 LLM 摘要
  - 否则简单拼接
- [ ] 5.3 在 merger 中实现 `source_ids_limit_method`
  - `FIFO`: 保留最新 N 个 source ID
  - `KEEP`: 保留最早 N 个 source ID
- [ ] 5.4 在 service 中暴露配置到知识库创建/更新 API
- [ ] 5.5 编写测试：参数生效、边界条件

---

### P1-6: 查询微调参数补齐

**目标**：补齐 LightRAG 中全部查询调优参数

**前置条件**：无

**涉及文件**：
- 修改：`packages/aurora-ext/src/aurora_ext/rag/retrieval/query_engine.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/retrieval/context_builder.py`

**实施步骤**：

- [ ] 6.1 添加缺失参数到 `QueryParam`
  ```python
  related_chunk_number: int = 5        # 每个实体/关系的关联 chunk 数
  kg_chunk_pick_method: str = "VECTOR" # VECTOR / WEIGHT — chunk 选择算法
  cosine_better_than_threshold: float = 0.2  # 向量相似度阈值
  max_graph_nodes: int = 1000          # 最大返回图节点数（可配置）
  ```
- [ ] 6.2 实现 `kg_chunk_pick_method`
  - `VECTOR`: 按 embedding 相似度选择关联 chunk（当前默认）
  - `WEIGHT`: 按实体/关系权重选择关联 chunk
- [ ] 6.3 实现 `related_chunk_number`：限制每个实体/关系最多关联 N 个 chunk
- [ ] 6.4 将 `max_graph_nodes` 从硬编码改为可配置
- [ ] 6.5 编写测试：不同参数组合下的检索结果

---

### P1-7: Skip KG Extraction（`!` 标记实现）

**目标**：让文档可以仅做 chunk 入库，跳过知识图谱构建（更快入库）

**前置条件**：无

**涉及文件**：
- 修改：`packages/aurora-ext/src/aurora_ext/rag/parser/routing.py`（已解析 `!` 标记）
- 修改：`packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`（管线中检查标记）

**实施步骤**：

- [ ] 7.1 确认 `routing.py` 已解析 `!` hint 到 `ParseOptions.skip_kg`
- [ ] 7.2 在 `_process_worker` 中添加分支：
  ```python
  if doc_info.parse_options.skip_kg:
      # 只做 chunking + embedding，跳过实体/关系抽取
      chunks = chunker.split(raw_text)
      for chunk in chunks:
          await vector_storage.upsert(...)
      # 不创建 graph 节点/边
  else:
      # 正常流程：抽取 + 图谱 + embedding
      ...
  ```
- [ ] 7.3 跳过 KG 的文档仍可通过 `naive` 模式查询
- [ ] 7.4 编写测试：`!` 标记文档的处理流程

---

### P1-8: 文件名去重 + 审计追踪

**目标**：补全双维度去重（文件名 + 内容哈希），添加审计元数据

**前置条件**：无

**涉及文件**：
- 修改：`packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/storage/base.py`（DocStatusInfo 添加字段）

**实施步骤**：

- [ ] 8.1 在 `DocStatusInfo` 中添加字段：
  ```python
  content_hash: str = ""           # 内容 MD5 哈希
  duplicate_kind: str = ""         # "filename" / "content_hash" / ""
  basename: str = ""               # 文件名（不含路径）
  ```
- [ ] 8.2 在 `BaseDocStatusStorage` 中添加查询方法：
  ```python
  async def get_doc_by_basename(self, basename: str, *, kb_name: str) -> Optional[DocStatusInfo]: ...
  async def get_doc_by_content_hash(self, content_hash: str, *, kb_name: str) -> Optional[DocStatusInfo]: ...
  ```
- [ ] 8.3 在 `upload_file()` 中实现双维度去重：
  1. 先查 `basename` 是否已存在 → `duplicate_kind = "filename"`
  2. 再查 `content_hash` 是否已存在 → `duplicate_kind = "content_hash"`
- [ ] 8.4 JSON DocStatus 实现新方法（内存扫描）
- [ ] 8.5 PostgreSQL DocStatus 实现新方法（索引查询）
- [ ] 8.6 编写测试：文件名去重、内容哈希去重、审计字段

---

## P2 — 解析质量 + 高级特性

### P2-1: MinerU 解析引擎集成

**目标**：GPU 加速的 PDF/文档解析，大幅提升解析质量

**前置条件**：MinerU 服务运行中

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/rag/parser/mineru_parser.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/parser/routing.py`

**实施步骤**：

- [ ] 1.1 安装依赖：`magic-pdf` (MinerU Python SDK)
- [ ] 1.2 实现 `MinerUParser(BaseParser)`
  - 支持格式：PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, PNG, JPG, JPEG, WEBP, GIF, BMP
  - 调用方式：本地 SDK 或远程 API（通过 `MINERU_API_URL` 环境变量选择）
  - 输出：纯文本 + 结构化 blocks（段落、表格、图片描述）
  - 表格处理：HTML 表格标记保留
  - 图片处理：提取图片并生成描述（如有 VLM）
- [ ] 1.3 在 `routing.py` 中添加路由规则
  - 默认：PDF 走 MinerU（如果可用），否则 fallback 到 pypdf
  - 文件名 hint `native` 强制使用内置解析器
  - 环境变量：`AURORA_PARSER_ENGINE=pdf:mineru` 覆盖默认路由
- [ ] 1.4 添加并发控制：MinerU GPU 密集，默认 `max_parallel=1`
- [ ] 1.5 编写测试：PDF 解析质量对比

---

### P2-2: Docling 解析引擎集成

**目标**：IBM Docling 作为备选高级解析引擎

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/rag/parser/docling_parser.py`
- 修改：`packages/aurora-ext/src/aurora_ext/rag/parser/routing.py`

**实施步骤**：

- [ ] 2.1 安装依赖：`docling`
- [ ] 2.2 实现 `DoclingParser(BaseParser)`
  - 支持格式：PDF, DOCX, PPTX, XLSX, MD, HTML, PNG, JPG, TIFF, WEBP, BMP
  - 调用 `DocumentConverter` API
  - 输出：Markdown 格式文本 + 结构化元素
- [ ] 2.3 路由集成：文件名 hint `docling` 或环境变量 `AURORA_PARSER_ENGINE=pdf:docling`
- [ ] 2.4 编写测试

---

### P2-3: 多模态 VLM 分析层

**目标**：添加第三层管线，处理文档中的图像/表格/公式

**前置条件**：P1-1（角色级 LLM 路由，需要 VLM 角色）

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/rag/extraction/multimodal_analyzer.py`
- 新增：`packages/aurora-ext/src/aurora_ext/rag/extraction/multimodal_prompts.py`
- 修改：`packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`（添加第三层队列）

**实施步骤**：

- [ ] 3.1 实现 `MultimodalAnalyzer`
  ```python
  class MultimodalAnalyzer:
      def __init__(self, vlm_llm: BaseLLM):
          self.vlm_llm = vlm_llm

      async def analyze_image(self, image_bytes: bytes, context: str) -> str:
          """VLM 描述图片内容"""

      async def analyze_table(self, table_html: str, context: str) -> str:
          """VLM 结构化提取表格数据"""

      async def analyze_equation(self, equation_image: bytes) -> str:
          """VLM 识别数学公式"""
  ```
- [ ] 3.2 添加管线第三层：`q_analyze`
  - 在 `q_parse` 和 `q_process` 之间插入
  - 仅处理带有 `i/t/e` 标记的文档
  - 无标记的文档直接跳过此层
- [ ] 3.3 VLM prompt 模板
  - 图片描述 prompt：描述图片内容，结合周围文本上下文
  - 表格提取 prompt：将表格图片转为结构化数据
  - 公式识别 prompt：将公式图片转为 LaTeX
- [ ] 3.4 Sidecar 持久化：分析结果存入 `.blocks.jsonl` 文件
- [ ] 3.5 最小像素阈值过滤：`DEFAULT_MM_IMAGE_MIN_PIXEL = 32`
- [ ] 3.6 编写测试

---

### P2-4: 自定义知识图谱批量注入

**目标**：支持批量导入手工构建的知识图谱条目

**前置条件**：无

**涉及文件**：
- 新增：API 端点在 `packages/aurora-serve/src/aurora_serve/knowledge/v2/graph_routes.py`
- 修改：`packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`

**实施步骤**：

- [ ] 4.1 定义输入 schema
  ```python
  @dataclass
  class KnowledgeGraphNode:
      id: str
      label: str
      entity_type: str
      description: str
      metadata: dict = field(default_factory=dict)

  @dataclass
  class KnowledgeGraphEdge:
      source_id: str
      target_id: str
      description: str
      keywords: list[str] = field(default_factory=list)

  @dataclass
  class CustomKnowledgeGraph:
      nodes: list[KnowledgeGraphNode]
      edges: list[KnowledgeGraphEdge]
  ```
- [ ] 4.2 实现 `insert_custom_kg(kb_name, custom_kg, doc_id)`
  - 批量 upsert 节点到 graph storage
  - 批量 upsert 边到 graph storage
  - 同步更新 vector storage（embedding 节点描述）
  - 更新 source_id 追踪
- [ ] 4.3 添加 API 端点：`POST /api/v1/knowledge/{name}/graph/import`
- [ ] 4.4 编写测试

---

### P2-5: RAGAS 评估框架

**目标**：量化 RAG 检索和生成质量

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-ext/src/aurora_ext/evaluation/__init__.py`
- 新增：`packages/aurora-ext/src/aurora_ext/evaluation/rag_quality.py`
- 新增：`packages/aurora-ext/src/aurora_ext/evaluation/retrieval_check.py`
- 新增：API 端点在 `packages/aurora-serve/src/aurora_serve/evaluation/api.py`

**实施步骤**：

- [ ] 5.1 安装依赖：`ragas`, `datasets`
- [ ] 5.2 实现 RAG 质量评估
  ```python
  class RAGQualityEvaluator:
      async def evaluate(
          self,
          questions: list[str],
          ground_truths: list[str],
          kb_name: str,
          modes: list[str] = ["mix", "naive", "local", "global"],
      ) -> dict:
          """返回 faithfulness, answer_relevancy, context_precision, context_recall"""
  ```
- [ ] 5.3 实现离线检索检查
  ```python
  class OfflineRetrievalChecker:
      async def check(
          self,
          queries: list[str],
          expected_entities: list[list[str]],
          kb_name: str,
      ) -> dict:
          """检查检索是否正确返回了预期的实体"""
  ```
- [ ] 5.4 添加 API 端点：
  - `POST /api/v1/evaluation/rag-quality` — 运行 RAG 质量评估
  - `POST /api/v1/evaluation/retrieval-check` — 运行检索检查
- [ ] 5.5 前端评估页面集成（可选）

---

### P2-6: Docker 部署方案

**目标**：标准化容器部署，支持 Docker Compose 一键启动

**前置条件**：P0 完成

**涉及文件**：
- 新增：`Dockerfile`
- 新增：`Dockerfile.lite`（精简版）
- 新增：`docker-compose.yml`
- 新增：`docker-compose-full.yml`（含 PostgreSQL + Neo4j + Milvus）

**实施步骤**：

- [ ] 6.1 编写 `Dockerfile`
  ```dockerfile
  FROM python:3.12-slim
  WORKDIR /app
  COPY pyproject.toml uv.lock ./
  RUN pip install uv && uv sync --frozen
  COPY . .
  EXPOSE 8888
  CMD ["uv", "run", "uvicorn", "aurora_app.main:app", "--host", "0.0.0.0", "--port", "8888"]
  ```
- [ ] 6.2 编写 `Dockerfile.lite`（无前端、无 GPU 依赖）
- [ ] 6.3 编写 `docker-compose.yml`（基础版）
  - Aurora 后端 + ChromaDB + 前端
- [ ] 6.4 编写 `docker-compose-full.yml`（完整版）
  - Aurora 后端 + PostgreSQL + Neo4j + Milvus + Redis + 前端
  - 健康检查配置
  - 数据卷持久化
- [ ] 6.5 添加 `.dockerignore`
- [ ] 6.6 编写部署文档 `docs/deployment.md`

---

### P2-7: 可观测性增强

**目标**：添加健康检查、队列监控、管线追踪

**前置条件**：无

**涉及文件**：
- 新增：`packages/aurora-serve/src/aurora_serve/health/service.py`
- 修改：`packages/aurora-serve/src/aurora_serve/health/api.py`

**实施步骤**：

- [ ] 7.1 增强健康检查端点 `GET /health`
  ```python
  {
      "status": "healthy",
      "version": "0.1.0",
      "uptime_seconds": 12345,
      "storage_backends": {
          "kv": "postgres_kv",
          "vector": "milvus",
          "graph": "neo4j",
          "doc_status": "postgres_doc_status"
      },
      "pipeline": {
          "is_busy": false,
          "queue_sizes": {"parse": 0, "process": 0},
          "active_workers": {"parse": 0, "process": 0}
      },
      "llm_roles": {
          "extract": {"model": "gpt-4o-mini", "queue_size": 0},
          "keyword": {"model": "gpt-4o-mini", "queue_size": 0},
          "query": {"model": "gpt-4o", "queue_size": 0}
      }
  }
  ```
- [ ] 7.2 添加管线追踪 API
  - `GET /api/v1/knowledge/{name}/pipeline/traces` — 返回管线执行追踪
  - 记录每个文档的阶段耗时：parsing_time, processing_time, total_time
- [ ] 7.3 添加管线阶段计时到 `DocStatusInfo`
  ```python
  parsing_start_time: str = ""
  parsing_end_time: str = ""
  processing_start_time: str = ""
  processing_end_time: str = ""
  ```
- [ ] 7.4 Langfuse 集成（可选）：
  ```toml
  [observability]
  langfuse_enabled = false
  langfuse_public_key = ""
  langfuse_secret_key = ""
  langfuse_host = "https://cloud.langfuse.com"
  ```

---

## 附录：任务依赖关系

```
P0-1 (PostgreSQL KV/DocStatus) ──┐
P0-2 (Neo4j Graph)               ├──→ P0-5 (Storage Factory) ──→ P0-6 (Shared Lock)
P0-3 (Milvus Vector)             ─┘

P0-4 (Auth) ──→ (独立，无前置依赖)

P1-1 (LLM Roles) ──→ P2-3 (VLM 多模态)
P1-2 (Embedding Cache) ──→ (独立)
P1-3 (Azure/Ollama) ──→ (依赖 P1-1 可热切换)
P1-4 (Reranking) ──→ (独立)
P1-5 (Extraction Params) ──→ (独立)
P1-6 (Query Params) ──→ (独立)
P1-7 (Skip KG) ──→ (独立)
P1-8 (Dedup) ──→ (依赖 P0-1 或 JSON 实现)

P2-1 (MinerU) ──→ (独立)
P2-2 (Docling) ──→ (独立)
P2-3 (VLM) ──→ (依赖 P1-1)
P2-4 (Custom KG) ──→ (独立)
P2-5 (Evaluation) ──→ (独立)
P2-6 (Docker) ──→ (依赖 P0 完成)
P2-7 (Observability) ──→ (独立)
```

## 附录：快速启动指南

```bash
# P0 开发环境准备
uv add asyncpg psycopg[binary,pool] neo4j pymilvus PyJWT "passlib[bcrypt]"

# P1 开发环境准备
uv add azure-openai ollama dashscope  # 按实际 SDK 包名调整

# P2 开发环境准备
uv add magic-pdf docling ragas datasets
```

---

> **最后更新**: 2026-06-01
> **分析基础**: Aurora-Design (当前 HEAD) vs LightRAG (HKUDS/LightRAG HEAD)
