# Aurora Frontend

基于 Vite + React 18 + TypeScript 5 的现代化前端应用。

## 技术栈

- **构建工具**: Vite 5
- **框架**: React 18 + react-router-dom
- **语言**: TypeScript 5（严格模式）
- **UI 组件库**: Ant Design 5
- **样式**: Tailwind CSS 3.4 + CSS Variables（Design Tokens）
- **状态管理**:
  - 服务端状态: TanStack Query v5
  - 客户端状态: Zustand
- **国际化**: i18next + react-i18next
- **测试**:
  - 单元测试: Vitest + @testing-library/react
  - E2E 测试: Playwright

## 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器（默认端口 3000，代理 /api 到 localhost:8888）
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview
```

## 测试

```bash
# 单元测试
npm test

# E2E 测试
npm run e2e

# E2E 调试模式
npm run e2e:ui
```

## 目录结构

```
src/
├── components/          # 纯 UI 组件与布局
│   ├── ui/              # 原子组件（Button, Input, Card...）
│   ├── layout/          # Shell, Sidebar
│   └── providers/       # 全局 Provider 组合
├── features/            # 按功能域组织
│   ├── chat/            # 聊天、Explore、Share
│   ├── construct/       # 构建中心（App / Database / Knowledge / Skills / Models / Flow / Prompt / Dbgpts）
│   ├── evaluation/      # 模型评测
│   └── mobile/          # 移动端适配
├── hooks/               # 全局通用 hooks
├── lib/                 # 第三方库封装（api-client, query-client, i18n）
├── services/            # 业务 API 层
├── stores/              # Zustand stores
├── styles/              # 全局样式（tokens.css, globals.css, antd-theme.ts）
└── utils/               # 纯工具函数
```

## 代码规范

- 单文件限制：组件 < 400 行，工具 < 300 行
- 按 feature 组织代码，禁止按文件类型平铺
- 所有用户-facing 字符串使用 `t()` 国际化
- 优先使用不可变更新（spread / immer）
- `npm run build` 零 TypeScript 错误（严格模式，无 `ignoreBuildErrors`）

## 性能优化

- Vite `manualChunks` 代码分割：`vendor-react`、`vendor-query`、`vendor-antd`、`vendor-markdown`
- `message-renderer` 使用 `React.lazy` + `Suspense` 懒加载
- 聊天消息列表已接入 `@tanstack/react-virtual` 虚拟滚动
- 首屏 `index.js` ~186 KB（gzipped ~62 KB）

## 路由一览

| 路由 | 页面 |
|------|------|
| `/` | Explore 首页 |
| `/chat` | 桌面端聊天页 |
| `/mobile/chat` | 移动端专属聊天页 |
| `/share/:id` | 分享对话只读页 |
| `/construct/app` | 应用管理 |
| `/construct/database` | 数据源管理 |
| `/construct/knowledge` | 知识库管理 |
| `/construct/skills` | 技能管理 |
| `/construct/models` | 模型管理 |
| `/construct/flow` | AWEL 工作流 |
| `/construct/prompt` | Prompt 管理 |
| `/construct/dbgpts` | 插件管理 |
| `/models_evaluation` | 模型评测 |
