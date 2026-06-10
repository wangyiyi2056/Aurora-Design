# LightRAG 迁移补充计划

> 本文档是 `lightrag-migration-plan.md` 的补充，逐项对比 LightRAG 全部功能，找出遗漏和不够详细的部分。
>
> **迁移原则**: 功能原样迁移，不自行重构，不擅自增加细节功能。前端 UI 按本项目现有技术栈调整，功能全部保留。

---

## 一、功能清单变更

### 从「次要」提升到「核心」

| 原编号 | 功能 | 调整原因 |
|--------|------|---------|
| S2 → **C13** | **Ollama 兼容 API** | 本地文件上传时需要 Ollama 做 embedding，是基础设施 |

### 新增遗漏功能 (LightRAG 有，原计划未覆盖)

| 新编号 | 功能 | 说明 | 优先级 |
|--------|------|------|--------|
| C14 | 查询数据端点 (query/data) | 纯数据检索，不经过 LLM 生成，返回实体/关系/chunks 结构化数据 | P1 |
| C15 | 文档目录扫描 | 扫描 input 目录自动发现新文件并入库 | P1 |
| C16 | 文本插入 (单条/批量) | 直接插入纯文本，不需要上传文件 | P1 |
| C17 | 内容哈希去重 | 基于内容 hash 检测重复文档 | P1 |
| C18 | Track ID 追踪系统 | 每次操作生成 track_id，用于追踪处理进度 | P1 |
| C19 | 查询模式前缀系统 | Ollama API 中通过 `/local`, `/global` 等前缀切换模式 | P1 |
| C20 | 连通子图检索 | 从指定标签出发，获取 max_depth 层连通子图 | P1 |
| C21 | 标签管理 (热门/搜索) | 标签列表、按度数排序的热门标签、模糊搜索 | P1 |
| C22 | 实体存在性检查 | 检查实体是否已存在 | P2 |
| C23 | 工作空间隔离 | 多租户数据隔离，每个 workspace 独立存储 | P2 |
| C24 | OpenWebUI 兼容检测 | 检测 OpenWebUI 的标题/关键词生成请求，直接转发 LLM | P2 |
| C25 | 加密 PDF 解密 | 支持密码保护的 PDF 文件解析 | P2 |
| C26 | 文件名解析提示 | 文件名中包含解析器/分块策略提示 (如 `doc.[native].docx`) | P2 |
| C27 | 非对称 Embedding | 查询/文档使用不同前缀的 embedding | P2 |
| C28 | COT 思维链解析 | 前端解析 `<think>` 标签，展示推理过程 | P2 |
| C29 | LaTeX 公式渲染 | 前端支持行内/块级 LaTeX 公式 | P2 |

### 仍保留为「暂不迁移」

| 编号 | 功能 | 原因 |
|------|------|------|
| S1 | 多模态 VLM 分析 | 需要视觉模型，复杂度高 |
| S3 | RAGAS 评估框架 | 可后续添加 |
| S4 | Gunicorn 多 Worker | 当前 Uvicorn 单进程足够 |
| S5 | 外部解析服务 (MinerU/Docling) | 原生解析器优先 |
| S8 | K8s Helm 部署 | 非功能需求 |
| S9 | Langfuse 可观测性 | 可后续添加 |

### 调整说明

| 原编号 | 原状态 | 调整 |
|--------|--------|------|
| S2 | Ollama 兼容 API (次要) | → **C13** (核心)，embedding 必需 |
| S6 | 角色 LLM 路由 (次要) | → **保留次要**，但 Ollama API 中需要基础的角色概念 |
| S7 | 全部 15 种存储后端 (次要) | → **保留次要**，先实现 3 种默认后端 |
| S10 | 非对称 Embedding (次要) | → **C27** (核心)，部分 embedding 模型需要 |

---

## 二、遗漏功能详细规格

### C13: Ollama 兼容 API (从 S2 提升)

**来源**: `lightrag/api/routers/ollama_api.py` (738行)

#### 端点清单 (原样迁移)

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/version` | 返回 Ollama 版本号 (硬编码 `0.9.3`) |
| `GET` | `/api/tags` | 返回可用模型列表 (模拟单个 LightRAG 模型) |
| `GET` | `/api/ps` | 返回运行中模型列表 |
| `POST` | `/api/generate` | 文本生成 — 直通底层 LLM，**不走 RAG** |
| `POST` | `/api/chat` | 聊天 — 根据查询前缀路由到 RAG 或直通 LLM |

#### 请求/响应格式

**OllamaChatRequest**:
```json
{
  "model": "lightrag",
  "messages": [{"role": "user", "content": "..."}],
  "stream": true,
  "options": {},
  "system": "可选系统提示"
}
```

**OllamaGenerateRequest**:
```json
{
  "model": "lightrag",
  "prompt": "文本内容",
  "system": "可选系统提示",
  "stream": false,
  "options": {}
}
```

- 支持 `application/json` 和 `application/octet-stream` 两种 Content-Type
- 流式使用 NDJSON (`application/x-ndjson`)，响应头 `X-Accel-Buffering: no`

#### 查询模式前缀系统 (C19 合并实现)

在 `/api/chat` 中解析消息内容的前缀来决定 RAG 模式:

| 前缀 | 对应模式 | 说明 |
|------|---------|------|
| `/local <query>` | local | 实体中心检索 |
| `/global <query>` | global | 关系中心检索 |
| `/naive <query>` | naive | 纯向量检索 |
| `/hybrid <query>` | hybrid | 混合检索 |
| `/mix <query>` | mix | KG + 向量融合 (推荐) |
| `/bypass <query>` | bypass | 直通 LLM，跳过 RAG |
| `/context <query>` | mix + context-only | 仅返回检索上下文 |
| `/localcontext <query>` | local + context-only | |
| `/globalcontext <query>` | global + context-only | |
| `/hybridcontext <query>` | hybrid + context-only | |
| `/naivecontext <query>` | naive + context-only | |
| `/mixcontext <query>` | mix + context-only | |
| `/local[自定义prompt] query` | local + user_prompt | 方括号提取自定义 prompt |

#### OpenWebUI 检测 (C24)

检测 `\n<chat_history>\nUSER:` 模式，识别 OpenWebUI 的标题/关键词生成请求，直接转发给底层 LLM，不走 RAG。

#### 模拟模型配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `OLLAMA_EMULATING_MODEL_NAME` | `lightrag` | 模拟模型名称 |
| `OLLAMA_EMULATING_MODEL_TAG` | `latest` | 模拟模型标签 |

#### Token 计数

使用 TiktokenTokenizer 返回 `prompt_eval_count` 和 `eval_count` 指标。

---

### C14: 查询数据端点 (query/data)

**来源**: `lightrag/api/routers/query_routes.py` — `query_data()` 函数

#### 端点

```
POST /api/v1/knowledge/{id}/query/data
```

#### 说明

纯数据检索，不经过 LLM 生成。返回结构化的实体、关系、chunks 数据。用于前端知识图谱交互、数据分析等场景。

#### 请求体

与标准 query 相同，但忽略 LLM 生成相关参数。

#### 响应格式

```json
{
  "status": "success",
  "message": "",
  "data": {
    "entities": [
      {
        "entity_name": "...",
        "entity_type": "...",
        "description": "...",
        "source_id": "...",
        "file_path": "...",
        "reference_id": "1"
      }
    ],
    "relationships": [
      {
        "src_id": "...",
        "tgt_id": "...",
        "description": "...",
        "keywords": "...",
        "weight": 1.0,
        "source_id": "...",
        "file_path": "...",
        "reference_id": "2"
      }
    ],
    "chunks": [
      {
        "content": "...",
        "file_path": "...",
        "chunk_id": "...",
        "reference_id": "3"
      }
    ],
    "references": [
      {"reference_id": "1", "file_path": "/docs/example.pdf"}
    ]
  },
  "metadata": {
    "query_mode": "mix",
    "keywords": {
      "high_level": ["..."],
      "low_level": ["..."]
    },
    "processing_info": {
      "total_entities_found": 15,
      "total_relations_found": 20,
      "entities_after_truncation": 10,
      "relations_after_truncation": 12,
      "final_chunks_count": 8
    }
  }
}
```

---

### C15: 文档目录扫描

**来源**: `lightrag/api/routers/document_routes.py` — `scan()` 函数

#### 端点

```
POST /api/v1/knowledge/{id}/documents/scan
```

#### 说明

扫描预配置的 input 目录，发现新文件后自动入库处理。

#### 响应

```json
{
  "status": "scanning_started | scanning_skipped_pipeline_busy",
  "message": "...",
  "track_id": "uuid"
}
```

#### 行为

- 管线繁忙时返回 `scanning_skipped_pipeline_busy`，不阻塞
- 扫描阶段互斥（分类期间不接受新扫描），处理阶段允许并发上传
- 支持的 46 种文件扩展名 (原样迁移):
  `.txt`, `.md`, `.mdx`, `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.rtf`, `.odt`, `.tex`, `.epub`, `.html`, `.htm`, `.csv`, `.json`, `.xml`, `.yaml`, `.yml`, `.log`, `.conf`, `.ini`, `.properties`, `.sql`, `.bat`, `.sh`, `.c`, `.h`, `.cpp`, `.hpp`, `.py`, `.java`, `.js`, `.ts`, `.swift`, `.go`, `.rb`, `.php`, `.css`, `.scss`, `.less`

---

### C16: 文本插入 (单条/批量)

**来源**: `lightrag/api/routers/document_routes.py` — `insert_text()`, `insert_texts()`

#### 端点

```
POST /api/v1/knowledge/{id}/documents/text    — 单条文本
POST /api/v1/knowledge/{id}/documents/texts   — 批量文本
```

#### 请求体

**单条**:
```json
{
  "text": "文本内容 (最少1字符，去除首尾空白)",
  "file_source": "可选来源标识"
}
```

**批量**:
```json
{
  "texts": ["文本1", "文本2"],
  "file_sources": ["来源1", "来源2"]
}
```

#### 响应

```json
{
  "status": "success | partial_success | failure",
  "message": "...",
  "track_id": "uuid"
}
```

---

### C17: 内容哈希去重

**来源**: `lightrag/utils.py` — `compute_mdhash_id()`

#### 说明

- 文档入库时计算内容 MD5 哈希
- 同步检测: 文件名重复 → 返回 HTTP 409
- 异步检测: 内容哈希重复 → 标记为 `is_duplicate`，附带 `original_doc_id` 和 `original_track_id`
- 在文档元数据中记录去重信息

---

### C18: Track ID 追踪系统

**来源**: `lightrag/utils.py` — `generate_track_id()`

#### 说明

- 每次操作 (上传、扫描、文本插入、重试) 生成唯一 track_id
- 端点:
  ```
  GET /api/v1/knowledge/{id}/documents/track/{track_id}
  ```
- 返回该 track_id 关联的所有文档处理状态
- Pipeline 状态中也包含当前 track_id

---

### C20: 连通子图检索

**来源**: `lightrag/api/routers/graph_routes.py` — `get_graphs()`

#### 端点

```
GET /api/v1/knowledge/{id}/graph/subgraph?label=xxx&max_depth=3&max_nodes=1000
```

#### 参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `label` | str | (必填) | 起始标签/实体名 |
| `max_depth` | int | 3 | 最大遍历深度 |
| `max_nodes` | int | 1000 | 最大返回节点数 |

#### 响应

返回 `KnowledgeGraph` 对象，包含 nodes 和 edges 列表。

---

### C21: 标签管理

**来源**: `lightrag/api/routers/graph_routes.py` — `get_label_list()`, `get_popular_labels()`, `search_labels()`

#### 端点

```
GET /api/v1/knowledge/{id}/graph/labels          — 所有标签
GET /api/v1/knowledge/{id}/graph/labels/popular   — 热门标签 (按节点度数排序)
GET /api/v1/knowledge/{id}/graph/labels/search    — 模糊搜索标签
```

#### 参数

| 端点 | 参数 | 默认 | 范围 |
|------|------|------|------|
| popular | `limit` | 300 | 1-1000 |
| search | `q` | (必填) | 搜索关键词 |
| search | `limit` | 50 | 1-100 |

---

### C22: 实体存在性检查

**来源**: `lightrag/api/routers/graph_routes.py` — `entity_exists()`

#### 端点

```
GET /api/v1/knowledge/{id}/graph/entity/exists?entity_name=xxx
```

---

### C23: 工作空间隔离

**来源**: LightRAG `WORKSPACE` 环境变量

#### 说明

- 通过 `WORKSPACE` 环境变量创建隔离的存储命名空间
- 仅允许字母数字和下划线
- 每个 workspace 拥有独立的 pipeline_status、doc_status 等
- Aurora 实现: 映射到现有的知识库 ID 机制，每个知识库即为一个 workspace

---

### C25: 加密 PDF 解密

**来源**: `lightrag/parser/` — PDF 解析器

#### 说明

- 支持密码保护的 PDF 文件
- 通过环境变量 `PDF_DECRYPT_PASSWORD` 配置密码
- 使用 `pycryptodome` 库

---

### C26: 文件名解析提示

**来源**: `lightrag/parser/routing.py`

#### 说明

文件名可以包含解析器和处理选项提示:

```
document.[native].docx        → 使用 native 解析器
report.[mineru].pdf           → 使用 mineru 解析器
data.[!F].csv                 → 跳过 KG 抽取 + 固定分块
image.[i].jpg                 → 启用 VLM 图像分析
```

选项代码:
| 代码 | 含义 |
|------|------|
| `native`/`mineru`/`docling` | 解析器引擎 |
| `i` | VLM 图像分析 |
| `t` | VLM 表格分析 |
| `e` | VLM 公式分析 |
| `!` | 跳过知识图谱抽取 |
| `F` | 固定长度分块 |
| `R` | 递归语义分块 |
| `V` | 向量语义分块 |
| `P` | 段落语义分块 |

---

### C27: 非对称 Embedding

**来源**: `lightrag/utils.py` — `EmbeddingFunc`

#### 说明

部分 embedding 模型 (BGE, E5, GTE) 对查询和文档使用不同前缀:

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `EMBEDDING_ASYMMETRIC` | `False` | 启用非对称 embedding |
| `EMBEDDING_QUERY_PREFIX` | None | 查询文本前缀 |
| `EMBEDDING_DOCUMENT_PREFIX` | None | 文档文本前缀 |

- Gemini/Jina/VoyageAI 使用 provider 特定的 task 参数
- Azure/OpenAI/Ollama 使用查询/文档前缀
- `NO_PREFIX` 哨兵值表示有意留空前缀

---

### C28: COT 思维链解析 (前端)

**来源**: LightRAG WebUI `RetrievalTesting.tsx`

#### 说明

- 检测 LLM 响应中的 `<think>...</think>` 标签
- 将思维链内容折叠展示，可展开查看
- 与最终答案分开展示

---

### C29: LaTeX 公式渲染 (前端)

**来源**: LightRAG WebUI `RetrievalTesting.tsx`

#### 说明

- 支持行内公式 `$...$` 和块级公式 `$$...$$`
- 公式完整性检测
- 使用 KaTeX 或 MathJax 渲染

---

## 三、原计划中不够详细的功能点

以下是原计划中已列出但规格不够详细的功能，需要补充 LightRAG 的完整规格。

### 3.1 Phase 4 查询参数 — 完整规格

原计划只列了 6 个参数，LightRAG 实际有 **18 个**查询参数:

| 参数 | 类型 | 默认值 | 说明 | 原计划 |
|------|------|--------|------|--------|
| `query` | str | (必填, ≥3字符) | 查询文本 | ✅ 有 |
| `mode` | enum | `"mix"` | 查询模式 | ✅ 有 |
| `only_need_context` | bool | None | 仅返回检索上下文 | ✅ 有 |
| `only_need_prompt` | bool | None | 仅返回构建的 prompt (不生成) | ❌ 遗漏 |
| `response_type` | str | None | 响应格式 (如 "Multiple Paragraphs", "Bullet Points") | ❌ 遗漏 |
| `top_k` | int | 40 | 顶层实体/关系数 | ✅ 有 |
| `chunk_top_k` | int | 20 | 向量检索 chunk 数 | ✅ 有 |
| `max_entity_tokens` | int | 6000 | 实体 token 预算 | ✅ 有 |
| `max_relation_tokens` | int | 8000 | 关系 token 预算 | ✅ 有 |
| `max_total_tokens` | int | 30000 | 总 token 预算 | ✅ 有 |
| `hl_keywords` | list[str] | [] | 高层关键词 (跳过 LLM 提取) | ❌ 遗漏 |
| `ll_keywords` | list[str] | [] | 底层关键词 (跳过 LLM 提取) | ❌ 遗漏 |
| `conversation_history` | list[dict] | None | 对话历史 `[{"role", "content"}]` | ✅ 有 |
| `user_prompt` | str | None | 自定义指令注入 prompt | ❌ 遗漏 |
| `enable_rerank` | bool | True | 启用重排序 | ✅ 有 |
| `include_references` | bool | True | 包含引用来源 | ✅ 有 |
| `include_chunk_content` | bool | False | 引用中包含原始 chunk 文本 | ❌ 遗漏 |
| `stream` | bool | True | 启用流式 (仅 /stream 端点) | ✅ 有 |

---

### 3.2 Phase 4 流式响应 — 完整规格

原计划只提了 "NDJSON 流式"，缺少具体格式:

```
Content-Type: application/x-ndjson
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**响应序列**:
```
第1行: {"references": [{"reference_id": "1", "file_path": "..."}]}    ← 引用信息 (首行)
第2行: {"response": "Machine learning is"}                            ← 流式文本块
第3行: {"response": " a subset of AI..."}                             ← 流式文本块
...
错误行: {"error": "message"}                                          ← 错误 (如有)
```

**非流式模式** (stream=false): 单行完整响应
```json
{"response": "完整回答...", "references": [...]}
```

---

### 3.3 Phase 4 检索模式 — 完整数据流

原计划列了 6 种模式名称但缺少内部流程:

**Local (实体中心)**:
```
查询 → LL关键词提取 → entities_vdb 向量搜索
  → 找关联边 (relationships)
  → 找关联 chunks (从 entities + relations)
  → 合并 + 排序 → 上下文构建
```

**Global (关系中心)**:
```
查询 → HL关键词提取 → relationships_vdb 向量搜索
  → 找关联实体 (entities)
  → 找关联 chunks (从 entities + relations)
  → 合并 + 排序 → 上下文构建
```

**Hybrid**: Local + Global 结果轮询合并

**Mix (推荐)**: KG 检索 (hybrid) + Naive 向量检索 → 合并去重

**Naive**: 查询 → chunk_vdb 向量搜索 → top chunks → 上下文构建 (无 KG)

**Bypass**: 查询 + 对话历史 → 直接发 LLM (无检索)

**Chunk 选取方法** (可配置):
| 方法 | 说明 |
|------|------|
| `VECTOR` (默认) | 从实体/关系的 source_id 中取 chunks，按向量相似度排序 |
| `WEIGHT` | 从实体/关系的 source_id 中取 chunks，按实体权重排序 |

环境变量: `KG_CHUNK_PICK_METHOD=VECTOR|WEIGHT`

---

### 3.4 Phase 3 实体抽取 — 完整规格

原计划列了基本流程，缺少关键参数:

| 参数/常量 | 默认值 | 说明 |
|----------|--------|------|
| `DEFAULT_MAX_GLEANING` | 1 | 多轮抽取次数 (0=不 gleaning) |
| `DEFAULT_ENTITY_NAME_MAX_LENGTH` | 256 | 实体名最大长度 |
| `DEFAULT_MAX_EXTRACTION_RECORDS` | 100 | 单次 LLM 响应最大记录数 |
| `DEFAULT_MAX_EXTRACTION_ENTITIES` | 40 | 单次 LLM 响应最大实体数 |
| `DEFAULT_MAX_EXTRACT_INPUT_TOKENS` | 20480 | 抽取输入最大 token |
| `GRAPH_FIELD_SEP` | `"<SEP>"` | 描述/source_id 字段分隔符 |
| `DEFAULT_MAX_SOURCE_IDS_PER_ENTITY` | 300 | 每实体最大 source_id 数 |
| `DEFAULT_MAX_SOURCE_IDS_PER_RELATION` | 300 | 每关系最大 source_id 数 |
| `SOURCE_IDS_LIMIT_METHOD` | `FIFO` | source_id 驱逐策略 (FIFO/KEEP) |
| `DEFAULT_MAX_FILE_PATHS` | 100 | 每实体最大文件路径数 |
| `DEFAULT_MAX_FILE_PATH_LENGTH` | 32768 | 文件路径最大长度 |

**抽取输出格式 — 分隔符模式**:
```
entity<|#|>实体名<|#|>实体类型<|#|>实体描述<|COMPLETE|>
```

**抽取输出格式 — JSON 模式** (`ENTITY_EXTRACTION_USE_JSON=true`):
```json
{
  "entities": [
    {"entity_name": "...", "entity_type": "...", "entity_description": "..."}
  ],
  "relationships": [
    {"source_entity": "...", "target_entity": "...", "relationship_keywords": "...", "relationship_description": "..."}
  ]
}
```

**默认 11 种实体类型**:
Person, Creature, Organization, Location, Event, Concept, Method, Content, Data, Artifact, NaturalObject (+ Other 兜底)

**描述合并阈值**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FORCE_LLM_SUMMARY_ON_MERGE` | 8 | 描述片段数达到此阈值时触发 LLM 摘要 |
| `SUMMARY_MAX_TOKENS` | 1200 | 摘要最大 token 数 |
| `SUMMARY_CONTEXT_SIZE` | 12000 | 发送给 LLM 做摘要的最大上下文 |
| `SUMMARY_LENGTH_RECOMMENDED` | 600 | 摘要推荐输出长度 |
| `SUMMARY_LANGUAGE` | `English` | 摘要输出语言 |

---

### 3.5 Phase 4 Reranker — 完整规格

原计划只列了 Cohere/Jina，缺少:

**支持的 Provider** (3种):

| Provider | 函数 | 默认模型 | 默认端点 |
|----------|------|---------|---------|
| Cohere | `cohere_rerank()` | `rerank-v3.5` | `https://api.cohere.com/v2/rerank` |
| Jina | `jina_rerank()` | `jina-reranker-v2-base-multilingual` | `https://api.jina.ai/v1/rerank` |
| Aliyun | `ali_rerank()` | `gte-rerank-v2` | `https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank` |

**功能细节**:
- 重试逻辑: 3 次，指数退避 (4s-60s)，基于 tenacity
- 文档分块: `chunk_documents_for_rerank()` 长文档分块 (默认 480 token, 32 overlap)
- 分数聚合: `aggregate_chunk_scores()` 策略: `max`, `mean`, `first`
- 响应格式: `standard` (Jina/Cohere) 和 `aliyun` (嵌套 input/parameters)
- Cohere `max_tokens_per_doc`: 默认 4096
- HTML 错误检测: 502/503/504 网关错误清洗

**配置**:
| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `RERANK_BINDING` | null | Provider: null/cohere/jina/aliyun |
| `RERANK_BINDING_HOST` | None | API 端点 |
| `RERANK_BINDING_API_KEY` | None | API 密钥 |
| `RERANK_MODEL` | None | 模型名 |
| `MIN_RERANK_SCORE` | 0.0 | 最低重排序分数阈值 |
| `MAX_ASYNC_RERANK` | 继承 MAX_ASYNC | 重排序并发 |
| `RERANK_TIMEOUT` | 30 | 请求超时 |

---

### 3.6 Phase 5 文档管理 API — 完整端点

原计划缺少部分端点:

| 方法 | 路径 | 说明 | 原计划 |
|------|------|------|--------|
| `POST` | `/documents/upload` | 上传文档 | ✅ |
| `POST` | `/documents/text` | 插入单条文本 | ✅ |
| `POST` | `/documents/texts` | 批量插入文本 | ✅ |
| `POST` | `/documents/scan` | 扫描 input 目录 | ❌ 遗漏 → C15 |
| `POST` | `/documents` (分页) | 分页文档列表 | ❌ 遗漏 |
| `GET` | `/documents` | 所有文档状态 (legacy) | ❌ 遗漏 |
| `GET` | `/documents/status_counts` | 状态统计 | ❌ 遗漏 |
| `GET` | `/documents/pipeline_status` | 管线状态 | ✅ |
| `GET` | `/documents/track_status/{track_id}` | 追踪 ID 查询 | ❌ 遗漏 → C18 |
| `DELETE` | `/documents` | 清除所有文档 | ❌ 遗漏 |
| `DELETE` | `/documents/delete_document` | 删除指定文档 | ✅ |
| `POST` | `/documents/clear_cache` | 清除 LLM 缓存 | ✅ |
| `POST` | `/documents/reprocess_failed` | 重试失败文档 | ✅ |
| `POST` | `/documents/cancel_pipeline` | 取消管线 | ✅ |
| `DELETE` | `/documents/delete_entity` | 删除实体 | ✅ (在图谱 API) |
| `DELETE` | `/documents/delete_relation` | 删除关系 | ✅ (在图谱 API) |

**分页请求参数**:

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `status_filter` | DocStatus | None | 单个状态过滤 |
| `status_filters` | List[DocStatus] | [] | 多状态过滤 |
| `page` | int | 1 | 页码 |
| `page_size` | int | 50 | 每页数量 (10-200) |
| `sort_field` | str | `created_at` | 排序字段: `created_at`/`updated_at`/`id`/`file_path` |
| `sort_direction` | str | `desc` | 排序方向: `asc`/`desc` |

**文档状态响应字段**:
```json
{
  "id": "uuid",
  "content_summary": "前100字符...",
  "content_length": 12345,
  "status": "PROCESSED",
  "created_at": "2026-01-01T00:00:00",
  "updated_at": "2026-01-01T00:01:00",
  "track_id": "uuid",
  "chunks_count": 15,
  "error_msg": null,
  "metadata": {},
  "file_path": "/uploads/doc.pdf"
}
```

**管线状态响应**:
```json
{
  "autoscanned": false,
  "busy": true,
  "job_name": "Processing documents",
  "job_start": "2026-01-01T00:00:00",
  "docs": {"total": 10, "processed": 5, "failed": 0, "pending": 5},
  "batchs": {"total": 3, "current": 2},
  "cur_batch": 2,
  "request_pending": false,
  "latest_message": "Processing batch 2/3",
  "history_messages": ["..."],
  "update_status": "processing"
}
```

**删除文档请求**:
```json
{
  "doc_ids": ["id1", "id2"],
  "delete_file": false,
  "delete_llm_cache": false
}
```

---

### 3.7 Phase 5 图谱 API — 完整端点

原计划缺少部分端点和参数:

| 方法 | 路径 | 说明 | 原计划 |
|------|------|------|--------|
| `GET` | `/graph/label/list` | 所有标签 | ✅ |
| `GET` | `/graph/label/popular` | 热门标签 (按度数) | ❌ 遗漏 → C21 |
| `GET` | `/graph/label/search` | 模糊搜索标签 | ❌ 遗漏 → C21 |
| `GET` | `/graphs` | 连通子图 | ❌ 遗漏 → C20 |
| `GET` | `/graph/entity/exists` | 实体存在性检查 | ❌ 遗漏 → C22 |
| `POST` | `/graph/entity/edit` | 编辑实体 | ✅ |
| `POST` | `/graph/relation/edit` | 编辑关系 | ✅ |
| `POST` | `/graph/entity/create` | 创建实体 (自动生成 embedding) | ✅ |
| `POST` | `/graph/relation/create` | 创建关系 (自动生成 embedding) | ✅ |
| `POST` | `/graph/entities/merge` | 合并重复实体 | ✅ |

**实体编辑请求** (含重命名/合并):
```json
{
  "entity_name": "原实体名",
  "updated_data": {"description": "...", "entity_type": "..."},
  "allow_rename": false,
  "allow_merge": false
}
```

**操作摘要响应**:
```json
{
  "merged": false,
  "merge_status": "not_attempted",
  "operation_status": "success",
  "renamed": false,
  "final_entity": "实体名",
  "target_entity": null
}
```

**实体合并请求**:
```json
{
  "entities_to_change": ["实体A", "实体B"],
  "entity_to_change_into": "目标实体"
}
```

**关系创建请求**:
```json
{
  "source_entity": "源实体",
  "target_entity": "目标实体",
  "relation_data": {
    "description": "...",
    "keywords": "...",
    "weight": 1.0,
    "source_id": "..."
  }
}
```

---

### 3.8 Phase 2 管线 — 完整规格

原计划缺少并发控制和队列细节:

**队列系统**:
| 队列 | 默认大小 | 并发 | 说明 |
|------|---------|------|------|
| `q_native` | 100 | 5 | 原生解析器队列 |
| `q_mineru` | 100 | 1 | MinerU 解析器队列 (暂不迁移) |
| `q_docling` | 100 | 1 | Docling 解析器队列 (暂不迁移) |
| `q_analyze` | 100 | 5 | VLM 分析队列 (暂不迁移) |
| `q_process` | 4 | MAX_PARALLEL_INSERT (2) | 抽取处理队列 |

**并发控制参数**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_ASYNC` | 4 | 最大并发异步操作 |
| `MAX_PARALLEL_INSERT` | 2 | 最大并行插入操作 |
| `EMBEDDING_FUNC_MAX_ASYNC` | 8 | Embedding 最大并发 |
| `EMBEDDING_BATCH_NUM` | 10 | Embedding 批大小 |
| `EMBEDDING_TIMEOUT` | 30 | Embedding 超时 |

**安全控制**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_UPLOAD_SIZE` | 104857600 (100MB) | 最大上传文件大小 |
| 路径遍历防护 | `sanitize_filename()` | 防止路径遍历攻击 |

**取消机制**:
- `/documents/cancel_pipeline` 设置取消标志
- 管线在关键处理点检查标志
- PROCESSING 中文档标记为 FAILED + "User cancelled"
- 已 PROCESSED 的文档保持不变

---

### 3.9 Phase 1 Embedding 配置 — 完整规格

原计划未详细列出 embedding 配置:

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `EMBEDDING_BINDING` | `ollama` | Provider: ollama/openai/azure_openai/bedrock/jina/gemini/voyageai |
| `EMBEDDING_BINDING_HOST` | 按 provider | API 端点 |
| `EMBEDDING_BINDING_API_KEY` | `""` | API 密钥 |
| `EMBEDDING_MODEL` | None (provider 默认) | Embedding 模型名 |
| `EMBEDDING_DIM` | None (provider 默认) | Embedding 维度 |
| `EMBEDDING_SEND_DIM` | `False` | 是否发送 dim 参数 |
| `EMBEDDING_FUNC_MAX_ASYNC` | 8 | 最大并发 |
| `EMBEDDING_BATCH_NUM` | 10 | 批大小 |
| `EMBEDDING_TIMEOUT` | 30 | 超时秒数 |
| `EMBEDDING_TOKEN_LIMIT` | None | 每条 embedding 的 token 限制 |
| `EMBEDDING_ASYMMETRIC` | `False` | 启用非对称 embedding → C27 |
| `EMBEDDING_QUERY_PREFIX` | None | 查询文本前缀 |
| `EMBEDDING_DOCUMENT_PREFIX` | None | 文档文本前缀 |

---

### 3.10 LLM 缓存系统 — 完整规格

原计划 C8 列了缓存但缺少细节:

**缓存范围**:
- 查询响应缓存: 按 `hash(query + params)` 索引
- 抽取响应缓存: 按 `hash(chunk_content + prompt)` 索引

**配置**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ENABLE_LLM_CACHE` | True | 启用查询缓存 |
| `ENABLE_LLM_CACHE_FOR_EXTRACT` | True | 启用抽取缓存 |

**缓存操作**:
- 自动: 查询/抽取时检查缓存，命中则跳过 LLM
- 手动清除: `POST /documents/clear_cache`
- 缓存键: `compute_args_hash()` 生成 MD5

---

### 3.11 Prompt 模板 — 完整清单

原计划只提了 "移植 prompt"，缺少完整清单:

| 模板名 | 用途 | 可定制 |
|--------|------|:------:|
| `DEFAULT_TUPLE_DELIMITER` | 字段分隔符 `<\|#\|>` | ✅ |
| `DEFAULT_COMPLETION_DELIMITER` | 结束标记 `<\|COMPLETE\|>` | ✅ |
| `default_entity_types_guidance` | 实体类型分类指南 (11 种) | ✅ |
| `entity_extraction_system_prompt` | 文本格式实体抽取系统 prompt | ✅ |
| `entity_extraction_user_prompt` | 文本格式抽取用户 prompt | ✅ |
| `entity_continue_extraction_user_prompt` | 继续/修复抽取 (文本格式) | ✅ |
| `entity_extraction_examples` | 3 个 few-shot 抽取示例 | ✅ |
| `entity_extraction_json_system_prompt` | JSON 格式抽取系统 prompt | ✅ |
| `entity_extraction_json_user_prompt` | JSON 格式抽取用户 prompt | ✅ |
| `entity_continue_extraction_json_user_prompt` | 继续/修复抽取 (JSON 格式) | ✅ |
| `entity_extraction_json_examples` | 3 个 JSON 格式 few-shot 示例 | ✅ |
| `summarize_entity_descriptions` | 多描述合并摘要 prompt | ✅ |
| `fail_response` | 无法回答时的默认消息 | ✅ |
| `rag_response` | 主 RAG 响应生成 prompt (含 KG) | ✅ |
| `naive_rag_response` | Naive 模式响应 prompt (仅 chunks) | ✅ |
| `kg_query_context` | KG 查询上下文模板 | ✅ |
| `naive_query_context` | Naive 查询上下文模板 | ✅ |
| `keywords_extraction` | 查询关键词提取 prompt | ✅ |
| `keywords_extraction_examples` | 3 个关键词提取 few-shot 示例 | ✅ |

**全部 prompt 原样移植**，不做修改。

---

### 3.12 前端 — 遗漏功能点

原计划的前端部分缺少以下 LightRAG WebUI 功能:

#### 3.12.1 文档管理器

| 功能 | 说明 | 原计划 |
|------|------|--------|
| 分页文档表格 | 可配置每页数量 | ✅ 有 |
| 状态过滤 | 单选/多选状态过滤 | ✅ 有 (未明确多选) |
| 排序 | 按 created_at/updated_at/id/file_path | ❌ 遗漏 |
| 拖拽上传 | 文件拖拽到上传区域 | ❌ 遗漏 |
| 管线状态对话框 | 实时监控管线 | ❌ 遗漏 |
| 状态计数 | 各状态聚合计数 | ❌ 遗漏 |
| 重试失败文档 | 一键重试 | ✅ 有 |
| 自动刷新 | 活跃状态文档轮询 | ❌ 遗漏 |
| 复制到剪贴板 | 文档 ID/文件路径 | ❌ 遗漏 |

#### 3.12.2 检索测试

| 功能 | 说明 | 原计划 |
|------|------|--------|
| 聊天式界面 | 消息历史 | ✅ 有 |
| 流式响应 | NDJSON 实时展示 | ✅ 有 |
| 查询设置面板 | 全部 QueryParam 可配置 | ✅ 有 |
| COT 解析 | `<think>` 标签检测展示 | ❌ 遗漏 → C28 |
| LaTeX 渲染 | 行内/块级公式 | ❌ 遗漏 → C29 |
| Markdown 渲染 | 完整 Markdown 支持 | ❌ 遗漏 |
| 复制到剪贴板 | 响应文本复制 | ❌ 遗漏 |
| 用户 prompt 历史 | 最近 12 条自定义 prompt | ❌ 遗漏 |

#### 3.12.3 图谱查看器

| 功能 | 说明 | 原计划 |
|------|------|--------|
| 力导向图渲染 | Sigma.js (LightRAG) / ECharts (Aurora) | ✅ 有 |
| 图谱搜索 | 按标签搜索节点 | ✅ 有 |
| 标签管理 | 下拉+热门+模糊搜索 | ❌ 遗漏 → C21 |
| 属性面板 | 查看/编辑实体和关系属性 | ✅ 有 |
| 实体编辑 | 内联属性编辑 | ✅ 有 |
| 实体合并 | MergeDialog | ✅ 有 |
| 布局控制 | 多种布局算法 | ❌ 遗漏 |
| 缩放控制 | 放大/缩小/适应 | ✅ 有 |
| 全屏 | 切换全屏 | ❌ 遗漏 |
| 图例 | 实体类型颜色图例 | ❌ 遗漏 |
| 聚焦节点 | 点击聚焦导航 | ❌ 遗漏 |
| 节点拖拽 | 拖拽重新定位 | ✅ 有 |
| 边事件 | 点击边选择 | ❌ 遗漏 |
| 主题支持 | 深色/浅色主题标签颜色 | ❌ 遗漏 |
| 可配置 | max_depth/max_nodes/边大小/标签可见性 | ❌ 遗漏 |

#### 3.12.4 其他 UI

| 功能 | 说明 | 原计划 |
|------|------|--------|
| 健康检查 | 后端连通性监控 | ❌ 遗漏 |
| 设置面板 | 综合设置管理 | ❌ 遗漏 |
| 主题切换 | 系统/浅色/深色 | 按本项目现有 |

---

## 四、更新后的完整功能清单

### 核心功能 (29 项)

| # | 功能 | 优先级 | 来源 |
|---|------|--------|------|
| C1 | 知识图谱构建 | P0 | 原计划 |
| C2 | 双级检索引擎 (6 模式) | P0 | 原计划 |
| C3 | 多格式文档解析 | P0 | 原计划 |
| C4 | 多分块策略 (4 种) | P0 | 原计划 |
| C5 | 文档生命周期管理 | P0 | 原计划 |
| C6 | 流式查询 + 引用 | P1 | 原计划 |
| C7 | 重排序 (Cohere/Jina/Aliyun) | P1 | 原计划 (扩充 provider) |
| C8 | LLM 缓存 (查询+抽取) | P1 | 原计划 (补充细节) |
| C9 | 前端知识图谱可视化 | P1 | 原计划 |
| C10 | 增强文档管理 UI | P1 | 原计划 |
| C11 | 查询界面重构 | P1 | 原计划 |
| C12 | Chat 知识库集成 UI | P2 | 原计划 |
| **C13** | **Ollama 兼容 API** | **P0** | **从 S2 提升** |
| **C14** | **查询数据端点 (query/data)** | **P1** | **新增** |
| **C15** | **文档目录扫描** | **P1** | **新增** |
| **C16** | **文本插入 (单条/批量)** | **P1** | **新增** |
| **C17** | **内容哈希去重** | **P1** | **新增** |
| **C18** | **Track ID 追踪系统** | **P1** | **新增** |
| C19 | 查询模式前缀系统 | P1 | 新增 (与 C13 合并) |
| **C20** | **连通子图检索** | **P1** | **新增** |
| **C21** | **标签管理 (热门/搜索)** | **P1** | **新增** |
| **C22** | **实体存在性检查** | **P2** | **新增** |
| **C23** | **工作空间隔离** | **P2** | **新增** |
| C24 | OpenWebUI 兼容检测 | P2 | 新增 |
| **C25** | **加密 PDF 解密** | **P2** | **新增** |
| C26 | 文件名解析提示 | P2 | 新增 |
| C27 | 非对称 Embedding | P2 | 新增 |
| C28 | COT 思维链解析 (前端) | P2 | 新增 |
| C29 | LaTeX 公式渲染 (前端) | P2 | 新增 |

### 暂不迁移 (6 项)

| # | 功能 | 原因 |
|---|------|------|
| S1 | 多模态 VLM 分析 | 需要视觉模型 |
| S3 | RAGAS 评估框架 | 可后续添加 |
| S4 | Gunicorn 多 Worker | Uvicorn 足够 |
| S5 | 外部解析服务 (MinerU/Docling) | 原生优先 |
| S8 | K8s Helm 部署 | 非功能需求 |
| S9 | Langfuse 可观测性 | 可后续添加 |

---

## 五、更新后的实施阶段

在原 7 个 Phase 基础上，补充以下内容:

### Phase 0: 基础设施 (新增)

在 Phase 1 之前，先搭建基础设施:

1. **TiktokenTokenizer** — Token 计数工具 (所有后续模块依赖)
2. **compute_mdhash_id** — 内容哈希计算
3. **compute_args_hash** — 参数哈希 (缓存键)
4. **generate_track_id** — 追踪 ID 生成
5. **priority_limit_async_func_call** — 异步并发限制器
6. **EmbeddingFunc** — Embedding 函数封装 (含 batch、前缀、非对称支持)
7. **sanitize_filename** — 文件名安全处理
8. **get_content_summary** — 内容摘要提取
9. **性能计时日志** — `performance_timing_log()`

### Phase 1.5: Ollama API (新增)

在 Phase 1 (存储层) 完成后，并行开始 Ollama API:

1. 注册 Ollama 路由 (`/api/version`, `/api/tags`, `/api/ps`)
2. `/api/generate` — LLM 直通
3. `/api/chat` — RAG 路由 + 前缀系统 + OpenWebUI 检测
4. NDJSON 流式响应
5. Token 计数指标

### Phase 5.5: 完整查询参数 + 响应格式

在 Phase 5 API 层中，确保:
1. 全部 18 个查询参数
2. NDJSON 流式格式 (首行 references + 后续 response chunks)
3. `only_need_context` / `only_need_prompt` 模式
4. `response_type` 参数
5. `include_chunk_content` 参数
6. `hl_keywords` / `ll_keywords` 直传

### Phase 6.5: 前端补充功能

在 Phase 6 前端中，确保:
1. 文档排序 + 多状态过滤
2. 拖拽上传
3. 管线状态对话框 + 自动刷新
4. COT 解析 + LaTeX 渲染
5. Markdown 渲染
6. 图谱布局控制 + 全屏 + 图例
7. 健康检查 + 设置面板

---

## 六、新增依赖 (补充)

### 后端 Python (补充)

```
pycryptodome>=3.19        # PDF 解密 (C25)
nano-vectordb>=0.1        # 轻量向量存储 (NanoVectorDB, 可选替代 ChromaDB)
```

### 前端 TypeScript (补充)

```
katex                     # LaTeX 公式渲染 (C29)
react-markdown            # Markdown 渲染 (已有?)
remark-math               # Math 插件 (配合 katex)
rehype-katex              # Rehype 插件
```

---

## 七、完整功能对照表 (LightRAG → Aurora)

| LightRAG 功能 | 对应 Aurora 计划 | 状态 |
|--------------|----------------|------|
| 6 种查询模式 | C2 | ✅ 覆盖 |
| 知识图谱构建 | C1 | ✅ 覆盖 |
| 46 种文件扩展名 | C3 + C15 | ✅ 覆盖 |
| 4 种分块策略 | C4 | ✅ 覆盖 |
| 文档状态机 | C5 | ✅ 覆盖 |
| NDJSON 流式 | C6 | ✅ 覆盖 |
| 3 种 Reranker | C7 | ✅ 覆盖 |
| LLM 缓存 | C8 | ✅ 覆盖 |
| 图谱可视化 | C9 | ✅ 覆盖 |
| 文档管理 UI | C10 | ✅ 覆盖 |
| 查询界面 | C11 | ✅ 覆盖 |
| Chat 集成 | C12 | ✅ 覆盖 |
| Ollama API | C13 | ✅ 补充 |
| query/data 端点 | C14 | ✅ 补充 |
| 目录扫描 | C15 | ✅ 补充 |
| 文本插入 | C16 | ✅ 补充 |
| 内容哈希去重 | C17 | ✅ 补充 |
| Track ID | C18 | ✅ 补充 |
| 前缀系统 | C19 | ✅ 补充 |
| 连通子图 | C20 | ✅ 补充 |
| 标签管理 | C21 | ✅ 补充 |
| 实体检查 | C22 | ✅ 补充 |
| 工作空间 | C23 | ✅ 补充 |
| OpenWebUI | C24 | ✅ 补充 |
| PDF 解密 | C25 | ✅ 补充 |
| 文件名提示 | C26 | ✅ 补充 |
| 非对称 Embedding | C27 | ✅ 补充 |
| COT 解析 | C28 | ✅ 补充 |
| LaTeX 渲染 | C29 | ✅ 补充 |
| 18 个查询参数 | 补充 3.1 | ✅ 补充 |
| 流式格式规格 | 补充 3.2 | ✅ 补充 |
| 检索数据流详情 | 补充 3.3 | ✅ 补充 |
| 抽取参数常量 | 补充 3.4 | ✅ 补充 |
| Reranker 完整规格 | 补充 3.5 | ✅ 补充 |
| 文档 API 完整端点 | 补充 3.6 | ✅ 补充 |
| 图谱 API 完整端点 | 补充 3.7 | ✅ 补充 |
| 管线队列规格 | 补充 3.8 | ✅ 补充 |
| Embedding 配置 | 补充 3.9 | ✅ 补充 |
| 缓存系统规格 | 补充 3.10 | ✅ 补充 |
| 19 个 Prompt 模板 | 补充 3.11 | ✅ 补充 |
| 前端遗漏功能 | 补充 3.12 | ✅ 补充 |
| VLM 多模态分析 | S1 | ⏳ 暂不迁移 |
| RAGAS 评估 | S3 | ⏳ 暂不迁移 |
| Gunicorn 多 Worker | S4 | ⏳ 暂不迁移 |
| MinerU/Docling | S5 | ⏳ 暂不迁移 |
| K8s 部署 | S8 | ⏳ 暂不迁移 |
| Langfuse | S9 | ⏳ 暂不迁移 |
