import { test, expect } from '@playwright/test'

test('construct shell shows tabs', async ({ page }) => {
  await page.goto('/construct/database')
  await expect(page.getByRole('tab', { name: /App|应用/ })).toBeVisible()
  await expect(page.getByRole('tab', { name: /Database|数据源/ })).toBeVisible()
  await expect(page.getByRole('tab', { name: /Knowledge|知识库/ })).toBeVisible()
})

test('switching construct tabs changes url', async ({ page }) => {
  await page.goto('/construct/app')
  await page.getByRole('tab', { name: /Knowledge|知识库/ }).click()
  await expect(page).toHaveURL(/\/construct\/knowledge/)
})
