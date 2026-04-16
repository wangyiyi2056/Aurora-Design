# Phase 1 完成记录：基础骨架 — 模型抽象 + 对话服务

**完成日期**：2026-04-15

## 已交付模块

### 1. 项目结构（uv workspace monorepo）

- `packages/chatbi-core/` — 核心框架层
- `packages/chatbi-serve/` — FastAPI 服务层
- `packages/chatbi-ext/` — 扩展能力层（占位）
- `packages/chatbi-app/` — 应用启动入口

### 2. 核心接口

#### BaseLLM / BaseEmbeddings

```python
class BaseLLM(ABC):
    async def achat(self, messages: List[Message], **kwargs) -> ModelOutput: ...
    async def achat_stream(self, messages: List[Message], **kwargs) -> AsyncIterator[ModelOutput]: ...
```

实现：
- `OpenAILLM` — 对接 OpenAI 兼容 API
- `ModelRegistry` — 按名称管理模型实例

#### 配置系统

- `Settings`（Pydantic Settings）+ TOML 加载
- 默认配置文件：`configs/chatbi.toml`
- 支持环境变量覆盖（`CHATBI_*`）

#### 组件注册中心

- `ComponentRegistry` — SystemApp 雏形，为后续服务解耦预留

### 3. API 接口

- `POST /api/v1/health` — 健康检查
- `POST /api/v1/chat/completions` — 对话接口（兼容 OpenAI）
  - 支持流式 SSE 返回
  - 支持 model 参数选择已注册模型

### 4. 启动方式

```bash
uv sync --all-packages
uv run uvicorn chatbi_app.main:app --host 0.0.0.0 --port 8000
```

### 5. 测试覆盖

- 12 个测试全部通过
- 覆盖：config、model registry、openai adapter、chat API、chat service

## 为后续阶段预留的结构

- `chatbi_core.component.ComponentRegistry` → Phase 3 Agent / Skill 注册
- `chatbi_ext.rag/`、`chatbi_ext.storage/` → Phase 3 RAG / VectorStore
- `ModelRegistry` 已预留 `register_embeddings` / `get_embeddings`
