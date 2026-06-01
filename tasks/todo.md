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

#### P1-4: Reranking 增强
- [ ] 4.1 实现 AliyunReranker（DashScope gte-rerank-v2）
- [ ] 4.2 添加长文分块重排 + RerankOptions
- [ ] 4.3 实现分数聚合策略（max/mean/first）
- [ ] 4.4 实现指数退避重试
- [ ] 4.5 集成到 query_engine
- [ ] 4.6 配置 + 测试

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

#### P2-1: MinerU 解析引擎
- [ ] 1.1 安装 magic-pdf SDK
- [ ] 1.2 实现 MinerUParser
- [ ] 1.3 路由集成 + 并发控制
- [ ] 1.4 编写测试

#### P2-2: Docling 解析引擎
- [ ] 2.1 安装 docling
- [ ] 2.2 实现 DoclingParser
- [ ] 2.3 路由集成
- [ ] 2.4 编写测试

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
- [ ] 5.1 安装 ragas + datasets
- [ ] 5.2 实现 RAGQualityEvaluator
- [ ] 5.3 实现 OfflineRetrievalChecker
- [ ] 5.4 添加 API 端点

#### P2-6: Docker 部署方案
- [ ] 6.1 Dockerfile（标准版）
- [ ] 6.2 Dockerfile.lite（精简版）
- [ ] 6.3 docker-compose.yml（基础版）
- [ ] 6.4 docker-compose-full.yml（含 PG + Neo4j + Milvus）
- [ ] 6.5 部署文档

#### P2-7: 可观测性增强
- [ ] 7.1 增强健康检查端点（存储后端 + 管线 + LLM 角色状态）
- [ ] 7.2 管线追踪 API + 阶段计时
- [ ] 7.3 （可选）Langfuse 集成
