import type { Page } from '@playwright/test'

import { expect, test } from './mockBackend.ts'

test.use({ viewport: { width: 390, height: 844 } })

/** Elements that scroll sideways (the page itself or any scroll container), ignoring the slide map. */
const horizontalOverflow = (page: Page) =>
  page.evaluate(() =>
    [document.documentElement, ...document.querySelectorAll<HTMLElement>('body *')]
      .filter((el) => !el.closest('.leaflet-container'))
      .filter((el) => el === document.documentElement || /auto|scroll/.test(getComputedStyle(el).overflowX))
      .filter((el) => el.scrollWidth > el.clientWidth + 1)
      .map((el) => `${el.tagName.toLowerCase()}.${el.className}`.slice(0, 80)),
  )

for (const route of ['/', '/slides/1']) {
  test(`fits a 390px phone screen in Mongolian: ${route}`, async ({ page, backend }) => {
    void backend
    await page.goto(route)
    await expect(page.getByText('Эрэмбэлэх туслах хэрэгсэл, оношлох систем биш.')).toBeVisible()
    await page.waitForLoadState('networkidle')
    expect(await horizontalOverflow(page)).toEqual([])

    const switcher = await page.getByRole('radiogroup', { name: 'Хэл' }).boundingBox()
    expect(switcher && switcher.x + switcher.width).toBeLessThanOrEqual(390)
  })
}
