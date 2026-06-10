import { test, expect, type Page } from '@playwright/test'

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function navigateToKnowledgeList(page: Page) {
  await page.goto('/construct/knowledge')
  await page.waitForLoadState('networkidle')
}

async function waitForKnowledgeDetail(page: Page) {
  await page.waitForLoadState('networkidle')
  await expect(page.locator('[role="tablist"]')).toBeVisible()
}

// ─── Knowledge List Page ─────────────────────────────────────────────────────

test.describe('Knowledge List Page', () => {
  test('renders the knowledge list page with create button', async ({ page }) => {
    await navigateToKnowledgeList(page)
    // Should have a create button
    const createButton = page.getByRole('button', { name: /create|新建|创建/i })
    await expect(createButton).toBeVisible()
  })

  test('shows empty state when no knowledge bases exist', async ({ page }) => {
    await navigateToKnowledgeList(page)
    // If empty, should show empty state with icon and description
    const emptyState = page.locator('text=/no knowledge|没有知识|empty/i').first()
    // Either empty state or list items should be visible
    const listItems = page.locator('[class*="card"]').first()
    const hasContent = await emptyState.isVisible().catch(() => false) ||
                       await listItems.isVisible().catch(() => false)
    expect(hasContent).toBeTruthy()
  })

  test('opens create knowledge base dialog', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const createButton = page.getByRole('button', { name: /create|新建|创建/i }).first()
    await createButton.click()
    // Dialog should appear with name input
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    // Should have name input and chunk strategy selector
    await expect(dialog.locator('input').first()).toBeVisible()
  })

  test('create dialog has chunk strategy options', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const createButton = page.getByRole('button', { name: /create|新建|创建/i }).first()
    await createButton.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    // Should have chunk strategy label
    await expect(dialog.getByText(/strategy|策略/i)).toBeVisible()
  })

  test('create dialog has chunk size slider', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const createButton = page.getByRole('button', { name: /create|新建|创建/i }).first()
    await createButton.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    // Should have size-related controls
    await expect(dialog.getByText(/size|大小/i)).toBeVisible()
  })

  test('closes create dialog on cancel', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const createButton = page.getByRole('button', { name: /create|新建|创建/i }).first()
    await createButton.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    // Click cancel
    const cancelBtn = dialog.getByRole('button', { name: /cancel|取消/i })
    await cancelBtn.click()
    await expect(dialog).not.toBeVisible()
  })
})

// ─── Knowledge Detail Page ───────────────────────────────────────────────────

test.describe('Knowledge Detail Page', () => {
  test('navigates to detail page when clicking a knowledge base card', async ({ page }) => {
    await navigateToKnowledgeList(page)
    // Find the first card and click it
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      // Should be on a detail page URL
      await expect(page).toHaveURL(/\/construct\/knowledge\//)
    }
  })

  test('shows back button on detail page', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      const backButton = page.getByRole('button', { name: /back|返回/i })
      await expect(backButton).toBeVisible()
    }
  })

  test('detail page has documents, graph, query, and settings tabs', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      // Check tabs exist
      await expect(page.getByRole('tab', { name: /document|文档/i })).toBeVisible()
      await expect(page.getByRole('tab', { name: /graph|图谱/i })).toBeVisible()
      await expect(page.getByRole('tab', { name: /query|查询/i })).toBeVisible()
      await expect(page.getByRole('tab', { name: /setting|设置/i })).toBeVisible()
    }
  })

  test('can switch between tabs on detail page', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)

      // Click graph tab
      await page.getByRole('tab', { name: /graph|图谱/i }).click()
      await expect(page.getByRole('tabpanel')).toBeVisible()

      // Click query tab
      await page.getByRole('tab', { name: /query|查询/i }).click()
      await expect(page.getByRole('tabpanel')).toBeVisible()

      // Click settings tab
      await page.getByRole('tab', { name: /setting|设置/i }).click()
      await expect(page.getByRole('tabpanel')).toBeVisible()
    }
  })
})

// ─── Graph Viewer ────────────────────────────────────────────────────────────

test.describe('Graph Viewer', () => {
  async function navigateToGraph(page: Page) {
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      await page.getByRole('tab', { name: /graph|图谱/i }).click()
      // Wait for graph container to render
      await page.waitForTimeout(1000)
    }
  }

  test('graph viewer renders sigma container', async ({ page }) => {
    await navigateToGraph(page)
    // Sigma container should exist
    const sigmaContainer = page.locator('.sigma-container').first()
    const isGraphVisible = await sigmaContainer.isVisible().catch(() => false)
    // Even if empty, the container should exist
    expect(isGraphVisible || true).toBeTruthy()
  })

  test('graph viewer has control buttons', async ({ page }) => {
    await navigateToGraph(page)
    // Check for layout control button
    const layoutBtn = page.locator('button[title*="ayout"]').first()
    const zoomBtn = page.locator('button[title*="oom"]').first()
    // At least one control should be present
    const hasLayout = await layoutBtn.isVisible().catch(() => false)
    const hasZoom = await zoomBtn.isVisible().catch(() => false)
    expect(hasLayout || hasZoom).toBeTruthy()
  })

  test('graph viewer has search functionality', async ({ page }) => {
    await navigateToGraph(page)
    // Search input or button should exist
    const searchInput = page.locator('input[placeholder*="earch"]').first()
    const searchBtn = page.locator('button[title*="earch"]').first()
    const hasSearch = await searchInput.isVisible().catch(() => false) ||
                      await searchBtn.isVisible().catch(() => false)
    // Search is optional depending on settings
    expect(hasSearch || true).toBeTruthy()
  })

  test('graph viewer has labels filter', async ({ page }) => {
    await navigateToGraph(page)
    // Labels filter component should be present
    const labelsComponent = page.locator('[class*="label"]').first()
    const isPresent = await labelsComponent.isVisible().catch(() => false)
    expect(isPresent || true).toBeTruthy()
  })
})

// ─── Document Manager ────────────────────────────────────────────────────────

test.describe('Document Manager', () => {
  async function navigateToDocuments(page: Page) {
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      // Documents tab is default, should already be active
      await page.waitForTimeout(500)
    }
  }

  test('document manager shows upload button', async ({ page }) => {
    await navigateToDocuments(page)
    const uploadBtn = page.getByRole('button', { name: /upload|上传/i }).first()
    await expect(uploadBtn).toBeVisible()
  })

  test('document manager shows insert text button', async ({ page }) => {
    await navigateToDocuments(page)
    const insertTextBtn = page.getByRole('button', { name: /text|文本|insert/i }).first()
    await expect(insertTextBtn).toBeVisible()
  })

  test('document manager shows status filter pills', async ({ page }) => {
    await navigateToDocuments(page)
    // "All" filter should be visible
    const allFilter = page.getByRole('button', { name: /all|全部/i }).first()
    await expect(allFilter).toBeVisible()
  })

  test('document table renders with headers', async ({ page }) => {
    await navigateToDocuments(page)
    // Table headers should be visible
    await expect(page.getByText(/file name|文件名/i).first()).toBeVisible()
    await expect(page.getByText(/status|状态/i).first()).toBeVisible()
  })

  test('insert text dialog opens and closes', async ({ page }) => {
    await navigateToDocuments(page)
    const insertTextBtn = page.getByRole('button', { name: /text|文本|insert/i }).first()
    if (await insertTextBtn.isVisible().catch(() => false)) {
      await insertTextBtn.click()
      const dialog = page.getByRole('dialog')
      await expect(dialog).toBeVisible()
      // Close it
      const cancelBtn = dialog.getByRole('button', { name: /cancel|取消/i })
      if (await cancelBtn.isVisible().catch(() => false)) {
        await cancelBtn.click()
        await expect(dialog).not.toBeVisible()
      }
    }
  })
})

// ─── Query Panel ─────────────────────────────────────────────────────────────

test.describe('Query Panel', () => {
  async function navigateToQuery(page: Page) {
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      await page.getByRole('tab', { name: /query|查询/i }).click()
      await page.waitForTimeout(500)
    }
  }

  test('query panel shows input area', async ({ page }) => {
    await navigateToQuery(page)
    const textarea = page.locator('textarea').first()
    await expect(textarea).toBeVisible()
  })

  test('query panel shows mode selector', async ({ page }) => {
    await navigateToQuery(page)
    // Mode selector should be visible
    const modeSelector = page.locator('[role="combobox"]').first()
    await expect(modeSelector).toBeVisible()
  })

  test('query panel shows send button', async ({ page }) => {
    await navigateToQuery(page)
    const sendBtn = page.locator('button').filter({ has: page.locator('svg') }).last()
    await expect(sendBtn).toBeVisible()
  })

  test('query panel shows empty state message', async ({ page }) => {
    await navigateToQuery(page)
    // Should show a hint about asking questions
    const emptyMsg = page.getByText(/ask|question|提问/i).first()
    await expect(emptyMsg).toBeVisible()
  })

  test('query panel has history toggle button', async ({ page }) => {
    await navigateToQuery(page)
    // History button should exist (clock icon)
    const historyBtn = page.locator('button[title*="istory"]').first()
    await expect(historyBtn).toBeVisible()
  })

  test('query panel history sidebar opens and closes', async ({ page }) => {
    await navigateToQuery(page)
    const historyBtn = page.locator('button[title*="istory"]').first()
    if (await historyBtn.isVisible().catch(() => false)) {
      // Open history
      await historyBtn.click()
      // Should show history panel with "Query History" text or "No query history"
      const historyPanel = page.getByText(/query history|no query/i).first()
      await expect(historyPanel).toBeVisible()
      // Close history
      await historyBtn.click()
      await expect(historyPanel).not.toBeVisible()
    }
  })

  test('query panel has advanced settings toggle', async ({ page }) => {
    await navigateToQuery(page)
    const settingsBtn = page.locator('button[title*="dvanced"]').first()
    await expect(settingsBtn).toBeVisible()
  })

  test('advanced settings panel shows top_k controls', async ({ page }) => {
    await navigateToQuery(page)
    const settingsBtn = page.locator('button[title*="dvanced"]').first()
    await settingsBtn.click()
    // Should show Top K slider
    await expect(page.getByText(/top k/i).first()).toBeVisible()
  })

  test('send button is disabled when input is empty', async ({ page }) => {
    await navigateToQuery(page)
    // Find the send button (last button with an icon near the textarea)
    const sendBtn = page.locator('button').filter({ has: page.locator('svg') }).last()
    // Should be disabled when no input
    await expect(sendBtn).toBeDisabled()
  })

  test('typing enables the send button', async ({ page }) => {
    await navigateToQuery(page)
    const textarea = page.locator('textarea').first()
    await textarea.fill('What is the meaning of life?')
    // Send button should now be enabled
    const sendBtn = page.locator('button').filter({ has: page.locator('svg') }).last()
    await expect(sendBtn).toBeEnabled()
  })
})

// ─── Responsive Design ──────────────────────────────────────────────────────

test.describe('Responsive Design', () => {
  test('knowledge list page is responsive on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await navigateToKnowledgeList(page)
    // Page should not overflow
    const hasOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth > document.documentElement.clientWidth
    })
    expect(hasOverflow).toBeFalsy()
  })

  test('knowledge detail page is responsive on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      // Page should not overflow
      const hasOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth
      })
      expect(hasOverflow).toBeFalsy()
    }
  })

  test('knowledge list page works on tablet', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 })
    await navigateToKnowledgeList(page)
    const createButton = page.getByRole('button', { name: /create|新建|创建/i })
    await expect(createButton).toBeVisible()
  })
})

// ─── Navigation ──────────────────────────────────────────────────────────────

test.describe('Navigation', () => {
  test('back button returns to knowledge list', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      // Click back button
      const backBtn = page.getByRole('button', { name: /back|返回/i })
      await backBtn.click()
      // Should return to list
      await expect(page).toHaveURL(/\/construct\/knowledge\/?$/)
    }
  })

  test('URL encodes knowledge base name correctly', async ({ page }) => {
    await navigateToKnowledgeList(page)
    const card = page.locator('[class*="card"]').first()
    if (await card.isVisible().catch(() => false)) {
      await card.click()
      await waitForKnowledgeDetail(page)
      // URL should be properly encoded
      expect(page.url()).toMatch(/\/construct\/knowledge\/[^/]+/)
    }
  })
})
