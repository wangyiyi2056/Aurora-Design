# LightRAG 知识库迁移计划

## 项目概述

将 Aurora 现有的简单知识库系统（基础向量检索 + 固定分块）全面改造为 LightRAG 级别的生产级 RAG 系统，核心目标是引入 **知识图谱 + 向量双检索引擎**，并完善文档处理管线。

---

## 现有系统 vs 目标系统对比

| 维度 | 现有 Aurora | 目标 (LightRAG) |
|------|------------|-----------------|
| 检索方式 | 纯向量相似度 | 向量 + 知识图谱双检索 (6种模式) |
| 文档解析 | 纯文本读取 | PDF/DOCX/PPTX/XLSX/MD 多格式 |
| 分块策略 | 仅固定大小 | 4种策略 (固定/递归字符/语义向量/段落语义) |
| 知识提取 | 无 | LLM 驱动的实体/关系自动抽取 |
| 重排序 | 无 | Cohere/Jina/vLLM Reranker |
| 文档状态 | 无 | 完整状态机 (pending→parsing→processing→done/failed) |
| 响应流式 | 仅Chat流式 | 查询也支持 NDJSON 流式 |
| 引用溯源 | 无 | 带 reference 的引用标注 |
| 缓存 | 无 | LLM 响应缓存 + 查询缓存 |
| 前端图谱 | 占位图 | 真实知识图谱可视化 + 交互编辑 |

---

## 迁移范围分类

### 核心功能 (必须迁移)

| # | 功能 | 说明 | 优先级 |
|---|------|------|--------|
| C1 | 知识图谱构建 | LLM 驱动的实体/关系自动抽取、图谱合并去重 | P0 |
| C2 | 双级检索引擎 | 6种查询模式 (local/global/hybrid/naive/mix/bypass) | P0 |
| C3 | 多格式文档解析 | PDF、DOCX、PPTX、XLSX、TXT、Markdown | P0 |
| C4 | 多分块策略 | 固定Token、递归字符、语义向量 (至少3种) | P0 |
| C5 | 文档生命周期管理 | 状态机 + 进度追踪 + 失败重试 | P0 |
| C6 | 流式查询 + 引用 | NDJSON 流式响应 + source reference | P1 |
| C7 | 重排序 (Rerank) | Cohere/Jina 重排序集成 | P1 |
| C8 | LLM 缓存 | 抽取/查询响应缓存 | P1 |
| C9 | 前端知识图谱可视化 | 真实图谱展示 + 实体/关系交互 | P1 |
| C10 | 增强文档管理 UI | 状态展示、批量上传、进度条、重试操作 | P1 |
| C11 | 查询界面重构 | 模式选择、参数配置、引用展示 | P1 |
| C12 | Chat 知识库集成 UI | 聊天时选择知识库、展示检索上下文 | P2 |

### 次要功能 (暂时不迁移)

| # | 功能 | 原因 |
|---|------|------|
| S1 | 多模态 VLM 分析 | 需要视觉模型，复杂度高 |
| S2 | Ollama 兼容 API | 非核心 RAG 功能 |
| S3 | RAGAS 评估框架 | 可后续添加 |
| S4 | Gunicorn 多 Worker | 当前 Uvicorn 单进程足够 |
| S5 | 外部解析服务 (MinerU/Docling) | 原生解析器优先 |
| S6 | 角色 LLM 路由 (4角色) | 单 LLM 足够启动 |
| S7 | 全部 15 种存储后端 | 先实现 2-3 种 (ChromaDB + NetworkX + PostgreSQL) |
| S8 | K8s Helm 部署 | 非功能需求 |
| S9 | Langfuse 可观测性 | 可后续添加 |
| S10 | 非对称 Embedding | 特殊场景需求 |

---

## 详细实施阶段

### Phase 1: 存储层抽象 (后端)

**目标**: 替换 ChromaDB 单一存储，引入四层存储抽象

#### 1.1 定义存储抽象基类
- **文件**: `packages/aurora-core/storage/base.py`
- 定义 4 个抽象基类:
  - `BaseKVStorage` — 键值存储 (文档、缓存)
  - `BaseVectorStorage` — 向量存储 (嵌入)
  - `BaseGraphStorage` — 图存储 (知识图谱)
  - `BaseDocStatusStorage` — 文档状态追踪
- 定义命名空间常量 (full_docs, text_chunks, entities, relationships, etc.)

#### 1.2 实现默认存储后端
- `JsonKVStorage` — JSON 文件键值存储 (轻量开发用)
- `ChromaVectorStorage` — 改造现有 ChromaDB 封装，适配新接口
- `NetworkXGraphStorage` — 基于 NetworkX 的本地图存储
- `JsonDocStatusStorage` — JSON 文件状态存储

#### 1.3 实现生产存储后端 (可选)
- `PostgresStorage` — PostgreSQL 统一存储 (KV + Vector + Graph + DocStatus)
- 使用 `pgvector` 扩展支持向量检索

#### 1.4 数据迁移策略
- 现有 ChromaDB 数据标记为 legacy
- 新知识库使用新存储架构
- 提供迁移脚本 (可选)

**依赖**: 无
**预估工作量**: 3-4 天

---

### Phase 2: 文档解析管线 (后端)

**目标**: 支持多格式文档解析 + 多策略分块

#### 2.1 文档解析器
- **文件**: `packages/aurora-ext/rag/parser/`
- 实现统一解析接口 `DocumentParser`:
  - `TextParser` — .txt, .md 纯文本
  - `PDFParser` — .pdf (基于 pypdf)
  - `DOCXParser` — .docx (基于 python-docx，段落/表格/图片提取)
  - `PPTXParser` — .pptx (基于 python-pptx)
  - `XLSXParser` — .xlsx (基于 openpyxl)
- 解析路由: 根据文件后缀自动选择解析器
- 统一输出: 纯文本 + 结构化元数据

#### 2.2 分块策略
- **文件**: `packages/aurora-ext/rag/chunker/`
- 实现分块策略注册表:
  - `FixedTokenChunker` — 固定 Token 窗口 (改造现有 ChunkManager)
  - `RecursiveCharacterChunker` — 递归字符分割 (基于 langchain-text-splitters)
  - `SemanticVectorChunker` — 语义向量分割 (基于 langchain-experimental)
- 每个策略支持 `chunk_size` + `chunk_overlap` 参数

#### 2.3 文档状态管理
- **文件**: `packages/aurora-ext/rag/pipeline/status.py`
- 实现文档处理状态机:
  ```
  PENDING → PARSING → PREPROCESSED → PROCESSING → PROCESSED
     │          │            │             │
     └──────────┴────────────┴─────────────┴──→ FAILED
  ```
- 数据库表: `document_processing_status`
  - `doc_id`, `file_name`, `status`, `error_message`, `progress`, `created_at`, `updated_at`

#### 2.4 新增 Python 依赖
```
pypdf>=4.0
python-docx>=1.0
python-pptx>=0.6.23
langchain-text-splitters>=0.3
langchain-experimental>=0.3 (可选, 语义分块)
```

**依赖**: Phase 1
**预估工作量**: 3-4 天

---

### Phase 3: 知识图谱构建引擎 (后端) — 核心

**目标**: LLM 驱动的实体/关系自动抽取 + 图谱构建

#### 3.1 实体/关系抽取
- **文件**: `packages/aurora-ext/rag/extraction/`
- `EntityExtractor` — 基于 LLM 的实体抽取:
  - 输入: 文本 chunk
  - 输出: `ExtractedEntity(entity_name, entity_type, entity_description)`
  - 支持可配置的实体类型列表 (Person, Organization, Location, Concept, etc.)
  - 支持多轮 gleaning (多次提取以捕获遗漏实体)
- `RelationshipExtractor` — 基于 LLM 的关系抽取:
  - 输出: `ExtractedRelationship(source, target, keywords, description)`
- 使用 Aurora 现有的 LLM 抽象层 (`BaseLLM`)

#### 3.2 Prompt 模板
- **文件**: `packages/aurora-ext/rag/extraction/prompts.py`
- 移植 LightRAG 的抽取 prompt (系统 prompt + 用户 prompt)
- 支持自定义实体类型配置 (YAML)
- 支持分隔符模式 + JSON 模式两种输出格式

#### 3.3 图谱合并与去重
- **文件**: `packages/aurora-ext/rag/extraction/merger.py`
- `merge_entities()` — 跨 chunk 实体合并:
  - 同名实体合并描述 (map-reduce 摘要当描述过长时)
  - 权重累加
  - source_id 追踪
- `merge_relationships()` — 关系合并:
  - 同 source-target 关系合并描述
  - 关键词合并

#### 3.4 管线编排
- **文件**: `packages/aurora-ext/rag/pipeline/ingestion.py`
- `IngestionPipeline` — 完整的文档入库管线:
  ```
  文件上传 → 解析 → 分块 → 实体抽取 → 关系抽取
     → 图谱合并 → 向量嵌入 → 存储写入
  ```
- 异步处理，支持并发控制 (`max_parallel`)
- 支持管线取消
- 支持失败重试

**依赖**: Phase 1, Phase 2
**预估工作量**: 5-7 天

---

### Phase 4: 双级检索引擎 (后端) — 核心

**目标**: 实现 6 种查询模式，结合知识图谱和向量检索

#### 4.1 关键词提取
- **文件**: `packages/aurora-ext/rag/retrieval/keyword_extractor.py`
- LLM 驱动的查询关键词提取:
  - 高层关键词 (hl_keywords) — 用于实体/关系检索
  - 底层关键词 (ll_keywords) — 用于 chunk 检索
- 支持直接提供关键词跳过 LLM 提取

#### 4.2 检索模式实现
- **文件**: `packages/aurora-ext/rag/retrieval/`
- `LocalRetriever` — 实体中心检索:
  - 查询 → 匹配实体 → 关联实体/关系/chunks
- `GlobalRetriever` — 关系中心检索:
  - 查询 → 匹配关系 → 关联实体/chunks
- `HybridRetriever` — 合并 local + global
- `NaiveRetriever` — 纯向量相似度 (改造现有 EmbeddingRetriever)
- `MixRetriever` — KG 检索 + 向量检索融合 (推荐模式)
- `BypassRetriever` — 直接发送给 LLM，无检索

#### 4.3 Token 预算分配
- **文件**: `packages/aurora-ext/rag/retrieval/token_budget.py`
- 可配置的 token 预算:
  - `max_entity_tokens` (默认 6000)
  - `max_relation_tokens` (默认 8000)
  - `max_total_tokens` (默认 30000)
- 在预算内优先选择高权重/高相关性的内容

#### 4.4 重排序集成
- **文件**: `packages/aurora-ext/rag/retrieval/reranker.py`
- `RerankerBase` 抽象接口
- 实现:
  - `CohereReranker` — Cohere rerank-v3.5
  - `JinaReranker` — Jina AI reranker
- 可选启用，支持 `min_rerank_score` 阈值过滤

#### 4.5 上下文构建
- **文件**: `packages/aurora-ext/rag/retrieval/context_builder.py`
- 将检索结果组装为 LLM prompt:
  - 实体列表 (名称、类型、描述)
  - 关系列表 (源、目标、描述)
  - 相关 chunks (来源标注)
  - 对话历史
  - 用户自定义 prompt

#### 4.6 查询服务
- **文件**: `packages/aurora-serve/services/knowledge_query_service.py`
- 统一查询接口，支持:
  - 流式响应 (NDJSON / SSE)
  - 非流式完整响应
  - 引用溯源 (references: file_path, chunk_content)
  - `only_need_context` 模式 (仅返回检索上下文不生成)

**依赖**: Phase 3
**预估工作量**: 5-7 天

---

### Phase 5: API 层重构 (后端)

**目标**: 重新设计知识库 API，支持全部核心功能

#### 5.1 知识库管理 API (改造现有)
```
POST   /api/v1/knowledge                          — 创建知识库
GET    /api/v1/knowledge                          — 列表所有知识库
GET    /api/v1/knowledge/{id}                     — 知识库详情 (含统计)
DELETE /api/v1/knowledge/{id}                     — 删除知识库
PUT    /api/v1/knowledge/{id}                     — 更新配置
```

#### 5.2 文档管理 API (新增/改造)
```
POST   /api/v1/knowledge/{id}/documents/upload    — 上传文档 (multipart)
POST   /api/v1/knowledge/{id}/documents/text      — 插入纯文本
GET    /api/v1/knowledge/{id}/documents           — 文档列表 (分页+状态过滤)
GET    /api/v1/knowledge/{id}/documents/status    — 处理状态统计
DELETE /api/v1/knowledge/{id}/documents/{doc_id}  — 删除文档
POST   /api/v1/knowledge/{id}/documents/retry     — 重试失败文档
GET    /api/v1/knowledge/{id}/pipeline/status     — 管线状态
POST   /api/v1/knowledge/{id}/pipeline/cancel     — 取消管线
```

#### 5.3 查询 API (改造)
```
POST   /api/v1/knowledge/{id}/query              — RAG 查询 (非流式)
POST   /api/v1/knowledge/{id}/query/stream       — RAG 查询 (流式 SSE)
```
请求体:
```json
{
  "query": "问题内容",
  "mode": "mix",              // local|global|hybrid|naive|mix|bypass
  "top_k": 40,
  "chunk_top_k": 20,
  "enable_rerank": false,
  "include_references": true,
  "conversation_history": []
}
```

#### 5.4 知识图谱 API (新增)
```
GET    /api/v1/knowledge/{id}/graph               — 获取图谱数据 (节点+边)
GET    /api/v1/knowledge/{id}/graph/labels        — 获取所有标签
GET    /api/v1/knowledge/{id}/graph/search        — 搜索实体
POST   /api/v1/knowledge/{id}/graph/entity        — 创建/编辑实体
POST   /api/v1/knowledge/{id}/graph/relation      — 创建/编辑关系
DELETE /api/v1/knowledge/{id}/graph/entity/{eid}  — 删除实体
DELETE /api/v1/knowledge/{id}/graph/relation/{rid}— 删除关系
POST   /api/v1/knowledge/{id}/graph/merge         — 合并重复实体
```

#### 5.5 系统 API
```
POST   /api/v1/knowledge/{id}/cache/clear         — 清除缓存
```

**依赖**: Phase 4
**预估工作量**: 3-4 天

---

### Phase 6: 前端重构

**目标**: 全新的知识库管理界面，支持图谱可视化和高级查询

#### 6.1 知识库列表页 (改造)
- **文件**: `frontend/src/features/construct/knowledge/`
- 知识库卡片: 名称、文档数、chunk 数、实体数、关系数、创建时间
- 创建知识库对话框: 名称、分块策略选择、chunk 参数配置
- 删除确认

#### 6.2 知识库详情页 (新增)
- 4 个 Tab 页:
  - **文档管理**: 文档列表、状态标签 (处理中/完成/失败)、上传按钮、删除/重试操作、进度条
  - **查询测试**: 查询输入、模式选择下拉框、参数配置面板、流式响应展示、引用来源展示
  - **知识图谱**: 力导向图可视化、实体/关系搜索、节点点击展开详情、实体/关系编辑
  - **设置**: 知识库配置、分块策略修改、清除缓存

#### 6.3 知识图谱可视化 (新增)
- **文件**: `frontend/src/features/construct/knowledge/components/GraphViewer/`
- 基于 ECharts 或 D3.js 的力导向图:
  - 节点 = 实体 (大小按权重，颜色按类型)
  - 边 = 关系 (粗细按权重，标签显示关键词)
  - 交互: 缩放、拖拽、点击查看详情、搜索高亮
  - 性能: 大量节点时分层加载 / 聚类

#### 6.4 Chat 知识库集成 (改造)
- **文件**: `frontend/src/features/chat/`
- 聊天输入区域增加知识库选择器 (多选)
- 检索上下文展示 (折叠面板显示检索到的实体/关系/chunks)
- 引用标注 (答案中的引用可点击跳转到源文档)

#### 6.5 i18n 更新
- 新增知识图谱、查询模式、文档状态等翻译键
- 中英文双语支持

**依赖**: Phase 5
**预估工作量**: 5-7 天

---

### Phase 7: 集成测试 + 联调

#### 7.1 后端测试
- 存储层单元测试 (各存储后端)
- 文档解析器测试 (各格式)
- 分块策略测试
- 实体/关系抽取测试 (mock LLM)
- 检索模式测试
- API 集成测试

#### 7.2 前端测试
- 知识库 CRUD E2E 测试
- 文档上传 + 状态轮询测试
- 查询流式响应测试
- 图谱可视化渲染测试

#### 7.3 端到端验证
- 完整流程: 上传 PDF → 解析 → 分块 → 抽取 → 构建图谱 → 查询 → 返回带引用的答案
- 多种查询模式对比测试

**预估工作量**: 3-4 天

---

## 实施路线图

```
Week 1-2:  Phase 1 (存储层) + Phase 2 (解析管线)    — 并行开发
Week 3-4:  Phase 3 (知识图谱引擎)                   — 核心攻坚
Week 5-6:  Phase 4 (检索引擎)                       — 核心攻坚
Week 7:    Phase 5 (API 层)                         — 接口对接
Week 8-9:  Phase 6 (前端)                           — UI 重构
Week 10:   Phase 7 (测试联调)                        — 质量保障
```

**总预估**: 8-10 周

---

## 技术决策

### 1. 存储策略
- **开发/轻量部署**: JSON (KV) + ChromaDB (Vector) + NetworkX (Graph)
- **生产部署**: PostgreSQL + pgvector 统一存储 (推荐)
- 保留 ChromaDB 兼容性，因为现有系统在用

### 2. LLM 使用
- 复用 Aurora 现有的 `BaseLLM` 抽象层
- 实体抽取默认使用配置的 main LLM
- 后续可扩展为不同任务使用不同 LLM (角色路由)

### 3. 前端图谱库
- **推荐**: ECharts (已有依赖，支持力导向图)
- **备选**: D3.js (更灵活但学习成本高)
- **备选**: react-force-graph (专门做力导向图)

### 4. 与现有 Chat 系统集成
- 知识查询可作为 Chat 的 context 注入 (保留现有机制)
- 增加知识库选择器 UI
- 查询结果带引用，在 Chat 中可展示来源

### 5. 迁移策略
- 非破坏性迁移: 新知识库使用新系统，旧知识库保持兼容
- 提供旧→新迁移工具 (可选)
- API 保持向后兼容一段时间

---

## 新增依赖清单

### 后端 Python
```
pypdf>=4.0                    # PDF 解析
python-docx>=1.0              # DOCX 解析
python-pptx>=0.6.23           # PPTX 解析
networkx>=3.0                 # 图存储 (默认)
langchain-text-splitters>=0.3 # 分块策略
json-repair>=0.1              # LLM 输出 JSON 修复
tiktoken>=0.5                 # Token 计数
tenacity>=8.0                 # 重试逻辑 (已有?)
```

### 前端 TypeScript
```
echarts-force-graph (或使用现有 echarts)  # 知识图谱可视化
```

---

## 风险与缓解

| 风险 | 级别 | 缓解措施 |
|------|------|---------|
| LLM 抽取质量不稳定 | 高 | 支持多轮 gleaning + 人工编辑图谱 |
| 大文档处理耗时长 | 高 | 异步管线 + 进度追踪 + 取消支持 |
| 知识图谱规模爆炸 (前端渲染) | 中 | 分页加载 + 聚类 + 筛选 |
| 存储一致性 (多存储后端) | 中 | 事务化写入 + 状态机保证 |
| 旧数据迁移 | 低 | 非破坏性迁移，新旧共存 |
| 嵌入模型不一致 | 中 | 统一使用 OpenAI embedding (或可配置) |

---

## 目录结构变更预览

```
packages/
├── aurora-core/
│   └── storage/                      # 新增
│       ├── __init__.py
│       ├── base.py                   # 4个存储抽象基类
│       ├── namespace.py              # 命名空间常量
│       └── factory.py                # 存储工厂
│
├── aurora-ext/
│   └── rag/
│       ├── parser/                   # 新增
│       │   ├── __init__.py
│       │   ├── base.py               # 解析器接口
│       │   ├── text_parser.py
│       │   ├── pdf_parser.py
│       │   ├── docx_parser.py
│       │   ├── pptx_parser.py
│       │   ├── xlsx_parser.py
│       │   └── routing.py            # 解析路由
│       │
│       ├── chunker/                  # 新增 (重构现有)
│       │   ├── __init__.py
│       │   ├── base.py               # 分块器接口
│       │   ├── fixed_token.py
│       │   ├── recursive_char.py
│       │   └── semantic_vector.py
│       │
│       ├── extraction/               # 新增 (核心)
│       │   ├── __init__.py
│       │   ├── entity_extractor.py
│       │   ├── relationship_extractor.py
│       │   ├── merger.py
│       │   ├── prompts.py
│       │   └── types.py
│       │
│       ├── retrieval/                # 新增 (核心)
│       │   ├── __init__.py
│       │   ├── local_retriever.py
│       │   ├── global_retriever.py
│       │   ├── hybrid_retriever.py
│       │   ├── naive_retriever.py
│       │   ├── mix_retriever.py
│       │   ├── keyword_extractor.py
│       │   ├── reranker.py
│       │   ├── context_builder.py
│       │   └── token_budget.py
│       │
│       ├── pipeline/                 # 新增
│       │   ├── __init__.py
│       │   ├── ingestion.py
│       │   └── status.py
│       │
│       └── storage/                  # 改造
│           ├── json_kv.py            # 新增
│           ├── chroma_vector.py      # 改造
│           ├── networkx_graph.py     # 新增
│           ├── json_doc_status.py    # 新增
│           └── postgres_all.py       # 新增 (可选)
│
├── aurora-serve/
│   ├── routers/
│   │   ├── knowledge.py              # 重构
│   │   ├── knowledge_graph.py        # 新增
│   │   └── knowledge_query.py        # 新增
│   ├── services/
│   │   ├── knowledge_service.py      # 重构
│   │   ├── knowledge_query_service.py# 新增
│   │   └── ingestion_service.py      # 新增
│   └── models/
│       ├── knowledge.py              # 重构
│       └── graph.py                  # 新增
│
frontend/src/features/construct/knowledge/
├── pages/
│   ├── KnowledgeListPage.tsx         # 改造
│   └── KnowledgeDetailPage.tsx       # 新增
├── components/
│   ├── DocumentManager/              # 新增
│   │   ├── DocumentList.tsx
│   │   ├── DocumentUpload.tsx
│   │   ├── StatusBadge.tsx
│   │   └── ProgressBar.tsx
│   ├── QueryPanel/                   # 新增
│   │   ├── QueryInput.tsx
│   │   ├── ModeSelector.tsx
│   │   ├── ResponseViewer.tsx
│   │   └── ReferenceList.tsx
│   ├── GraphViewer/                  # 新增
│   │   ├── GraphCanvas.tsx
│   │   ├── NodeDetail.tsx
│   │   ├── EdgeDetail.tsx
│   │   └── GraphSearch.tsx
│   └── KnowledgeSettings.tsx         # 新增
├── hooks/
│   ├── useKnowledgeGraph.ts          # 新增
│   ├── useDocumentStatus.ts          # 新增
│   └── useKnowledgeQuery.ts          # 新增
└── services/
    └── knowledge.ts                  # 重构
```

---

## 确认事项

请确认以下内容后开始实施:

1. **迁移范围**: 核心功能列表 (C1-C12) 是否完整？是否有遗漏？
2. **次要功能**: 标记为 "暂不迁移" 的功能 (S1-S10) 是否有需要提前做的？
3. **存储策略**: 开发用 JSON+ChromaDB+NetworkX，生产用 PostgreSQL，是否可接受？
4. **前端图谱库**: 使用 ECharts (已有依赖) 还是其他方案？
5. **时间预期**: 8-10 周的开发周期是否合理？
6. **实施顺序**: 从后端存储层开始，逐步推进到前端，是否认同？
