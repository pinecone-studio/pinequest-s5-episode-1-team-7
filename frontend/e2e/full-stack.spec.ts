import { expect, test } from '@playwright/test'

import { rowIds, SLIDE_PHOTO, useLanguage } from './helpers.ts'

/** The real backend and ONNX engine. Run with `npm run test:e2e:full`. */
test('upload → AI score → review → archive against the real backend', async ({ page }) => {
  test.setTimeout(120_000)
  await useLanguage(page, 'en')
  await page.goto('/')
  await expect(page.getByText('No slides waiting. Add a slide photo to begin.')).toBeVisible()

  await page.getByLabel('Patient ID (optional)').fill('E2E-PATIENT')
  await page.getByRole('radio', { name: 'Urgent' }).click()
  await page.getByRole('complementary').getByLabel('Organ').selectOption('lymph_node')
  await page.locator('input[type=file]').setInputFiles(SLIDE_PHOTO)
  await page.getByRole('button', { name: 'Submit for AI triage' }).click()
  await expect(page.getByText(/Slide #1 added/)).toBeVisible()

  // The engine scores it and the backend queues it.
  const row = page.getByRole('list', { name: 'Worklist' }).getByRole('link', { name: /Slide #1/ })
  await expect(row).toBeVisible({ timeout: 60_000 })
  await expect(row).toContainText(/High risk|Moderate risk|Low risk/)
  await expect(row).toContainText('Urgent')
  expect(await rowIds(page, 'Worklist')).toEqual([1])

  await row.click()
  await expect(page.locator('.leaflet-container img')).toHaveCount(2) // photo + real heatmap
  await page.getByRole('button', { name: 'Start review' }).click()
  await page.getByRole('button', { name: 'Request formal biopsy' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Request formal biopsy' }).click()

  await expect(page).toHaveURL('/')
  await expect(page.getByText('No slides waiting. Add a slide photo to begin.')).toBeVisible()
  await page.getByRole('radio', { name: 'Archived' }).click()
  await expect(page.getByRole('link', { name: /Slide #1/ })).toContainText('Request formal biopsy')
})
