import { test, expect } from '@playwright/test'

test('chat page has input and send button', async ({ page }) => {
  await page.goto('/chat')
  await expect(page.locator('textarea[placeholder]')).toBeVisible()
  await expect(page.getByRole('button', { name: /Send|发送/ })).toBeVisible()
})

test('typing a message and clicking send adds message to list', async ({ page }) => {
  await page.goto('/chat')
  const input = page.locator('textarea[placeholder]')
  await input.fill('Hello ChatBI')
  await page.getByRole('button', { name: /Send|发送/ }).click()
  await expect(page.getByText('Hello ChatBI').first()).toBeVisible()
})
