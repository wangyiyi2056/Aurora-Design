# Phase 4 完成记录：工作流编排与沙箱安全 — AWEL + Sandbox

**完成日期**：2026-04-15

## 已交付模块

### 1. AWEL 工作流编排引擎（`chatbi_core.awel`）

AWEL（Agentic Workflow Expression Language）是 ChatBI 的声明式工作流引擎。

#### 算子层（`operator/`）

- `BaseOperator` — 所有算子的基类，支持 `>>` 语法链式连接
- `MapOperator` — 单输入单输出映射算子
- `BranchOperator` — 分支算子，支持条件路由

#### DAG 层（`dag/`）

- `DAG` — 有向无环图数据结构
- `DAGBuilder` — DAG 构建器，通过 `add_node()` 注册算子
- `DAGExecutor` — 拓扑排序执行器，按依赖顺序逐个执行算子

#### 调度层（`task/`）

- `TaskScheduler` — 简单的异步任务调度器，支持并发提交和统一等待

#### 可视化元数据（`flow/`）

- `FlowMetadata` / `OperatorMetadata` — 供前端渲染流程图的元数据结构

### 2. AWEL 服务 API（`chatbi_serve.awel`）

- `GET /api/v1/awel/operators` — 列出可用算子类型及其元数据
- `POST /api/v1/awel/run` — 运行一个示例 AWEL 工作流

示例工作流：
```python
op1 = EchoOperator(name="echo")
op2 = UpperOperator(name="upper")
op1 >> op2
builder = DAGBuilder()
builder.add_node(op1).add_node(op2)
dag = builder.build()
executor = DAGExecutor(dag)
outputs = await executor.execute("hello")
# outputs: {"echo": "echo: hello", "upper": "ECHO: HELLO"}
```

### 3. 沙箱执行环境（`chatbi-sandbox`）

独立的沙箱子包，提供安全的代码执行能力。

#### DockerCodeExecutor

- 基于 `docker run` 的隔离执行
- 支持参数配置：镜像、超时、内存限制、网络隔离
- 自动清理容器（`--rm`）
- 超时后强制 `docker kill` 容器

#### 沙箱 API 网关

- `POST /execute` — 接收代码并在 Docker 中执行
- `GET /health` — 健康检查

启动方式：
```bash
uv run uvicorn sandbox.api.server:app --port 9000
```

### 4. 测试覆盖

新增 2 个测试：
- `tests/core/test_awel.py` — DAG 构建与执行测试

**总计 25 个测试全部通过**

## API 使用示例

### 运行 AWEL 工作流

```bash
curl -X POST http://localhost:8000/api/v1/awel/run \
  -H "Content-Type: application/json" \
  -d '{"initial_input": "hello"}'
```

### 列出算子

```bash
curl http://localhost:8000/api/v1/awel/operators
```

### 沙箱执行代码

```bash
curl -X POST http://localhost:9000/execute \
  -H "Content-Type: application/json" \
  -d '{"code": "print(1+1)", "language": "python"}'
```

## 安全约束

- Docker 沙箱默认网络隔离（`--network none`）
- 默认内存限制 128m
- 默认超时 30 秒
- 禁止访问宿主机敏感目录（仅挂载临时目录只读）

## 企业级扩展预留

- `DAGBuilder` 已支持从 JSON 反序列化重建算子链路（为前端可视化预留）
- `BranchOperator` 为条件分支和循环预留了扩展点
- 沙箱可扩展为支持 Jupyter Kernel、浏览器自动化（Selenium）
