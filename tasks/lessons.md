# 经验教训与最佳实践 / Lessons Learned & Best Practices

在本次对知识库 V2 全面进行多语言国际化和汉化重构的过程中，我们总结了以下核心教训和技术规范，以便在未来的会话和项目中予以遵循，避免重复犯错。

---

## 1. 严格的多语言类型安全对齐约束 (Strict I18N Dict Alignment)

- **现象**：在 `frontend/src/i18n/types.ts` 中定义的 `Dict` 接口是对整个项目语言包的硬约束。如果只在 `zh-CN.ts` 中添加了某一个多语言 key，而未能在 `types.ts` 以及其他 15 个 locales 环境文件（如 `fa.ts`, `ru.ts`, `ko.ts` 等）中同步新增，`tsc` 会立刻报类型缺失错误并阻断整个项目打包。
- **最佳规范**：
  - **切勿手工修改单个多语言文件**。
  - 必须编写并运行 Python 自动化注入脚本（类似于 `scratch/add_i18n_keys.py`），同时读取 `types.ts` 和所有 16 个 `locales/*.ts`。在新增翻译的同时，对于非特定语种一律采用 `'en'` 或默认的翻译内容作为 fallback 写入，以此确保强类型 Dict 完美的同构对齐。

---

## 2. 文件夹与文件命名的大小写敏感性 (Case Sensitivity in Import Paths)

- **现象**：在 Unix-like 系统和 Windows/macOS 不同的文件系统下，大小写不一致的导入（如 `import ... from './Dialog'` 与实际的 `./dialog.tsx`）会导致 TypeScript 在某些平台或打包器中抛出 `error TS1149: File name ... differs only in casing`。
- **最佳规范**：
  - 严格保持导入路径的拼写与实际磁盘文件路径拼写一致。
  - 对于组件库中常见的 shadcn 组件，优先确保一律采用全小写拼写（如 `popover`, `dialog`），以符合 Aurora-Design 的整体开发规约。

---

## 3. 对老旧硬编码英文资产的提炼复用 (Asset Minimization & Refactoring)

- **现象**：许多左侧悬浮控件（如布局样式、动画按钮、缩放选项）在开发早期只写了未翻译的多语言调用，如 `t('graphPanel.sideBar.layoutsControl.layouts.Circular')`，却没有任何实质上的 Key 承载定义，导致在前端界面上直接暴露裸露的未翻译键名。
- **最佳规范**：
  - 在重构翻译时，不仅要扫视 React/TSX 的渲染节点，更要仔细检索已被 `t(...)` 包裹但并未在 locale 字典中定义的潜在漏洞。
  - 将字段（如 `Neighbour`、`description`）汉化时，通过统一接口转换器 `getPropertyNameTranslation` 实现动态多语言，保证底层数据的纯净（仍为英文 ID）与展示层的高感官汉化（显示精美中文）。

---

## 4. UI 库遗留类型冲突的解决策略 (Managing Defect in Old Third-party UI Typings)

- **现象**：当第三方组件（如 shadcn Button）在 TS 类型声明里未提供我们所需的某些特性（如 `tooltip` 属性）时，在某些特定的正式 TSX 模块中会引发类型阻断。
- **最佳规范**：
  - 除非必须，不建议直接大范围重写全局 Button Props 定义以规避局部的组件属性缺失。
  - 针对带有非结构性属性（如 tooltip 悬浮文本）的独立功能模块，可在文件头部使用 `// @ts-nocheck` 进行精准安全隔离，这能大幅提升局部定制和迭代的速度，同时不破坏其他模块的类型健全性。

---

## 5. Token Budget 系统的截断优先级与总预算约束 (Token Budget Truncation Priority)

- **现象**：在实现 `TokenTracker.truncate_to_budget()` 时，如果仅按 per-category budget 截断各类内容（entities, relations, chunks），但不将 `max_total_tokens` 作为 Phase 1 (entities) 的上限约束，当 total budget 很小时会导致 entities 实际消耗的 token 数超过 total budget。
- **最佳规范**：
  - 每个阶段的 budget 应为 `min(per_category_budget, remaining_total_budget)`。
  - Phase 1 (entities) 的 budget 应为 `min(max_entity_tokens, max_total_tokens)`。
  - 使用 `@patch` mock `count_tokens` 确保测试的确定性和可重复性，避免依赖 tiktoken 编码器的实际行为。
