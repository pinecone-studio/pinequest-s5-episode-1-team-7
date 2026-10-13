import { fileURLToPath } from 'node:url'

import type { Page } from '@playwright/test'

export const SLIDE_PHOTO = fileURLToPath(new URL('fixtures/slide.jpg', import.meta.url))

/** Start the page in `lng` (the app defaults to Mongolian). Applies on every navigation of this page. */
export function useLanguage(page: Page, lng: 'en' | 'mn') {
  return page.addInitScript((value) => localStorage.setItem('pathtriage.language', value), lng)
}

/** Slide ids of the rows in the named list, top to bottom. */
export async function rowIds(page: Page, list: string) {
  const hrefs = await page.getByRole('list', { name: list }).getByRole('link').evaluateAll((links) =>
    links.map((a) => a.getAttribute('href')),
  )
  return hrefs.map((href) => Number(href?.split('/').pop()))
}
