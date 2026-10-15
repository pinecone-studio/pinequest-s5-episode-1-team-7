import type { Page } from '@playwright/test'

import { expect } from './mockBackend.ts'
import { makeSlide, test } from './mockBackend.ts'
import { rowIds, SLIDE_PHOTO, useLanguage } from './helpers.ts'

const uploadOrgan = (page: Page) => page.getByRole('complementary').getByLabel('Organ')

test('upload requires an organ; the wrong model never scores silently', async ({ page, backend }) => {
  await useLanguage(page, 'en')
  await page.goto('/')

  await page.locator('input[type=file]').setInputFiles(SLIDE_PHOTO)
  const submit = page.getByRole('button', { name: 'Submit for AI triage' })
  await expect(submit).toBeDisabled()
  await uploadOrgan(page).selectOption('colon')
  await expect(submit).toBeEnabled()
  await submit.click()

  await expect(page.getByText(/Slide #\d+ added/)).toBeVisible()
  expect(backend.posts).toEqual([{ path: '/ingest', body: { indication: 'Routine', organ: 'colon' } }])
  expect(backend.slides.at(-1)).toMatchObject({ organ: 'colon' })
})

test('worklist shows and filters by organ', async ({ page, backend }) => {
  backend.slides.push(makeSlide(5, { risk_score: 0.95, risk_flag: 'red', organ: 'colon' }))
  await useLanguage(page, 'en')
  await page.goto('/')

  // Rows name the organ; slides from before organs existed read as lymph node.
  await expect(page.getByRole('link', { name: /Slide #1/ })).toContainText('Lymph node')
  await expect(page.getByRole('link', { name: /Slide #5/ })).toContainText('Colon')

  const filter = page.locator('section[aria-labelledby="worklist-title"]').getByLabel('Organ')
  await filter.selectOption('colon')
  expect(await rowIds(page, 'Worklist')).toEqual([5])
  await filter.selectOption('lymph_node')
  expect(await rowIds(page, 'Worklist')).toEqual([1, 2, 3])
  await filter.selectOption('')
  expect(await rowIds(page, 'Worklist')).toEqual([5, 1, 2, 3])
})

test('slide page shows the organ', async ({ page, backend }) => {
  backend.slides.push(makeSlide(6, { risk_score: 0.8, risk_flag: 'red', organ: 'colon' }))
  await useLanguage(page, 'en')
  await page.goto('/slides/6')
  await expect(page.getByText('Colon').first()).toBeVisible()
})

test('about page shows each organ model card', async ({ page, backend }) => {
  await useLanguage(page, 'en')
  await page.goto('/about')
  await expect(page.getByText('PCam MobileNetV3-Small, Hibou-B-distilled')).toBeVisible()

  await page.getByLabel('Organ model').selectOption('colon')
  await expect(page.getByText('CRC MobileNetV3-Small, Hibou-B-distilled')).toBeVisible()

  await page.getByLabel('Organ model').selectOption('lymph_node')
  await expect(page.getByText('PCam MobileNetV3-Small, Hibou-B-distilled')).toBeVisible()
  expect(backend.posts).toEqual([]) // the About page only GETs
})
