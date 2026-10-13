import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import type { Page } from '@playwright/test'

import { expect, test } from './mockBackend.ts'

const LOCALES = fileURLToPath(new URL('../src/i18n/locales/', import.meta.url))

function strings(lng: string): string[] {
  const out: string[] = []
  const walk = (v: unknown) => {
    if (typeof v === 'string') out.push(v)
    else if (Array.isArray(v)) v.forEach(walk)
    else if (v && typeof v === 'object') Object.values(v).forEach(walk)
  }
  for (const file of readdirSync(`${LOCALES}${lng}`)) walk(JSON.parse(readFileSync(`${LOCALES}${lng}/${file}`, 'utf8')))
  return out
}

/** English UI phrases (2+ words, split at {{variables}} and <tags>) that never appear in Mongolian text. */
const mongolian = strings('mn').join('\n')
const englishPhrases = [
  ...new Set(
    strings('en')
      .flatMap((s) => s.split(/{{[^}]+}}|<\/?\w+>/))
      .map((s) => s.trim().replace(/[.:,]$/, ''))
      .filter((s) => s.split(/\s+/).length >= 2 && s.length >= 8 && !mongolian.includes(s)),
  ),
]

async function leftoverEnglish(page: Page) {
  const text = await page.locator('body').innerText()
  return englishPhrases.filter((phrase) => text.includes(phrase))
}

test.describe('languages', () => {
  test('opens in Mongolian and remembers a switch to English', async ({ page, backend }) => {
    void backend
    await page.goto('/')
    await expect(page.locator('html')).toHaveAttribute('lang', 'mn')
    await expect(page.getByRole('heading', { name: 'Эрэмбэлсэн ажлын жагсаалт' })).toBeVisible()
    await expect(page).toHaveTitle('Эрэмбэлсэн ажлын жагсаалт · PathTriage')

    await page.getByRole('radio', { name: 'EN' }).click()
    await expect(page.getByRole('heading', { name: 'Priority worklist' })).toBeVisible()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    await page.reload()
    await expect(page.getByRole('heading', { name: 'Priority worklist' })).toBeVisible()
  })

  for (const route of ['/', '/slides/1']) {
    test(`no English is left on ${route} in Mongolian`, async ({ page, backend }) => {
      void backend
      await page.goto(route)
      await expect(page.getByText('Эрэмбэлэх туслах хэрэгсэл, оношлох систем биш.')).toBeVisible()
      await page.waitForLoadState('networkidle')
      if (route !== '/') await page.getByText(/Түүх/).click() // open the history so it is checked too
      expect(await leftoverEnglish(page)).toEqual([])
    })
  }

  test('the review dialog is translated', async ({ page, backend }) => {
    backend.get(1).state = 'under_review'
    await page.goto('/slides/1')
    await page.getByRole('button', { name: 'Хоргүй гэж тэмдэглэх' }).click()
    const dialog = page.getByRole('dialog', { name: 'Энэ бэлдмэлийг хоргүй гэж тэмдэглэх үү?' })
    await expect(dialog.getByRole('button', { name: 'Цуцлах' })).toBeVisible()
    expect(await leftoverEnglish(page)).toEqual([])
  })
})
