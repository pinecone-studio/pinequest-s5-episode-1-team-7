import { expect } from './mockBackend.ts'
import { makeSlide, test } from './mockBackend.ts'
import { useLanguage } from './helpers.ts'

test('about page shows the essentials and a model comparison', async ({ page, backend }) => {
  await useLanguage(page, 'en')
  await page.goto('/about')

  await expect(page.getByRole('heading', { name: 'About the AI' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'This model' })).toBeVisible()
  await expect(page.getByText('PCam MobileNetV3-Small, Hibou-B-distilled')).toBeVisible()
  await expect(page.getByText('PatchCamelyon (PCam)')).toBeVisible()
  await expect(page.getByText('On this computer, offline.', { exact: false })).toBeVisible()
  await expect(page.getByText('6.42 MB').first()).toBeVisible()
  await expect(page.getByText('≈0.1 s per slide')).toBeVisible()
  await expect(page.getByText('AUC 0.969 on PCam test')).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Compared with other models' })).toBeVisible()
  const rows = page.getByRole('row')
  await expect(rows.filter({ hasText: 'Hibou-B teacher' })).toContainText('343 MB')
  await expect(rows.filter({ hasText: 'Hibou-B teacher' })).toContainText('No')
  await expect(rows.filter({ hasText: 'Published DenseNet' })).toContainText('0.955')
  await expect(page.getByRole('link', { name: 'Veeling et al. 2018' })).toHaveAttribute('href', 'https://arxiv.org/abs/1806.03962')

  // Detail stays available but collapsed.
  await expect(page.getByText('Prioritisation aid only.')).toBeHidden()
  await page.getByText('Technical details').click()
  await expect(page.getByText('Prioritisation aid only.')).toBeVisible()
  expect(backend.posts).toEqual([]) // the About page only GETs
})

test('header has no calibration link; calibration is reached from the upload panel', async ({ page }) => {
  await useLanguage(page, 'en')
  await page.goto('/')
  await expect(page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Calibration' })).toHaveCount(0)
  await expect(page.locator('a[href="/calibrate"]').first()).toBeVisible()
})

test('slide viewer labels the model version that scored it', async ({ page, backend }) => {
  backend.slides.push(
    makeSlide(21, { risk_score: 0.91, risk_flag: 'red', model_name: 'model_fp32.onnx', model_sha256: 'abc123def456' }),
  )
  await useLanguage(page, 'en')
  await page.goto('/slides/21')
  await expect(page.getByText('AI model model_fp32.onnx · abc123def456')).toBeVisible()
})

test('about page header link works in Mongolian', async ({ page, backend }) => {
  await useLanguage(page, 'mn')
  await page.goto('/')
  await page.getByRole('link', { name: 'Хиймэл оюуны тухай' }).click()
  await expect(page.getByRole('heading', { name: 'Хиймэл оюуны тухай' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Энэ загвар' })).toBeVisible()
  expect(backend.posts).toEqual([]) // the About page only GETs
})
