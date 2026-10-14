import type { Page } from '@playwright/test'

import { useLanguage } from './helpers.ts'
import { expect, test } from './mockBackend.ts'

const isDark = (page: Page) => page.evaluate(() => document.documentElement.classList.contains('dark'))

test.describe('appearance', () => {
  test('follows the device by default, and a chosen appearance is remembered', async ({ page, backend }) => {
    void backend
    await useLanguage(page, 'en')
    await page.emulateMedia({ colorScheme: 'dark' })
    await page.goto('/')
    await expect(page.getByRole('list', { name: 'Worklist' }).getByRole('link')).toHaveCount(3)
    expect(await isDark(page)).toBe(true)

    await page.getByRole('button', { name: 'Appearance: Same as device' }).click()
    await page.getByRole('menuitemradio', { name: 'Light' }).click()
    expect(await isDark(page)).toBe(false)
    await expect(page.locator('body')).toHaveCSS('background-color', 'oklch(0.984 0.003 247.858)')

    await page.reload()
    expect(await isDark(page)).toBe(false)

    await page.getByRole('button', { name: 'Appearance: Light' }).click()
    await page.getByRole('menuitemradio', { name: 'Dark' }).click()
    await page.emulateMedia({ colorScheme: 'light' })
    expect(await isDark(page)).toBe(true)
  })

  test('the switch is translated into Mongolian', async ({ page, backend }) => {
    void backend
    await page.goto('/calibrate')
    await page.getByRole('button', { name: /Харагдах байдал/ }).click()
    await page.getByRole('menuitemradio', { name: 'Бараан' }).click()
    expect(await isDark(page)).toBe(true)
  })
})
