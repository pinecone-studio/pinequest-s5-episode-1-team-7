import { expect } from './mockBackend.ts'
import { makeSlide, test } from './mockBackend.ts'
import { useLanguage } from './helpers.ts'

test('about page shows the model card sections', async ({ page, backend }) => {
  await useLanguage(page, 'en')
  await page.goto('/about')

  await expect(page.getByRole('heading', { name: 'About the AI' })).toBeVisible()
  await expect(page.getByText('PCam MobileNetV3-Small, Hibou-B-distilled')).toBeVisible()
  // Identity, runtime, patch + slide metrics, PLISM, comparison, limitations.
  for (const heading of [
    'Model identity',
    'Where it runs',
    'Patch test results',
    'Slide triage results',
    'Smartphone robustness (PLISM)',
    'Compared models',
    'Limitations and intended use',
  ]) {
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  }
  await expect(page.getByText('0.9687').first()).toBeVisible()
  await expect(page.getByText('CPUExecutionProvider')).toBeVisible()
  await expect(page.getByText('Direct model')).toBeVisible()
  await expect(page.getByText('Prioritisation aid only.')).toBeVisible()
  expect(backend.posts).toEqual([]) // the About page only GETs
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
  await expect(page.getByText('Загварын танилцуулга')).toBeVisible()
  expect(backend.posts).toEqual([]) // the About page only GETs
})
