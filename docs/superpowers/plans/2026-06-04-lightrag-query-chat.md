# LightRAG Query Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Aurora knowledge QueryPanel behave like LightRAG retrieval chat for follow-up questions.

**Architecture:** Keep the backend unchanged because it already accepts `conversation_history` and forwards it into the RAG query engine. Add LightRAG-style frontend history construction in QueryPanel before each request, filtering failed/incomplete assistant messages and sending the last three complete turns.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, NDJSON streaming fetch.

---

### Task 1: QueryPanel Conversation History

**Files:**
- Modify: `frontend/src/features/construct/knowledge/components/QueryPanel.tsx`
- Test: `frontend/src/features/construct/knowledge/components/QueryPanel.test.tsx`

- [ ] **Step 1: Write failing test**

Add a test that sends two streamed queries. The second request body must include:

```json
{
  "conversation_history": [
    { "role": "user", "content": "第一问" },
    { "role": "assistant", "content": "第一答" }
  ]
}
```

- [ ] **Step 2: Verify red**

Run:

```bash
pnpm --dir frontend test QueryPanel.test.tsx --run
```

Expected: FAIL because `conversation_history` is currently missing.

- [ ] **Step 3: Implement LightRAG-style history builder**

In `QueryPanel.tsx`, add a helper that:

- Takes previous messages only, before the newly submitted user message.
- Filters `isError`, `isStreaming`, and empty content.
- Keeps only `user` and `assistant` messages.
- Slices the last 3 turns (`6` messages).
- Maps to `{ role, content }`.

Use that history in streamed query requests and structured data requests.

- [ ] **Step 4: Verify green**

Run:

```bash
pnpm --dir frontend test QueryPanel.test.tsx --run
```

Expected: PASS.

- [ ] **Step 5: Broader check**

Run:

```bash
pnpm --dir frontend test --run
```

Expected: PASS or report unrelated existing failures separately.
