# 彻底移植 LightRAG 图谱渲染引擎（从 ECharts 切换至 Sigma.js）

问题描述：用户指出当前的知识图谱与 LightRAG 在 UI 细节、鼠标悬停交互、右侧属性面板等方面存在明显差异。经查，这是因为底层渲染引擎不同（ECharts vs Sigma.js）。为实现真正的“完全移植”，我们需要将底层组件全量替换为 LightRAG 原生的组件代码。

## 待办事项 / Inspectable Items

- [x] **依赖安装**：在 `frontend/package.json` 中安装 `sigma`, `@react-sigma/core`, `graphology` 及其相关插件包。
- [x] **拷贝组件**：从 `lightrag_webui/src/components/graph` 拷贝所有的左侧控件和右侧面板代码到本项目中。
- [x] **拷贝状态库**：从 `lightrag_webui/src/stores` 拷贝图谱相关的 `zustand` Store（`graph.ts`, `settings.ts`）。
- [x] **拷贝主容器**：拷贝 `GraphViewer.tsx`，并对其进行必要的路由和 API 钩子适配。
- [x] **数据层适配**：修改图谱数据入口，将原先传给 ECharts 的 `nodes/edges` 转换为 `graphology.DirectedGraph` 实例。
- [x] **清理冗余**：移除旧版的 ECharts 图谱相关代码。

## 新阶段待办事项（2026-05-29） / Phase 2: Debug Empty Graph & Support General Preview

- [x] **后端代码修改**：修改后端的 `NetworkXGraphStorage.get_connected_subgraph` 接口（`/Users/wyl/Desktop/Aurora-Design/packages/aurora-ext/src/aurora_ext/rag/storage/networkx_graph.py`），使它在 `label` 为 `*` 或空时，不再抛出或返回空，而是返回按度数排序的核心节点以及它们之间的边。
- [x] **前端代码确认**：核对 `useLightragGraph.tsx` 中 fetch 时的 label 处理逻辑，确认当 `queryLabel` 为空时成功查询 `*` 并拉取后端的全量预览。
- [x] **前后台联调测试**：运行或测试接口，确保初次加载知识图谱时能够完整渲染出丰富的节点与关系边，而不再是只有一个灰色的占位节点。
- [x] **清除临时调试样式**：移除之前遗留 of 红色调试 overlay 文本，恢复纯净精致 of UI。

## 阶段三待办事项（2026-06-01） / Phase 3: Comprehensive Localization & Translation for Knowledge Base V2

- [x] **多语言脚本开发与 Key 同步**：编写或更新 Python 自动化脚本，将新增的多语言 key 同步注入到 `frontend/src/i18n/types.ts` 和 `frontend/src/i18n/locales/*.ts` 所有 16 个语言文件中，避免 TypeScript 编译报错。
- [x] **文档管理组件国际化**：重构 `DocumentManager.tsx`，将所有硬编码英文/中文（如 `All`, `Upload`, `Insert Text`, `No documents found` 等）替换为 `t(...)` 调用。
- [x] **上传文件对话框国际化**：重构 `UploadDialog.tsx`，提取拖拽、失败信息、重试状态等硬编码中文和英文为多语言。
- [x] **设置组件国际化**：重构 `KnowledgeSettings.tsx`，将 `Knowledge Base Info`, `Chunk Configuration`, `Danger Zone` 等及里面的表单文本全部应用国际化。
- [x] **属性面板与字段名国际化**：在多语言文件中补充常用的实体属性名翻译（如 `description` -> `描述`, `entity_id` -> `实体 ID`, `entity_type` -> `实体类型`, `keywords` -> `关键词`, `source_id` -> `源 ID`），以及邻居关系字段名翻译，使图谱属性面板显示纯中文。
- [x] **本地验证与构建测试**：运行 `npx tsc --noEmit` 进行 TypeScript 类型安全验证，确保 16 个 locale 文件在追加 key 后能够正常编译。

## 阶段四待办事项（2026-06-01） / Phase 4: Fix Graph Legend Z-Index and Direct Chinese Extraction

- [x] **修复图例层级物理遮挡**：在 `GraphViewer.tsx` 中，将包裹 `<Legend>` 的外层 `div` 的定位类从 `z-0` 修改为 `z-10`，解决图例不显示及无法交互的 Bug。
- [x] **后端大模型抽取语言参数修正**：在 `service.py` 的 `extractor.extract` 中，显式添加 `language="Chinese"`。从源头上解决“大模型提取英文连线”的问题，直接让知识库解析出的实体、关系和属性自带纯正中文，保持数据和界面的纯净，前端不进行任何翻译改动。
- [x] **整体验证与 TSC 检测**：执行 `npx tsc --noEmit` 并查看效果，确保全功能无错运行。

## 验证与审查 (Review)
**完成情况**：
1. 已成功安装 sigma.js 及其相关的布局（circlepack, force, noverlap, random）库。
2. 完整拷贝了原版 LightRAG 的 GraphViewer、PropertiesView、Settings、ZoomControl 等组件，确保样式 1:1 还原。
3. 重构了 `useLightragGraph` 和 `use-knowledge-v2` 数据对接，接入了后端的 `getGraphSubgraph` 接口。
4. 修复了 UI 组件的导入路径，适配了 Aurora-Design 内部自带 of shadcn UI，并补充了缺失的基础组件（如 cmdk）。
5. 编译通过 (`vite build` 测试无误)。

---

## 阶段五（2026-06-01） / Phase 5: Aurora vs LightRAG 差异补齐

> 详细计划见 `tasks/gap-closure-plan.md`
> 基于 2026-06-01 对两个项目的深度对比分析

### P0 — 生产可用性（阻塞上线）

#### P0-1: PostgreSQL 存储后端（KV + DocStatus）
- [ ] 1.1 安装依赖：`asyncpg`, `psycopg[binary,pool]`
- [ ] 1.2 实现 `PostgresKVStorage(BaseKVStorage)` — 表结构 + CRUD + 连接池
- [ ] 1.3 实现 `PostgresDocStatusStorage(BaseDocStatusStorage)` — 分页/过滤/聚合
- [ ] 1.4 编写测试 `tests/test_postgres_storage.py`
- [ ] 1.5 注册后端到 `storage/__init__.py`
- [ ] 1.6 添加 `aurora.toml` 配置项
- [ ] 1.7 编写 JSON → PostgreSQL 数据迁移脚本

#### P0-2: Neo4j 图存储后端
- [ ] 2.1 安装依赖：`neo4j` Python driver
- [ ] 2.2 实现 `Neo4jGraphStorage(BaseGraphStorage)` — Cypher 查询全覆盖
- [ ] 2.3 索引优化：Entity.id 唯一索引 + 全文索引
- [ ] 2.4 编写测试 `tests/test_neo4j_storage.py`
- [ ] 2.5 注册后端 + 配置
- [ ] 2.6 NetworkX → Neo4j 数据迁移脚本

#### P0-3: Milvus 向量存储后端
- [ ] 3.1 安装依赖：`pymilvus`
- [ ] 3.2 实现 `MilvusVectorStorage(BaseVectorStorage)` — Collection + HNSW 索引
- [ ] 3.3 （可选）实现 `QdrantVectorStorage`
- [ ] 3.4 编写测试
- [ ] 3.5 注册后端 + 配置

#### P0-4: JWT + API Key 认证
- [ ] 4.1 安装依赖：`PyJWT`, `passlib[bcrypt]`
- [ ] 4.2 实现 JWT Handler（create/verify/refresh token）
- [ ] 4.3 实现 API Key Handler（SHA-256 哈希存储）
- [ ] 4.4 实现认证中间件（FastAPI Depends）
- [ ] 4.5 添加登录端点 `/api/v1/auth/*`
- [ ] 4.6 挂载到现有路由
- [ ] 4.7 编写测试
- [ ] 4.8 CLI 密码哈希工具

#### P0-5: 存储后端工厂 + 运行时切换
- [ ] 5.1 实现 `StorageFactory`（register + create_kv/vector/graph/doc_status）
- [ ] 5.2 自动注册所有内置后端
- [ ] 5.3 修改 `KnowledgeV2Service` 使用工厂
- [ ] 5.4 添加环境变量覆盖
- [ ] 5.5 编写测试

#### P0-6: 跨进程锁 + 工作空间隔离
- [ ] 6.1 实现 `SharedLock` 抽象（本地/PostgreSQL/Redis 模式）
- [ ] 6.2 在 `StorageNameSpace` 添加 workspace 字段
- [ ] 6.3 在 `KnowledgeV2Service` 支持 workspace 参数
- [ ] 6.4 编写并发测试

### P1 — 成本与性能优化

#### P1-1: 角色级 LLM 路由
- [ ] 1.1 定义 LLMRole 枚举 + RoleLLMConfig
- [ ] 1.2 实现 LLMRoleRegistry（热切换 + 并发队列隔离）
- [ ] 1.3 修改 extractor → EXTRACT 角色
- [ ] 1.4 修改 keyword_extractor → KEYWORD 角色
- [ ] 1.5 修改 query_engine → QUERY 角色
- [ ] 1.6 添加队列状态监控 API
- [ ] 1.7 配置扩展
- [ ] 1.8 编写测试

#### P1-2: Embedding 缓存系统
- [ ] 2.1 实现 EmbeddingCache（精确 + 近似匹配 + LLM 验证）
- [ ] 2.2 修改 EmbeddingFunc 集成缓存
- [ ] 2.3 配置项
- [ ] 2.4 编写测试

#### P1-3: Azure OpenAI + Ollama 原生绑定
- [ ] 3.1 实现 Azure OpenAI Adapter
- [ ] 3.2 实现 Ollama 原生 Adapter（含 embedding）
- [ ] 3.3 注册到 ModelRegistry
- [ ] 3.4 编写测试

#### P1-4: Reranking 增强 ✅ COMPLETED
- [x] 4.1 实现 AliyunReranker（DashScope gte-rerank-v2）
- [x] 4.2 添加长文分块重排 + RerankOptions
- [x] 4.3 实现分数聚合策略（max/mean/first）
- [x] 4.4 实现指数退避重试
- [x] 4.5 集成到 query_engine（mix 模式默认启用）
- [x] 4.6 配置 + 测试（32 个测试全部通过）
- [x] 4.7 实现 vLLM Reranker（Cohere API 兼容）
- [x] 4.8 实现 RerankerConfig 和工厂模式
- [x] 4.9 实现 RobustReranker（错误处理、降级、熔断器）
- [x] 4.10 添加 TOML 配置和环境变量支持
- [x] 4.11 编写完整文档（RERANKER.md）

#### P1-5: 实体抽取调优参数
- [ ] 5.1 添加缺失参数（force_llm_summary, source_ids_limit 等）
- [ ] 5.2 在 merger 中实现 LLM 摘要触发
- [ ] 5.3 实现 source_ids_limit_method（FIFO/KEEP）
- [ ] 5.4 暴露到 API
- [ ] 5.5 编写测试

#### P1-6: 查询微调参数补齐
- [ ] 6.1 添加 related_chunk_number, kg_chunk_pick_method, cosine_threshold
- [ ] 6.2 实现 VECTOR/WEIGHT chunk 选择算法
- [ ] 6.3 max_graph_nodes 可配置化
- [ ] 6.4 编写测试

#### P1-7: Skip KG Extraction（`!` 标记实现）
- [ ] 7.1 确认 routing.py 已解析 `!` hint
- [ ] 7.2 在 _process_worker 添加跳过分支
- [ ] 7.3 编写测试

#### P1-8: 文件名去重 + 审计追踪
- [ ] 8.1 DocStatusInfo 添加 content_hash, duplicate_kind, basename
- [ ] 8.2 BaseDocStatusStorage 添加 get_doc_by_basename/content_hash
- [ ] 8.3 upload_file 实现双维度去重
- [ ] 8.4 JSON + PostgreSQL 实现
- [ ] 8.5 编写测试

### P2 — 解析质量 + 高级特性

#### P2-1: MinerU 解析引擎 ✅
- [x] 1.1 添加 magic-pdf 可选依赖到 pyproject.toml
- [x] 1.2 实现 MinerUParser（SDK + HTTP API 双模式，asyncio.Semaphore 并发控制）
- [x] 1.3 路由集成（hint > env > default，graceful fallback）
- [x] 1.4 编写测试（34 tests passing）

#### P2-2: Docling 解析引擎 ✅
- [x] 2.1 添加 docling 可选依赖到 pyproject.toml
- [x] 2.2 实现 DoclingParser（DocumentConverter API，线程池异步）
- [x] 2.3 路由集成（hint/env/native 三级路由 + fallback）
- [x] 2.4 编写测试（34 tests passing）

#### P2-3: 多模态 VLM 分析层
- [ ] 3.1 实现 MultimodalAnalyzer（图像/表格/公式）
- [ ] 3.2 添加管线第三层 q_analyze
- [ ] 3.3 VLM prompt 模板
- [ ] 3.4 Sidecar 持久化
- [ ] 3.5 编写测试

#### P2-4: 自定义知识图谱批量注入
- [ ] 4.1 定义 CustomKnowledgeGraph schema
- [ ] 4.2 实现 insert_custom_kg()
- [ ] 4.3 添加 API 端点
- [ ] 4.4 编写测试

#### P2-5: RAGAS 评估框架
- [x] 5.1 添加 ragas + datasets + langchain-core 可选依赖
- [x] 5.2 实现 RAGASEvaluator（faithfulness/answer_relevancy/context_precision/context_recall）
- [x] 5.3 实现 LangChain 适配器（wrap_llm / wrap_embeddings）
- [x] 5.4 添加 API 端点（POST /knowledge/{name}/evaluate + /evaluate/html）

#### P2-6: Docker 部署方案
- [x] 6.1 Dockerfile（标准版 — 多阶段构建: deps + frontend + runtime）
- [x] 6.2 Dockerfile.lite（精简版 — 仅后端，无可选依赖和前端）
- [x] 6.3 docker-compose.yml（基础版 — Aurora + Redis）
- [x] 6.4 docker-compose.full.yml（含 PG + Neo4j + Milvus + Redis + etcd + MinIO）
- [x] 6.5 部署文档（docs/deployment/docker.md + README 更新）

#### P2-7: 可观测性增强 ✅
- [x] 7.1 增强健康检查端点（存储后端 + 管线 + LLM 角色状态）
- [x] 7.2 管线追踪 API + 阶段计时
- [x] 7.3 Prometheus 指标导出（/metrics 端点）
- [x] 7.4 内存指标收集器（pipeline 性能、LLM 调用、缓存命中率）
- [x] 7.5 Readiness/Liveness 探针（K8s 兼容）

---

## 阶段六（2026-06-01） / Phase 6: Storage Backend Expansion (13 new backends)

> 从 ~8 种存储扩展到完整支持 21 种后端

### KV Storage (3 new)
- [ ] RedisKVStorage → `redis_kv.py`
- [ ] MongoKVStorage → `mongo_kv.py`
- [ ] OpenSearchKVStorage → `opensearch_kv.py`

### Vector Storage (5 new)
- [ ] PGVectorStorage → `pgvector.py`
- [ ] FaissVectorDBStorage → `faiss_vector.py`
- [ ] QdrantVectorDBStorage → `qdrant_vector.py`
- [ ] MongoVectorDBStorage → `mongo_vector.py`
- [ ] OpenSearchVectorDBStorage → `opensearch_vector.py`

### Graph Storage (3 new)
- [ ] PGGraphStorage → `pg_graph.py`
- [ ] MemgraphStorage → `memgraph_graph.py`
- [ ] OpenSearchGraphStorage → `opensearch_graph.py`

### Doc Status Storage (2 new)
- [ ] MongoDocStatusStorage → `mongo_doc_status.py`
- [ ] OpenSearchDocStatusStorage → `opensearch_doc_status.py`

### Integration
- [ ] Update `storage/__init__.py` — register all new backends
- [ ] Update `storage/factory.py` — add factory mappings
- [ ] Update `pyproject.toml` — add optional dependency groups
- [ ] Update `configs/aurora.toml` — add configuration examples
- [ ] Verify all imports work correctly

---

## 阶段六（2026-06-01） / Phase 6: 完整实现 6 种 RAG 查询模式

### 已完成

- [x] **增强 Local 模式** — 双路径实体发现（向量搜索 + 图标签模糊搜索）+ BFS 深度-1 邻居扩展
- [x] **增强 Global 模式** — 关系中心检索 + 权重排序 + 端点实体 chunk 收集
- [x] **增强 Hybrid 模式** — `asyncio.gather` 并行执行 local+global，延迟减半
- [x] **增强 Mix 模式** — `asyncio.gather` 并行执行 hybrid+naive，KG 与向量结果合并去重
- [x] **完善 Bypass 模式** — 直接 LLM 透传 + 完整对话历史支持
- [x] **Naive 模式** — 纯向量相似度搜索（保持不变）
- [x] **导出 QueryMode** — 添加到 `retrieval/__init__.py` 的 `__all__`
- [x] **编写 42 个单元测试** — 覆盖所有模式、关键词提取、重排、去重、流式、对话历史、端到端流水线

### 变更文件

| 文件 | 说明 |
|------|------|
| `packages/aurora-ext/src/aurora_ext/rag/retrieval/query_engine.py` | 增强 6 种查询模式实现 |
| `packages/aurora-ext/src/aurora_ext/rag/retrieval/__init__.py` | 导出 QueryMode |
| `tests/ext/test_query_engine.py` | 42 个单元测试（全部通过） |

### 测试结果

```
tests/ext/test_query_engine.py  — 42 passed
tests/ext/                      — 132 passed (no regressions)
```

---

## 阶段七（2026-06-01） / Phase 7: Citation 引用溯源功能

### 已完成

- [x] **Citation 数据结构** — `Citation`（frozen dataclass）+ `QueryResultWithCitations`
- [x] **CitationTracker** — build / sort / deduplicate / filter_by_source / filter_by_min_score
- [x] **Chunk ID 生成** — 基于 SHA-256 的确定性 ID（`generate_chunk_id`）
- [x] **Distance→Score 转换** — `distance_to_score()` 支持 L2 距离归一化到 [0,1]
- [x] **ChunkManager 增强** — 注入 `chunk_id`, `file_path`, `start_pos`, `end_pos`, `page_number`
- [x] **PDFParser 页码追踪** — 生成 `page_boundaries` 元数据用于 chunk→page 映射
- [x] **ChromaVectorStore 元数据** — chunk_id 作为文档 ID，sanitize 复杂类型
- [x] **EmbeddingRetriever.retrieve_raw()** — 返回含 score / chunk_id 的 enriched dict
- [x] **KnowledgeService.query()** — 返回 citations + results（向后兼容）
- [x] **API 端点增强** — `/knowledge/{name}/query` 支持 `source_filter`, `min_score`
- [x] **QueryEngine.query_with_citations()** — KG 路径也能返回结构化 citations
- [x] **KnowledgeFactory** — 使用 parser routing 支持 PDF/DOCX/XLSX
- [x] **修复 ExportScope 导入错误** — `knowledge/__init__.py`
- [x] **41 个测试全部通过** — 覆盖 citation 提取、多文档引用、PDF 页码追踪

### 变更文件

| 文件 | 说明 |
|------|------|
| `citation_tracker.py` | Citation / QueryResultWithCitations / CitationTracker |
| `transformer/chunk.py` | ChunkManager 注入 citation 元数据 |
| `parser/pdf_parser.py` | page_boundaries 页码边界追踪 |
| `storage/chroma_store.py` | chunk_id 存储 + metadata sanitize |
| `retriever/embedding_retriever.py` | retrieve_raw() + score 计算 |
| `knowledge/factory.py` | parser routing 集成 |
| `retrieval/query_engine.py` | query_with_citations() + _build_citations() |
| `knowledge/api.py` | source_filter + min_score 参数 |
| `knowledge/service.py` | CitationTracker 集成 |
| `tests/test_citation_tracker.py` | 41 个单元测试 |

### 测试结果

```
tests/test_citation_tracker.py  — 41 passed (0 regressions)
```
