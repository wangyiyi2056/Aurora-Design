# Ollama API 兼容层实现计划

## 目标
在 `aurora-serve/src/aurora_serve/ollama_compat/` 中实现完整的 Ollama API 兼容层，使 Aurora 可直接接入 Open WebUI 等工具。

## 现状分析
- 已有部分实现在 `knowledge/v2/ollama_routes.py`（单文件 ~375 行）
- 缺少 `/api/show` 端点
- 缺少 TOML 配置支持（model mapping）
- 缺少测试
- 缺少文档

## 待办事项

### Phase 1: 创建 `ollama_compat` 包
- [x] `__init__.py` - 公开导出
- [x] `models.py` - 冻结 Pydantic 模型（request/response）
- [x] `config.py` - TOML 配置加载器
- [x] `mapper.py` - model→KB 映射, message→QueryParam 转换, mode 检测
- [x] `streaming.py` - NDJSON 流式响应辅助
- [x] `routes.py` - 所有 API 端点

### Phase 2: 更新现有接线
- [x] 更新 `server.py` 导入路径
- [x] 将旧 `knowledge/v2/ollama_routes.py` 替换为薄代理
- [x] 在 `configs/aurora.toml` 添加 `[ollama_compat]` 配置

### Phase 3: 测试
- [x] Chat API（streaming + non-streaming）
- [x] Generate API（streaming + non-streaming）
- [x] Model management（`/api/tags`, `/api/show`）
- [x] 请求/响应映射（mapper）
- [x] 配置加载
- [x] 模拟 Open WebUI 请求模式

### Phase 4: 文档
- [x] `README_OLLAMA.md` - Open WebUI 配置指南、故障排除

## 架构决策
1. 使用 Pydantic v2 + `frozen=True` 而非 dataclass（保持 FastAPI 兼容 + 不可变性）
2. 将 model→KB 映射放在配置中，支持多知识库
3. 添加 `/api/show` 端点（Open WebUI 需要）
4. 流式响应抽取为独立模块，减少路由代码复杂度
