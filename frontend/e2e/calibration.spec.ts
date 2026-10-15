import { expect } from './mockBackend.ts'
import { test } from './mockBackend.ts'
import { makeSlide } from './mockBackend.ts'
import { SLIDE_PHOTO, useLanguage } from './helpers.ts'
import type { Locator, Page } from '@playwright/test'

/** Click at (x, y) px from the photo's top-left corner, as a user would. */
async function clickPhoto(page: Page, photo: Locator, x: number, y: number) {
  await photo.scrollIntoViewIfNeeded()
  const box = await photo.boundingBox()
  if (!box) throw new Error('micrometer photo is not visible')
  await page.mouse.click(box.x + x, box.y + y)
}

/** µm/px shown on the page, e.g. "This setup sees 0.123 µm per pixel." */
async function shownUmPerPx(page: Page) {
  const text = await page.getByText(/µm per pixel/).textContent()
  return Number(/([\d.]+) µm per pixel/.exec(text ?? '')?.[1])
}

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
  // The photo sits in a zoomable map: clicks land on the map, at these spots over the photo.
  await clickPhoto(page, photo, 100, 100)
  await clickPhoto(page, photo, 150, 100)
  await page.getByLabel(/Distance between the marks/).fill('100')
  await expect(page.getByText(/µm per pixel/)).toBeVisible()

  await page.getByRole('button', { name: 'Save setup' }).click()
  await expect(page.getByText(/saved at .* µm\/px/)).toBeVisible()
  await expect(page.getByText('Lab scope + Redmi 12', { exact: true })).toBeVisible()
  expect(backend.setups).toHaveLength(1)
  expect(backend.setups[0]).toMatchObject({ name: 'Lab scope + Redmi 12', calibration_objective: '40x' })
})

test('zooming in keeps the marks on the same image pixels', async ({ page }) => {
  await useLanguage(page, 'en')
  await page.goto('/calibrate')
  await page.locator('input[type=file]').setInputFiles(SLIDE_PHOTO)
  const photo = page.getByRole('img', { name: 'Micrometer photo' })
  await expect.poll(() => photo.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0)
  await photo.scrollIntoViewIfNeeded()
  const fit = (await photo.boundingBox())!
  const centre = { x: fit.x + fit.width / 2, y: fit.y + fit.height / 2 }

  // Two marks 50 px either side of the centre at fit-to-view...
  await page.mouse.click(centre.x - 50, centre.y)
  await page.mouse.click(centre.x + 50, centre.y)
  await page.getByLabel(/Distance between the marks/).fill('100')
  const atFit = await shownUmPerPx(page)

  // ...then zoom in 2x (zooming keeps the centre in place) and mark the same two pixels,
  // now 100 px either side: the image distance, and so µm/px, must not change.
  // Each click zooms by √2. Leaflet ignores a click while the view is still settling, so
  // click again only if the zoom hasn't changed (never past the target).
  const zoomIn = page.getByRole('button', { name: 'Zoom in' })
  const ratio = async () => (await photo.boundingBox())!.width / fit.width
  for (const factor of [Math.SQRT2, 2]) {
    await expect(async () => {
      if ((await ratio()) < factor - 0.01) {
        await zoomIn.click()
        await page.waitForTimeout(400) // Leaflet's zoom animation is 250 ms
      }
      expect(await ratio()).toBeCloseTo(factor, 2) // Leaflet rounds the photo's size to whole pixels
    }).toPass({ timeout: 10_000 })
  }
  await page.mouse.click(centre.x - 100, centre.y)
  await page.mouse.click(centre.x + 100, centre.y)
  expect(await shownUmPerPx(page)).toBeCloseTo(atFit, 2)

  // A third click starts over with a new A.
  await page.mouse.click(centre.x, centre.y + 40)
  await expect(page.getByText('Click two marks and enter their distance')).toBeVisible()
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
  await page.getByRole('complementary').getByLabel('Organ').selectOption('lymph_node')
  await page.locator('input[type=file]').setInputFiles(SLIDE_PHOTO)
  await page.getByRole('button', { name: 'Submit for AI triage' }).click()
  await expect(page.getByText(/Slide #\d+ added/)).toBeVisible()

  // Multipart fields arrive as strings; the objective defaults to the setup's calibration.
  expect(backend.posts).toEqual([
    { path: '/ingest', body: { indication: 'Routine', setup_id: '1', objective: '40x', organ: 'lymph_node' } },
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
