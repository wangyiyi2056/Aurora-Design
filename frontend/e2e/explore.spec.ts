import { test, expect } from '@playwright/test'

test('explore page loads with title', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('h1')).toContainText('ChatBI')
  await expect(page.getByRole('button', { name: /New Chat|新对话/ })).toBeVisible()
})

test('navigate from explore to chat', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /New Chat|新对话/ }).click()
  await expect(page).toHaveURL(/\/chat/)
  await expect(page.locator('h2')).toContainText(/Chat|聊天/)
})

test('navigate to construct database', async ({ page }) => {
  const size = page.viewportSize()
  test.skip(size !== null && size.width < 768, 'Sidebar hidden on mobile')
  await page.goto('/')
  await page.getByRole('link', { name: /Construct|构建/ }).click()
  await expect(page).toHaveURL(/\/construct/)
  await expect(page.getByRole('tab', { name: /Database|数据源/ })).toBeVisible()
})
