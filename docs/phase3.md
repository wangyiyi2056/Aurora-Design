# Phase 3 完成记录：RAG 与 Agent 框架 — 知识库 + 多 Agent 协作

**完成日期**：2026-04-15

## 已交付模块

### 1. RAG 核心模块（`chatbi_ext.rag`）

#### 知识库（`knowledge/`）

- `BaseKnowledge` — 知识库抽象
- `KnowledgeFactory.from_file_path()` — 从文件路径创建知识库
- `Document` — 统一文档数据结构（content + metadata）

#### 文档切分（`transformer/`）

- `ChunkParameters` — 分块参数（chunk_size, chunk_overlap）
- `ChunkManager` — 按固定长度滑动窗口切分文档

#### 组装器（`assembler/`）

- `BaseAssembler` — 组装器抽象
- `EmbeddingAssembler` — 文档加载 → 切分 → Embedding → 写入向量库

#### 检索器（`retriever/`）

- `BaseRetriever` — 检索器抽象
- `EmbeddingRetriever` — 基于向量相似度的检索
- `BM25Retriever` — 基于关键词匹配的回退检索

#### AWEL 算子（`operators/`）

- `BaseOperator` — 算子抽象
- `KnowledgeLoadOperator` — 加载文档算子
- `VectorStorageOperator` — 向量化存储算子

### 2. 向量存储（`chatbi_ext.storage`）

- `VectorStoreBase` — 向量存储抽象
- `ChromaVectorStore` — ChromaDB 实现，支持内存/持久化模式

### 3. Embedding Adapter（`chatbi_core.model.adapter`）

- `OpenAIEmbeddings` — 对接 OpenAI Embedding API（默认 `text-embedding-3-small`）

### 4. Agent 框架（`chatbi_core.agent`）

- `BaseAgent` — Agent 抽象（Plan → Action → Observation → Final Answer）
- `AgentResource` — Agent 可调用的资源抽象
- `BaseSkill` / `SkillRegistry` — Skill 定义与注册表
- `ShortTermMemory` — 短期对话记忆管理
- `ManagerAgent` — 多 Agent 编排入口（Manager + Worker 模式雏形）

### 5. 服务 API 扩展（`chatbi_serve`）

#### Agent API

- `GET /api/v1/agent/skills` — 列出可用 Skills

内置示例 Skill：
- `CSVAnalysisSkill` — 分析 CSV 内容并返回行数、列名、前 5 行预览

#### Knowledge API

- `POST /api/v1/knowledge/upload?name={name}` — 上传文件并建立向量索引
- `GET /api/v1/knowledge` — 列出已建立的知识库
- `POST /api/v1/knowledge/{name}/query?query={text}` — 基于向量检索问答

### 6. 配置扩展

`configs/chatbi.toml` 启动时自动：
- 注册 OpenAI Embedding 模型
- 初始化 `SkillRegistry`（含内置 CSV Skill）
- 初始化 `knowledge_stores`

### 7. 测试覆盖

新增 6 个测试：
- `tests/ext/test_rag.py` — RAG 完整流程测试
- `tests/ext/test_storage.py` — ChromaVectorStore 测试
- `tests/core/test_agent.py` — Agent / Skill / Memory 测试

**总计 23 个测试全部通过**

## API 使用示例

### 上传文件建立知识库

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/upload?name=docs" \
  -F "file=@README.md"
```

### 知识库问答

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/docs/query?query=What%20is%20ChatBI"
```

### 列出 Skills

```bash
curl http://localhost:8000/api/v1/agent/skills
```

## 架构预留

- `BaseOperator` 和 `BaseAssembler` 为 Phase 4 的 AWEL DAG 编排预留了算子接口
- `ManagerAgent` 为后续多 Agent 团队协作（Manager + Worker）预留了入口
