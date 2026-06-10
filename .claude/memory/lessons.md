# 项目经验教训

## 2026-05-29: 知识库管道 "Claude Code exited with code 1" Bug

### 现象
用户上传文件到知识库后，处理状态变为 FAILED，错误信息为 "Claude Code exited with code 1"。

### 根因
数据库 `model_configs` 表中的模型配置名为 `chat-cli-claude`，这是 Aurora 系统内部的模型标识名（用于 UI 显示和内部路由），但 `local_cli.py` 的 `build_agent_args()` 把它当作真实的 CLI 模型名，以 `--model chat-cli-claude` 参数传给了 Claude CLI 子进程。Claude CLI 不认识这个模型名，直接以 exit code 1 退出。

从终端直接运行 Claude CLI（不传 `--model` 参数）时工作正常，因为会使用代理的默认模型。

### 修复
在 `packages/aurora-core/src/aurora_core/model/local_cli.py` 的 `sanitize_custom_model()` 函数中，过滤掉以 `chat-cli-` 为前缀的内部标识名，使其不传给 CLI 的 `--model` 参数。

```python
def sanitize_custom_model(model: str | None) -> str | None:
    if model is None:
        return None
    value = model.strip()
    if not value or value == "default":
        return None
    # Strip internal Aurora model identifiers that are not real model names
    if value.startswith("chat-cli-"):
        return None
    ...
```

### 教训
1. **区分内部标识名和外部 API 参数**：Aurora 数据库中的 `model_configs.name` 是内部标识（如 `chat-cli-claude`），不等于 CLI 工具认识的模型名。在传递给外部工具之前，必须做名称映射或过滤。
2. **子进程调试**：当子进程返回非零退出码但没有 stderr 输出时，需要对比"直接运行"和"代码中运行"的环境差异（环境变量、参数等）。
3. **V1/V2 混合调用**：知识库列表页用 V1 hook 创建但 V2 hook 展示，query key 不匹配导致页面不刷新——这是典型的版本迁移不彻底问题。
