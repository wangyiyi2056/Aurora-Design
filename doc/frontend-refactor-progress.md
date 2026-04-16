# ChatBI 前端重构进度记录

> 基于 PLANS.md (DB-GPT-Web 前端 0 到 1 重构实施计划) 执行
> 开始日期: 2026-04-15

---

## 阶段总览

| 阶段 | 名称 | 状态 | 备注 |
|------|------|------|------|
| Phase 0 | 基础建设与目录重构 | ✅ Completed | 引入 AntD + Tailwind + TanStack Query + Zustand，建立设计系统 |
| Phase 1 | 核心聊天体验 | ✅ Completed | 拆分聊天组件、Explore 首页、模型选择器、消息复制、Markdown 渲染 |
| Phase 2 | 构建中心模块 | ✅ Completed (Basic) | Construct Shell + 8 个子模块路由与占位页面 |
| Phase 3 | 高级功能 | ✅ Completed (Basic) | Evaluation / Share 页面占位 |
| Phase 4 | 打磨与规模化 | 🚧 In Progress | 性能、测试、a11y、国际化、代码分割 |

---

## Phase 0: 基础建设与目录重构

### 2026-04-15 - Step 1: 依赖治理与目录结构

**已完成:**
- 分析现有前端结构 (Vite + React + react-router-dom)
- 确定迁移策略: 保留 Vite 构建工具，引入 PLANS.md 指定的核心库栈
- 新增依赖:
  - `antd` (Ant Design 5)
  - `@ant-design/icons`
  - `tailwindcss@3.4` + `postcss` + `autoprefixer`
  - `@tanstack/react-query` v5
  - `zustand`
  - `clsx`, `tailwind-merge`
  - `axios`

### 2026-04-15 - Step 2: 设计系统与基础架构搭建

**已完成:**
- 初始化 Tailwind CSS v3 配置 (`tailwind.config.js`) 并绑定 CSS Variables
- 创建 `src/styles/tokens.css` (Design Tokens)，支持 dark/light 双主题
- 创建 `src/styles/globals.css` (全局样式 + Tailwind 指令 + 滚动条样式)
- 创建 `src/styles/antd-theme.ts` (Ant Design 主题收敛，使用 CSS 变量)
- 创建 `src/lib/api-client.ts` (Axios 统一封装)
- 创建 `src/lib/query-client.ts` (TanStack Query Client 配置)
- 创建 `src/stores/global-store.ts` (Zustand: 主题/语言/侧边栏折叠，持久化到 localStorage)
- 创建 `src/stores/chat-store.ts` (Zustand: 聊天状态)
- 创建 `src/components/providers/app-providers.tsx`
- 创建 `src/components/layout/shell.tsx` 和 `sidebar.tsx`
- 创建 `src/hooks/use-theme.ts`
- 配置 Vite `@/` 路径别名

### 2026-04-15 - Step 3: API 服务层拆分

**已完成:**
- `src/services/chat.ts`
- `src/services/database.ts`
- `src/services/knowledge.ts`
- `src/services/models.ts`
- `src/services/flow.ts`
- 删除旧的 `src/lib/api.ts` 和 `src/index.css`

### 2026-04-15 - Step 4: TanStack Query Hooks

**已完成:**
- `src/features/chat/hooks/use-chat-stream.ts`
- `src/features/construct/database/hooks/use-datasources.ts`
- `src/features/construct/knowledge/hooks/use-knowledge.ts`
- `src/features/construct/skills/hooks/use-skills.ts`
- `src/features/construct/flow/hooks/use-flow.ts`

### 2026-04-15 - Step 5: 基础 UI 原子组件库

使用 `design-system-architect` agent 创建:
- `src/components/ui/button.tsx`
- `src/components/ui/card.tsx`
- `src/components/ui/input.tsx`
- `src/components/ui/select.tsx`
- `src/components/ui/modal.tsx`
- `src/components/ui/badge.tsx`
- `src/components/ui/empty.tsx`

---

## Phase 1: 核心聊天体验

### 2026-04-15 - 聊天组件拆分

**已完成组件:**
- `src/features/chat/components/chat-header.tsx`
- `src/features/chat/components/model-selector.tsx`
- `src/features/chat/components/chat-message-item.tsx` (新增复制按钮)
- `src/features/chat/components/chat-message-list.tsx`
- `src/features/chat/components/chat-input.tsx`
- `src/features/chat/components/chat-welcome.tsx`

**重构后页面:**
- `src/features/chat/pages/chat-page.tsx`

### 2026-04-15 - 消息 Markdown 渲染引擎

**已完成:**
- 安装 `react-markdown`, `remark-gfm`, `react-syntax-highlighter`
- 创建 `src/features/chat/components/message-renderer.tsx`
- 支持 Markdown、代码块语法高亮 (vscDarkPlus 主题)、表格、列表、链接
- `message-renderer.tsx` 使用 `React.lazy` + `Suspense` 懒加载，减少首屏体积
- 助手消息自动渲染 Markdown，用户消息保持纯文本

### 2026-04-15 - Explore 首页

**已完成:**
- `src/features/chat/pages/explore-page.tsx` — 入口导航页
- 更新路由: `/` → Explore, `/chat` → Chat
- 更新 Sidebar 导航

---

## Phase 2: 构建中心模块

### 2026-04-15 - Construct Shell 与路由重构

**已完成:**
- `src/features/construct/components/construct-shell.tsx` — Tabs 二级导航
- 将原有独立路由迁移到 `/construct/*` 体系:
  - `/construct/app`
  - `/construct/database`
  - `/construct/knowledge`
  - `/construct/skills`
  - `/construct/models`
  - `/construct/flow`
  - `/construct/prompt`
  - `/construct/dbgpts`
- 现有功能页面已包裹在 ConstructShell 中
- 新增占位页面:
  - `app-list-page.tsx`
  - `models-page.tsx`
  - `prompt-page.tsx`
  - `dbgpts-page.tsx`

---

## Phase 3: 高级功能

### 2026-04-15 - 基础占位页面

**已完成:**
- `src/features/evaluation/pages/evaluation-list-page.tsx` → `/models_evaluation`
- `src/features/chat/pages/share-page.tsx` → `/share/:id`

---

## Phase 4: 打磨与规模化

### 性能优化

**已完成:**
- Vite `manualChunks` 代码分割:
  - `vendor-react`: 163KB
  - `vendor-query`: 42KB
  - `vendor-antd`: 664KB
  - `vendor-markdown`: 773KB (懒加载，不影响首屏)
- 首屏 `index.js` 降至 ~145KB (gzipped ~49KB)
- `message-renderer` 懒加载 chunk 仅 5.5KB

### 国际化 (i18n)

**已完成:**
- 安装 `i18next`, `react-i18next`, `i18next-browser-languagedetector`
- 创建 `src/lib/i18n.ts` 初始化配置
- 添加翻译文件:
  - `public/locales/zh/common.json`
  - `public/locales/en/common.json`
- `main.tsx` 中导入初始化
- `sidebar.tsx` 导航和 App 名称已使用 `t()`，并添加语言切换按钮
- 补全剩余页面的 `t()` 翻译调用:
  - `chat-input.tsx`, `chat-header.tsx`, `chat-welcome.tsx`
  - `explore-page.tsx`
  - `construct-shell.tsx`, `database-list-page.tsx`, `knowledge-page.tsx`, `skills-page.tsx`, `flow-page.tsx`
- 语言检测顺序: `localStorage` → `navigator`

### 测试体系

**已完成:**
- 安装 `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`
- 创建 `vitest.config.ts` 和 `tests/setup.ts`
- 编写首批单元测试:
  - `src/utils/cn.test.ts`
  - `src/stores/global-store.test.ts`
  - `src/stores/chat-store.test.ts`
- `npm test` 通过 (7/7 tests passed)
- `package.json` 新增 `test` 和 `test:watch` 脚本

### E2E 测试 (Playwright)

**已完成:**
- 安装 `@playwright/test` v1.59.1 并下载 Chromium / WebKit 浏览器
- 创建 `playwright.config.ts` (Desktop Chrome + iPhone 12 双项目)
- `package.json` 新增 `e2e` 和 `e2e:ui` 脚本
- 编写 3 个 spec 文件，覆盖 14 个测试用例:
  - `e2e/explore.spec.ts`: Explore 页面加载、导航到 Chat、导航到 Construct Database
  - `e2e/chat.spec.ts`: Chat 输入框与发送按钮可见性、输入消息并点击发送
  - `e2e/construct.spec.ts`: Construct Shell Tabs 展示、切换 Tab 改变 URL
- `npm run e2e` 全部通过 (14/14 passed, 16.6s)

### 当前构建状态
- `npm run build` 持续通过
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### 可访问性优化 (a11y)

**已完成:**
- `chat-input.tsx`: 修复为 `Enter` 发送、`Shift+Enter` 换行（通过 `onKeyDown` 拦截）
- `Input` 与发送 `Button` 添加 `aria-label`
- `sidebar.tsx`: 收起/展开/语言切换按钮补充 `aria-label` 和 `title`，使用翻译键
- `chat-message-item.tsx`: 头像图标添加 `aria-hidden`，复制按钮已有 `aria-label`
- `explore-page.tsx` / `chat-welcome.tsx`: 快捷入口按钮添加 `aria-label`，图标添加 `aria-hidden`
- `globals.css` 增加 `@media (prefers-reduced-motion: reduce)`，禁用所有过渡与动画
- `vitest.config.ts` 排除 `e2e/` 目录，避免 Vitest 误运行 Playwright 测试

### i18n Namespace 拆分

**已完成:**
- 将 monolithic `common.json` 拆分为 3 个 namespace:
  - `common`: appName, nav, sidebar, actions
  - `chat`: chat.* + explore.*
  - `construct`: construct.* + database.* + knowledge.* + agent.* + awel.*
- 新增翻译文件:
  - `public/locales/zh/chat.json`, `zh/construct.json`
  - `public/locales/en/chat.json`, `en/construct.json`
- 更新 `src/lib/i18n.ts` 加载 namespace，设置 `ns: ["common", "chat", "construct"]`
- 更新所有组件的 `useTranslation()` 调用，使用对应的 namespace:
  - `chat` namespace: `chat-header`, `chat-input`, `chat-welcome`, `explore-page`, `chat-message-item`
  - `construct` namespace: `construct-shell`, `database-list-page`, `knowledge-page`, `skills-page`, `flow-page`
  - `common` namespace: `sidebar` (保持不变)

### 移动端适配 (Mobile Shell / Chat UI)

**已完成:**
- 创建 `src/hooks/use-media-query.ts`，提供 `useIsMobile()` hook ( breakpoint 767px )
- 修改 `shell.tsx`: 移动端 (< 768px) 隐藏 Sidebar，`main` padding 从 `p-6` 降为 `p-3`
- 创建 `src/features/mobile/components/mobile-nav.tsx`: 顶部固定导航栏（返回、标题、新对话按钮）
- 创建 `src/features/mobile/pages/mobile-chat-page.tsx`: 移动端专属聊天页，底部固定输入栏，复用 `chat-store` 和 `useChatStream`
- 修改 `App.tsx`: 添加 `/mobile/chat` 独立路由，该路由不经过 `Shell`（避免 Sidebar）
- 更新 `e2e/explore.spec.ts`: 在 mobile viewport 下跳过 `navigate to construct database`（Sidebar 已隐藏）

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### Prompt Editor

**已完成:**
- 重写 `src/features/construct/prompt/pages/prompt-page.tsx`
- 左侧列表展示所有 Prompt，支持新增、删除
- 右侧编辑器包含：名称输入、内容 textarea、变量自动提取（`{{var}}`）、实时预览
- 所有文案接入 `construct` namespace 翻译

### App Builder

**已完成:**
- 重写 `src/features/construct/app/pages/app-list-page.tsx`
- App 卡片列表视图，展示名称、描述、类型、模型、发布状态
- 三步骤向导式创建表单（Ant Design Steps + Form）：
  - Step 1: 基本信息（名称、描述、类型）
  - Step 2: 配置参数（模型选择）
  - Step 3: 发布确认
- 所有文案接入 `construct` namespace 翻译

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### Models 管理

**已完成:**
- 重写 `src/features/construct/models/pages/models-page.tsx`
- 模型列表展示：名称、类型、运行状态
- 支持启动/停止状态切换
- 支持新增模型（名称 + 类型选择）
- 所有文案接入 `construct` / `common` namespace 翻译

### Dbgpts 插件管理

**已完成:**
- 重写 `src/features/construct/dbgpts/pages/dbgpts-page.tsx`
- 使用 Tabs 分为 "Hub" 和 "My Plugins"
- Hub：展示可安装插件列表（模拟数据），支持安装到 My Plugins
- My Plugins：展示已安装插件，支持卸载
- 所有文案接入 `construct` namespace 翻译

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### 知识库管理增强

**已完成:**
- 重写 `src/features/construct/knowledge/pages/knowledge-page.tsx`
- 使用 Tabs 组织四个模块：知识库列表、查询、文档分块策略、知识图谱
- 文档分块策略：
  - 支持三种策略选择（固定长度 / 按段落 / 语义分块）
  - 块大小 Slider（128 ~ 2048，步进 128）
  - 重叠长度 Slider（0 ~ 256，步进 16）
- 知识图谱可视化占位：
  - SVG 节点连线示意背景
  - 展示实体数 / 关系数统计卡片
- 所有文案接入 `construct` namespace 翻译（新增 `knowledge.chunking`, `knowledge.graph` 等键）

### Bundle 分析

**已完成:**
- 运行 `npx vite-bundle-visualizer` 生成分析报告
- 当前生产构建 chunks 分布：
  - `index.js`: ~181 KB (gzipped ~60 KB)
  - `vendor-react.js`: ~164 KB (gzipped ~53 KB)
  - `vendor-query.js`: ~43 KB (gzipped ~13 KB)
  - `vendor-antd.js`: ~773 KB (gzipped ~247 KB)
  - `vendor-markdown.js`: ~774 KB (gzipped ~269 KB) — 懒加载
  - `message-renderer.js`: ~5.5 KB (gzipped ~1.6 KB) — 懒加载
- 结论：首屏主 chunk 控制在合理范围，AntD 与 Markdown 库体积较大但已拆分为独立 chunk；后续如需进一步缩减可考虑 AntD 按需加载或替换为轻量组件

### 虚拟滚动评估与落地

**已完成:**
- 安装 `@tanstack/react-virtual`
- 重构 `src/features/chat/components/chat-message-list.tsx`
- 实现基于 `useVirtualizer` 的消息列表虚拟滚动：
  - 动态高度测量 (`measureElement`)
  - `overscan: 5` 减少白屏
  - 保留自动滚动到底部行为
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### Flow 编辑器可视化增强

**已完成:**
- 重写 `src/features/construct/flow/pages/flow-page.tsx`
- 使用 Tabs 组织三个模块：画布、算子、运行
- 画布占位：
  - 左侧节点库（开始 / LLM / 条件 / 结束）
  - 中间 SVG 画布展示 Mock 节点与连线
  - 右侧属性面板（点击节点高亮并显示配置占位）
- 保留原有算子列表与运行工作流功能
- 所有文案接入 `construct` namespace 翻译（新增 `awel.canvas`, `awel.nodePalette`, `awel.properties`, `awel.nodes.*` 等键）

### Evaluation 评测模块增强

**已完成:**
- 重写 `src/features/evaluation/pages/evaluation-list-page.tsx`
- 使用 Tabs 分为 "评测任务" 与 "数据集"
- 评测任务列表：展示任务名称、状态标签（待运行 / 运行中 / 已完成）、模型
- 数据集：卡片网格展示数据集名称与描述
- 所有文案接入 `construct` namespace 翻译（新增 `evaluation.*` 键）

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### Share 分享页增强

**已完成:**
- 重写 `src/features/chat/pages/share-page.tsx`
- 使用 `ChatMessageItem` 渲染只读消息列表（Mock 数据）
- 展示分享对话 ID 与只读提示
- 接入 `chat` namespace 翻译（新增 `share.title`, `share.readonly`）

### 文档更新

**已完成:**
- 创建 `frontend/README.md`：说明技术栈、目录结构、快速开始、测试命令、性能优化、路由一览
- 更新根目录 `README.md`：补充前端完整页面说明与前端测试指引，链接到 `frontend/README.md`

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### Component 使用文档

**已完成:**
- 创建 `frontend/docs/ui-components.md`
- 文档覆盖 7 个原子组件：Button、Card、Input、Select、Modal、Badge、Empty
- 说明设计原则、继承的 Ant Design API、默认注入的 Tailwind 类名、使用示例

---

### ChatGPT 风格聊天输入框升级

**已完成:**
- 重写 `src/features/chat/components/chat-input.tsx`
- 采用类 ChatGPT 的圆角容器设计 (`rounded-3xl` + `bg-surface` + `border-border` + `shadow-sm`)
- 将单行 `Input` 替换为支持自动高度的 `Input.TextArea` (`autoSize`)，支持多行输入与 `Shift+Enter` 换行
- 底部操作栏分为左右两部分：
  - 左下角新增 4 个功能按钮（图标 + 文字）：
    - 从本地文件添加 (`PaperClipOutlined`)
    - 使用技能 (`ThunderboltOutlined`)
    - 使用知识库 (`BookOutlined`)
    - 使用数据库 (`DatabaseOutlined`)
  - 右侧改为圆形发送按钮 (`UpOutlined`)，空内容时自动禁用
- 更新 `chat-page.tsx` / `mobile-chat-page.tsx` 传入新按钮的回调占位
- 更新 `chat.json`（zh/en）新增翻译键：`chat.attachFile`、`chat.useSkill`、`chat.useKnowledge`、`chat.useDatabase`
- 更新 `e2e/chat.spec.ts`：将定位器从 `input[placeholder]` 改为 `textarea[placeholder]`
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 全局主题切换功能

**已完成:**
- `sidebar.tsx` 底部新增主题切换按钮（太阳/月亮图标），点击在 dark/light 间切换
- `mobile-nav.tsx` 顶部导航栏右侧新增主题切换按钮，移动端也可切换
- 更新 `common.json`（zh/en）新增翻译键：`sidebar.toggleTheme`、`sidebar.lightMode`、`sidebar.darkMode`
- 主题状态通过 `global-store` 持久化到 localStorage，刷新后保持上次选择
- `useTheme` hook 已自动将 `data-theme` 同步到 `document.documentElement`，CSS 变量和 AntD 主题已跟随响应
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

---

## 重构完成总结

**截至当前，ChatBI 前端 0 到 1 重构的所有计划任务已基本完成：**

- **Phase 0 基础建设**: 目录重构、设计系统（tokens + Tailwind + AntD 主题收敛）、API 分层（Axios + TanStack Query + services）、Zustand 状态管理、基础 UI 组件库
- **Phase 1 核心聊天体验**: Explore 首页、聊天页（消息渲染、模型选择、输入发送）、移动端专属聊天页
- **Phase 2 构建中心模块**: Construct Shell + 8 个子模块全部具备功能性页面（App / Database / Knowledge / Skills / Models / Flow / Prompt / Dbgpts）
- **Phase 3 高级功能**: Flow 可视化画布占位、Evaluation 评测任务/数据集管理、Share 分享页只读渲染
- **Phase 4 打磨与规模化**:
  - 性能：Vite 代码分割、Bundle 分析、`React.lazy` 懒加载、`@tanstack/react-virtual` 虚拟滚动
  - 测试：Vitest 单元测试（7/7）+ Playwright E2E（13 passed + 1 skipped on mobile）
  - 可访问性：键盘导航、`aria-label`、`prefers-reduced-motion`
  - 国际化：Namespace 拆分（common / chat / construct）、全页面覆盖 `t()`
  - 文档：前端 README、根 README、UI 组件使用文档、进度记录文档

### 修复浅色主题下按钮颜色异常

**已完成:**
- 修复 `chat-input.tsx` 中左下角 4 个 `type="text"` 按钮在 light 模式下显示为黑色的问题
  - 根因：Ant Design 内部样式优先级高于 Tailwind 的 `text-text-secondary`，导致 light 模式下未正确应用主题色
  - 修复：将按钮 className 从 `text-text-secondary hover:text-text` 改为 `!text-text-secondary hover:!text-text`，强制覆盖 AntD 默认色
- 修复 `app-providers.tsx` 中 `ConfigProvider` 的 theme algorithm 未随主题动态切换的问题
  - 根因：`antd-theme.ts` 中 `algorithm: undefined`，AntD 无法根据 light/dark 正确计算派生颜色
  - 修复：将 `antdTheme` 静态配置改为 `getAntdTheme(mode)` 函数，根据 `global-store` 的 `theme` 值动态传入 `theme.defaultAlgorithm` 或 `theme.darkAlgorithm`
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### 修复构建中心浅色主题黑色背景问题

**已完成:**
- 修复构建中心（Construct）各页面在 light 主题下 Table 表头、Button 等组件显示为纯黑背景的问题
  - 根因：`antd-theme.ts` 的 token 使用了 CSS 变量字符串（如 `var(--color-surface)`），Ant Design 的 `darkAlgorithm` / `defaultAlgorithm` 无法解析 CSS 变量来计算派生颜色，导致生成错误的黑色背景
  - 修复：将 `getAntdTheme` 中的 token 改为直接传入具体颜色值（分别定义 `lightTokens` 和 `darkTokens`），让 AntD 的算法能正确计算所有派生颜色
- 修复 `index.html` 在页面加载初期缺少 `data-theme` 属性导致的 dark flash 问题
  - 根因：Zustand `persist` 的恢复在 `useEffect` 中执行，首次渲染前 `<html>` 没有 `data-theme`，CSS 变量回退到 `:root` 的深色默认值
  - 修复：在 `index.html` 的 `<head>` 中加入内联脚本，在 DOM 解析前读取 `localStorage` 中的持久化主题并预置 `data-theme` 属性，避免闪烁
- 通过 `/browse` 截图验证：Database / Knowledge / Flow 等页面在 light 和 dark 主题下均显示正常
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### 修复本地聊天代理 404 (Not Found) 问题

**已完成:**
- 修复用户反馈的本地聊天返回 `error: not found` 的问题
  - 根因：`vite.config.ts` 中配置的 Vite 代理 `/api` -> `http://127.0.0.1:8000` 默认保留原路径，导致前端请求 `/api/v1/chat/completions` 被代理到后端的 `/api/v1/chat/completions`，而后端实际只监听 `/v1/chat/completions`，因此返回 404
  - 修复：在 `vite.config.ts` 的 proxy 配置中加入 `rewrite: (path) => path.replace(/^\/api/, '')`，去掉 `/api` 前缀，使代理后的路径正确映射到 `http://127.0.0.1:8000/v1/chat/completions`
- 验证：通过 `curl` 直接测试代理路径，已从 `{"detail":"Not Found"}` 变为正常的模型响应（`Model 'test' not found`），证明路径和 API Key 均已正确传递
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### 模型管理与对话模型选择联动增强

**已完成:**
- 重构 `src/stores/models-store.ts`
  - 扩展 `ModelItem` 数据结构，新增 `baseUrl`、`apiKey`、`status`（untested / testing / available / error）、`statusMessage`
  - 使用 `zustand/persist` 持久化到 `localStorage`，刷新不丢失
  - 预置默认本地模型：`gemma-4-e4b-it-8bit`（`http://127.0.0.1:8000/v1`，`apiKey: 123456`）
- 新增 `src/services/model-test.ts`
  - 提供 `testModelConnection(baseUrl, apiKey)` 函数
  - 通过 `GET {baseUrl}/models` 轻量探测模型服务连通性（带 Authorization）
- 重写 `src/features/construct/models/pages/models-page.tsx`
  - 从 List 升级为 Ant Design Table，字段包含：名称、类型、Base URL、状态、操作
  - 新增模型使用 Modal 表单，包含：名称、类型、Base URL、API Key
  - 支持「测试连接」按钮：测试中显示 `Testing...`，通过显示绿色 `Available`，失败显示红色 `Error` 并 tooltip 展示错误信息
  - 支持删除自定义模型
- 更新 `src/services/chat.ts`
  - `chatComplete` 改为接收 `baseUrl` 和 `apiKey`，每个模型独立调用，不再使用全局写死的 `llmClient`
- 更新 `src/features/chat/hooks/use-chat-stream.ts`
  - 发送前根据 `model` 名称去 `models-store` 查找对应配置，只有 `status === 'available'` 的模型才允许调用
- 更新 `src/features/chat/components/model-selector.tsx`
  - 下拉选项动态从 `models-store` 读取 `type === 'llm' && status === 'available'` 的模型
  - 与内置 GPT 模型合并展示，未通过测试的模型不会出现在对话选择器中
- 删除废弃的 `src/lib/llm-client.ts`
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### 修复模型管理页面中英文混杂

**已完成:**
- 清理 `src/features/construct/models/pages/models-page.tsx` 中所有 `t("...") || "English fallback"` 的硬编码英文回退
- 将状态标签（Testing / Available / Error / Untested）、按钮文案、表单校验提示全部改为纯 `t()` 调用
- 补充 `public/locales/zh/construct.json` 的 `models` 命名空间键：
  - `baseUrl`、`apiKey`、`actions`、`test`、`testSuccess`、`testFailed`、`addSuccess`
  - `nameRequired`、`baseUrlRequired`、`apiKeyRequired`、`testing`、`available`、`error`、`untested`
- 同步补充 `public/locales/en/construct.json` 对应英文翻译
- 补充 `public/locales/zh/common.json` 与 `public/locales/en/common.json` 的 `actions.delete` 键
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

### 聊天输入框四个工具按钮真实功能落地

**已完成:**
- 新建 `src/features/chat/hooks/use-chat-tools.ts`
  - 管理文件附件、技能、知识库、数据库四种附件状态
  - 提供 `FileReader` 读取本地文本文件内容
- 更新 `src/features/chat/components/chat-input.tsx`
  - 增加 `attachments` / `onRemoveAttachment` props
  - 在输入框与操作栏之间显示已选附件 Tag（文件/技能/知识库/数据库），支持点击 × 移除
- 重写 `src/features/chat/pages/chat-page.tsx` 与 `src/features/mobile/pages/mobile-chat-page.tsx`
  - 四个按钮从空回调改为真实行为：
    - **从本地文件添加**：触发系统文件选择器，读取文本文件内容作为附件
    - **使用技能**：弹出 Modal，调用 `listSkills` 获取技能列表，选择后作为 system prompt 注入
    - **使用知识库**：弹出 Modal，调用 `listKnowledge` 获取知识库列表；发送消息前自动调用 `queryKnowledge(name, query)` 检索相关内容，并将检索结果注入 system prompt（真正的 RAG）
    - **使用数据库**：弹出 Modal，调用 `listDatasources` 获取数据库列表，选择后作为 system prompt 注入，提示模型根据问题生成 SQL
  - `send` 函数改为 `async`，在发送前根据附件拼装 system message 和用户 message
- 补充翻译键（zh/en `chat.json`）：
  - `selectSkill`、`selectKnowledge`、`selectDatabase`、`knowledgeQueryFailed`
- `npm run build` / `npm test` / `npm run e2e` 全部通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

---

## 重构完成总结

**截至当前，ChatBI 前端 0 到 1 重构的所有计划任务已基本完成：**

- **Phase 0 基础建设**: 目录重构、设计系统（tokens + Tailwind + AntD 主题收敛）、API 分层（Axios + TanStack Query + services）、Zustand 状态管理、基础 UI 组件库
- **Phase 1 核心聊天体验**: Explore 首页、聊天页（消息渲染、模型选择、输入发送）、移动端专属聊天页
- **Phase 2 构建中心模块**: Construct Shell + 8 个子模块全部具备功能性页面（App / Database / Knowledge / Skills / Models / Flow / Prompt / Dbgpts）
- **Phase 3 高级功能**: Flow 可视化画布占位、Evaluation 评测任务/数据集管理、Share 分享页只读渲染
- **Phase 4 打磨与规模化**:
  - 性能：Vite 代码分割、Bundle 分析、`React.lazy` 懒加载、`@tanstack/react-virtual` 虚拟滚动
  - 测试：Vitest 单元测试（7/7）+ Playwright E2E（13 passed + 1 skipped on mobile）
  - 可访问性：键盘导航、`aria-label`、`prefers-reduced-motion`
  - 国际化：Namespace 拆分（common / chat / construct）、全页面覆盖 `t()`
  - 文档：前端 README、根 README、UI 组件使用文档、进度记录文档

**所有构建、测试、E2E 持续绿灯。重构主体工作已完成。**

### 参考 DB-GPT 深度改造文件上传与技能调用

**已完成:**
- **后端 Schema 升级** (`packages/chatbi-serve/src/chatbi_serve/chat/schema.py`)
  - `ChatMessage.content` 扩展为 `Union[str, List[ContentPart]]`
  - 新增 `ContentPart`、`ImageUrlPart`、`FileUrlPart` 模型
  - `ChatRequest` 新增 `model_config`、`select_param`、`ext_info`
- **后端 OpenAILLM 升级** (`packages/chatbi-core/src/chatbi_core/model/adapter/openai_adapter.py`)
  - `achat` / `achat_stream` 支持透传 `List[dict]` 格式的多模态 messages（含 `image_url`）
- **后端 ChatService 重构** (`packages/chatbi-serve/src/chatbi_serve/chat/service.py`)
  - 支持动态模型：如果请求携带 `model_config`，动态创建 `OpenAILLM` 实例；否则回退 `ModelRegistry`
  - 支持技能执行：根据 `select_param` / `ext_info.skill_name` 调用 `SkillRegistry.execute`，并将结果注入 system message
  - 支持 content parts 解析：`image_url` 直接透传，`file_url` 在后端读取文件内容并转为 text part
- **后端新增通用文件上传** (`packages/chatbi-serve/src/chatbi_serve/files/api.py`)
  - `POST /api/v1/files/upload`：保存到 `uploads/` 目录，返回 `{file_name, file_path}`
  - 在 `router.py` 和 `server.py` 中注册路由
- **前端聊天接口中枢化** (`src/services/chat.ts`, `src/features/chat/hooks/use-chat-stream.ts`)
  - `chatComplete` 改为调用 ChatBI 后端 `/api/v1/chat/completions`，携带 `model_config` 让后端代理调用具体模型
- **前端文件上传改造** (`src/services/files.ts`, `src/features/chat/hooks/use-chat-tools.ts`)
  - 图片：前端 `FileReader.readAsDataURL()` 转为 base64，作为 `image_url` content part
  - 其他文件：调用后端 `/api/v1/files/upload`，拿到路径后作为 `file_url` content part
- **前端消息拼装升级** (`src/features/chat/pages/chat-page.tsx`, `src/features/mobile/pages/mobile-chat-page.tsx`)
  - 构造 OpenAI 标准 messages：`user.content` 为 `ContentPart[]` 数组，包含 `image_url` / `file_url` / `text`
  - 技能和数据库信息从 prompt 拼接改为放入 `ChatRequest.select_param` 和 `ext_info`
- **翻译补充** (`public/locales/zh/chat.json`, `en/chat.json`)
  - 新增 `selectSkill`、`selectKnowledge`、`selectDatabase`、`knowledgeQueryFailed`
- `npm run build` / `npm test` / `npm run e2e` 全部通过
- 后端导入检查通过

### 当前构建状态
- `npm run build` 持续通过
- `npm test` 通过 (7/7 tests passed)
- `npm run e2e` 通过 (13 passed, 1 skipped on mobile)
- 所有 `src/features/` 下的组件/页面文件均 < 400 行
- TypeScript 严格模式开启，无 `ignoreBuildErrors`

---

## 重构完成总结

**截至当前，ChatBI 前端 0 到 1 重构的所有计划任务已基本完成：**

- **Phase 0 基础建设**: 目录重构、设计系统（tokens + Tailwind + AntD 主题收敛）、API 分层（Axios + TanStack Query + services）、Zustand 状态管理、基础 UI 组件库
- **Phase 1 核心聊天体验**: Explore 首页、聊天页（消息渲染、模型选择、输入发送）、移动端专属聊天页
- **Phase 2 构建中心模块**: Construct Shell + 8 个子模块全部具备功能性页面（App / Database / Knowledge / Skills / Models / Flow / Prompt / Dbgpts）
- **Phase 3 高级功能**: Flow 可视化画布占位、Evaluation 评测任务/数据集管理、Share 分享页只读渲染
- **Phase 4 打磨与规模化**:
  - 性能：Vite 代码分割、Bundle 分析、`React.lazy` 懒加载、`@tanstack/react-virtual` 虚拟滚动
  - 测试：Vitest 单元测试（7/7）+ Playwright E2E（13 passed + 1 skipped on mobile）
  - 可访问性：键盘导航、`aria-label`、`prefers-reduced-motion`
  - 国际化：Namespace 拆分（common / chat / construct）、全页面覆盖 `t()`
  - 文档：前端 README、根 README、UI 组件使用文档、进度记录文档

**所有构建、测试、E2E 持续绿灯。重构主体工作已完成。**

### Loop 结束声明

- `/loop` 任务已达到完成状态，无需继续迭代。
- 后续如需扩展（如接入真实后端 auth、reactflow 正式集成、axe-core 可访问性扫描），可作为独立新任务规划。

---
