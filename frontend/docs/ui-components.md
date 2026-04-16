# UI 组件使用说明

`src/components/ui/` 下的原子组件基于 **Ant Design 5** 进行轻量封装，统一接入 Design Tokens（通过 Tailwind 语义类名），并支持 `className` 透传。

## 设计原则

- **薄封装**：保留 Ant Design 原组件的绝大多数 API 与行为。
- **样式收敛**：通过 `cn(clsx, tailwind-merge)` 注入统一的背景、边框、圆角、阴影等 token 类名。
- **TypeScript**：所有组件均导出显式的 `Props` 接口。

---

## Button

```tsx
import { Button } from "@/components/ui/button"

<Button type="primary" onClick={() => console.log("clicked")}>
  提交
</Button>
```

- 继承自 `AntButtonProps`
- 默认追加 `shadow-sm transition-colors duration-fast`

---

## Card

```tsx
import { Card } from "@/components/ui/card"

<Card title="标题">
  <p>内容</p>
</Card>
```

- 继承自 `CardProps`
- 默认追加 `bg-surface border-border shadow-md rounded-lg`

---

## Input

```tsx
import { Input } from "@/components/ui/input"

<Input placeholder="请输入" />
```

- 继承自 `AntInputProps`
- 默认追加背景色、边框、聚焦态 ring 样式

---

## Select

```tsx
import { Select } from "@/components/ui/select"

<Select
  options={[
    { value: "a", label: "选项 A" },
    { value: "b", label: "选项 B" },
  ]}
/>
```

- 继承自 `SelectProps`
- 默认最小宽度 `min-w-[8rem]`
- 下拉面板自动应用 `bg-surface-elevated border-border`

---

## Modal

```tsx
import { Modal } from "@/components/ui/modal"

<Modal open={visible} onCancel={() => setVisible(false)} title="提示">
  <p>内容</p>
</Modal>
```

- 继承自 `ModalProps`
- `wrapClassName` 默认追加 `ant-modal-root-custom`

---

## Badge

```tsx
import { Badge } from "@/components/ui/badge"

<Badge count={5} />
```

- 继承自 `BadgeProps`
- 轻量透传，无额外样式覆盖

---

## Empty

```tsx
import { Empty } from "@/components/ui/empty"

<Empty description="暂无数据" />
```

- 继承自 `EmptyProps`
- 默认文字颜色为 `text-text-secondary`
