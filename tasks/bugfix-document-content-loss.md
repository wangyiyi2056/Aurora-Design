# Bug Fix: 文档内容丢失问题

## 问题描述

用户报告部分文档状态显示为 PROCESSED，但查看内容时为空。

## 根本原因

**`clear_llm_cache()` 和 `reprocess_all()` 方法调用了 `self._kv.drop()`**，这会删除整个 KV 存储，包括：

| 数据类型 | Key 模式 | 被删除？ | 应该删除？ |
|---------|---------|---------|-----------|
| 文档完整内容 | `full_docs:*` | ✅ 被删了 | ❌ 不应该 |
| 文档 Chunks | `text_chunks:*` | ✅ 被删了 | ❌ 不应该 |
| LLM 抽取缓存 | `llm_response_cache:*` | ✅ 被删了 | ✅ 这才是该删的 |
| 实体数据 | `full_entities:*` | ✅ 被删了 | ❌ 不应该 |
| 关系数据 | `full_relations:*` | ✅ 被删了 | ❌ 不应该 |

**特别严重的是**：通过 `insert_text` 插入的文档，原始文本存在 KV 中，`drop()` 之后 parse_worker 再也读不到原文了，文档就变成空的了。

## 修复方案

### 1. 修复 `clear_llm_cache()` - 只删除 LLM 缓存

**文件**: `packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`

```python
# 修复前（错误）
async def clear_llm_cache(self, kb_name: str) -> bool:
    try:
        await self._kv.drop()  # ❌ 删除所有数据
        return True
    except Exception:
        return False

# 修复后（正确）
async def clear_llm_cache(self, kb_name: str) -> bool:
    try:
        cache_prefix = self._ns(
            kb_name, f"{NameSpace.KV_STORE_LLM_RESPONSE_CACHE}:"
        )
        all_keys = await self._kv.all_keys()
        cache_keys = [k for k in all_keys if k.startswith(cache_prefix)]
        if cache_keys:
            await self._kv.delete(cache_keys)  # ✅ 只删除缓存
        return True
    except Exception:
        return False
```

### 2. 修复 `reprocess_all()` - 使用修复后的 `clear_llm_cache()`

```python
# 修复前
await self._kv.drop()  # ❌ 删除所有数据

# 修复后
await self.clear_llm_cache(kb_name)  # ✅ 只删除 LLM 缓存
```

### 3. 添加文档完整性诊断功能

**新增 API 端点**: `GET /documents/diagnose`

返回诊断报告：
```json
{
  "total": 10,
  "processed": 8,
  "healthy": 6,
  "missing_content": 1,
  "missing_chunks": 1,
  "repairable": 2,
  "details": {
    "healthy_docs": [...],
    "missing_content_docs": [...],
    "missing_chunks_docs": [...],
    "repairable_docs": [...]
  }
}
```

### 4. 添加自动修复功能

**新增 API 端点**: `POST /documents/repair`

自动修复丢失内容/chunks 的文档（仅限原始文件仍在磁盘上的文档）。

### 5. 前端 UI 增强

#### DocumentPreview 组件增强
- ✅ 显示文档完整内容（支持 Markdown 渲染）
- ✅ 显示文档被拆分成哪些 chunks
- ✅ 每个 chunk 可展开查看完整内容
- ✅ 支持复制 chunk 内容

#### DocumentManager 新增诊断按钮
- 🩺 诊断按钮：点击后显示诊断对话框
- 诊断对话框显示：
  - 总文档数 / 正常数 / 问题数
  - 丢失内容的文档列表（标记是否可修复）
  - 丢失 chunks 的文档列表（标记是否可修复）
  - 自动修复按钮（如果有可修复的文档）

## 使用方法

### 诊断文档完整性

1. 在知识库页面点击 🩺 诊断按钮
2. 查看诊断报告：
   - ✅ 绿色：文档正常
   - ⚠️ 黄色：丢失 chunks
   - ❌ 红色：丢失完整内容
   - 🔵 蓝色：可自动修复
3. 如果有可修复的文档，点击「自动修复」按钮

### 查看文档内容和 Chunks

1. 在文档列表点击 👁️ 眼睛图标
2. 弹出侧边面板，默认显示「文档内容」标签页
3. 点击「Chunks」标签页查看所有 chunks
4. 点击每个 chunk 展开查看完整内容
5. 可以复制 chunk 内容

### 重新处理失败文档

如果文档状态为 FAILED，可以：
1. 点击 🔄 重新处理按钮（只重新处理失败的文档）
2. 或在诊断对话框中点击「自动修复」

## 测试验证

```bash
# 后端测试
uv run python -c "
import asyncio
from aurora_serve.knowledge.v2.service import KnowledgeV2Service
# ... 测试代码见上面的集成测试
"

# 前端编译检查
cd frontend && npx tsc --noEmit --skipLibCheck
```

## 影响范围

- ✅ 修复了 `clear_llm_cache()` 删除所有数据的 bug
- ✅ 修复了 `reprocess_all()` 删除所有数据的 bug
- ✅ 新增文档完整性诊断功能
- ✅ 新增自动修复功能
- ✅ 新增文档内容和 chunks 查看功能
- ✅ 前端 UI 增强

## 文件变更

### 后端
- `packages/aurora-serve/src/aurora_serve/knowledge/v2/service.py`
  - 修复 `clear_llm_cache()`
  - 修复 `reprocess_all()`
  - 新增 `diagnose_documents()`
  - 新增 `repair_documents()`
  - 新增 `get_document_content()`
  - 新增 `get_document_chunks()`

- `packages/aurora-serve/src/aurora_serve/knowledge/v2/document_routes.py`
  - 新增 `GET /documents/{doc_id}/content`
  - 新增 `GET /documents/{doc_id}/chunks`
  - 新增 `GET /documents/diagnose`
  - 新增 `POST /documents/repair`

### 前端
- `frontend/src/services/knowledge-v2.ts`
  - 新增 `diagnoseDocuments()`
  - 新增 `repairDocuments()`

- `frontend/src/features/construct/knowledge/hooks/use-knowledge-v2.ts`
  - 新增 `useDiagnoseDocuments()`
  - 新增 `useRepairDocuments()`

- `frontend/src/features/construct/knowledge/components/DocumentPreview.tsx`
  - 重写为双标签页界面（文档内容 + Chunks）
  - 支持 Markdown 渲染和 Raw 模式切换
  - 支持 chunk 展开/折叠和复制

- `frontend/src/features/construct/knowledge/components/DocumentManager.tsx`
  - 新增诊断按钮和诊断对话框
  - 支持自动修复功能

## 后续建议

1. **定期诊断**：建议用户定期运行诊断，及时发现内容丢失问题
2. **备份策略**：对于重要文档，建议保留原始文件备份
3. **监控告警**：可以考虑添加监控，当检测到内容丢失时自动告警
4. **数据迁移**：如果有历史数据已经丢失，可以通过诊断+修复功能批量修复
