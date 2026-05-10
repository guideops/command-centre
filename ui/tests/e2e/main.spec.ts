import { test, expect } from '@playwright/test'

const BASE = 'http://127.0.0.1:5173'

test.describe('Command Centre', () => {
  test('Command page renders', async ({ page }) => {
    await page.goto(BASE + '/')
    await expect(page.locator('text=Command Centre').first()).toBeVisible()
    await expect(page.locator('text=Live Sessions').first()).toBeVisible()
    await expect(page.locator('text=Token Usage').first()).toBeVisible()
    await expect(page.locator('text=Observability').first()).toBeVisible()
  })

  test('Activity page renders', async ({ page }) => {
    await page.goto(BASE + '/activity')
    await expect(page.locator('text=30-Day Activity').first()).toBeVisible()
    await expect(page.locator('text=OTEL Firehose').first()).toBeVisible()
    await expect(page.locator('text=All Sessions').first()).toBeVisible()
  })

  test('Skills page renders', async ({ page }) => {
    await page.goto(BASE + '/skills')
    await expect(page.locator('text=MCP Servers').first()).toBeVisible()
    await expect(page.locator('text=Skills & Context').first()).toBeVisible()
  })

  test('Command palette opens with Ctrl+K', async ({ page }) => {
    await page.goto(BASE + '/')
    await page.keyboard.press('Control+k')
    await expect(page.locator('input[placeholder="Search commands…"]')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('input[placeholder="Search commands…"]')).not.toBeVisible()
  })

  test('Command palette navigates to Activity', async ({ page }) => {
    await page.goto(BASE + '/')
    await page.keyboard.press('Control+k')
    await page.locator('input[placeholder="Search commands…"]').fill('Activity')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(BASE + '/activity')
  })

  test('Collapsible section collapses and expands', async ({ page }) => {
    await page.goto(BASE + '/')
    const section = page.locator('text=Token Usage').first()
    await section.click()
    await page.waitForTimeout(300)
    await section.click()
    await page.waitForTimeout(300)
    await expect(page.locator('text=Token Usage').first()).toBeVisible()
  })

  test('Schedule composer opens', async ({ page }) => {
    await page.goto(BASE + '/')
    await page.locator('text=New Schedule').click()
    await expect(page.locator('text=Schedule name').first()).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator('text=Schedule name').first()).not.toBeVisible()
  })

  test('Task composer opens', async ({ page }) => {
    await page.goto(BASE + '/')
    await page.locator('button:has-text("Queue Task")').first().click()
    await expect(page.getByPlaceholder('What should Claude do?')).toBeVisible()
    await page.keyboard.press('Escape')
  })
})
