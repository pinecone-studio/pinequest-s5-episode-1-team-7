import { expect } from './mockBackend.ts'
import { test } from './mockBackend.ts'
import { makeSlide } from './mockBackend.ts'
import { SLIDE_PHOTO, useLanguage } from './helpers.ts'

test('calibrates a setup from a micrometer photo', async ({ page, backend }) => {
  await useLanguage(page, 'en')
  await page.goto('/calibrate')
  await expect(page.getByRole('heading', { name: 'Microscope calibration' })).toBeVisible()
  await expect(page.getByText('No calibrated setup yet.')).toBeVisible()

  await page.getByLabel('Setup name').fill('Lab scope + Redmi 12')
  await page.locator('input[type=file]').setInputFiles(SLIDE_PHOTO)
  const photo = page.getByRole('img', { name: 'Micrometer photo' })
  await expect(photo).toBeVisible()
  await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  await photo.click({ position: { x: 10, y: 10 } })
  await photo.click({ position: { x: 60, y: 10 } })
  await page.getByLabel(/Distance between the marks/).fill('100')
  await expect(page.getByText(/µm per pixel/)).toBeVisible()

  await page.getByRole('button', { name: 'Save setup' }).click()
  await expect(page.getByText(/saved at .* µm\/px/)).toBeVisible()
  await expect(page.getByText('Lab scope + Redmi 12', { exact: true })).toBeVisible()
  expect(backend.setups).toHaveLength(1)
  expect(backend.setups[0]).toMatchObject({ name: 'Lab scope + Redmi 12', calibration_objective: '40x' })
})

test('uploads with the calibrated setup and objective', async ({ page, backend }) => {
  backend.setups.push({
    id: 1,
    name: 'Scope A',
    um_per_px: 0.5,
    calibration_objective: '40x',
    phone_resolution: null,
    created_at: '2026-10-09T08:00:00.000Z',
  })
  await useLanguage(page, 'en')
  await page.goto('/')

  await page.getByLabel('Microscope setup').selectOption({ label: 'Scope A' })
  await page.locator('input[type=file]').setInputFiles(SLIDE_PHOTO)
  await page.getByRole('button', { name: 'Submit for AI triage' }).click()
  await expect(page.getByText(/Slide #\d+ added/)).toBeVisible()

  // Multipart fields arrive as strings; the objective defaults to the setup's calibration.
  expect(backend.posts).toEqual([
    { path: '/ingest', body: { indication: 'Routine', setup_id: '1', objective: '40x' } },
  ])
  const slide = backend.slides.at(-1)!
  expect(slide.setup_id).toBe(1)
  expect(slide.objective).toBe('40x')
  expect(slide.um_per_px).toBeCloseTo(0.5)
})

test('slide page warns without calibration and shows the scale when calibrated', async ({ page, backend }) => {
  backend.slides.push(
    makeSlide(11, { risk_score: 0.91, risk_flag: 'red' }),
    makeSlide(12, { risk_score: 0.9, risk_flag: 'red', setup_id: 1, objective: '40x', um_per_px: 0.5 }),
    makeSlide(13, { risk_score: 0.9, risk_flag: 'red', scale_warning: 'no_scale_info' }),
  )
  await useLanguage(page, 'en')

  await page.goto('/slides/11')
  await expect(page.getByText('No microscope setup was picked')).toBeVisible()

  await page.goto('/slides/12')
  await expect(page.getByText('0.50 µm/px (40x)')).toBeVisible()

  await page.goto('/slides/13')
  await expect(page.getByText('Scale note from the AI engine: no_scale_info')).toBeVisible()
})
