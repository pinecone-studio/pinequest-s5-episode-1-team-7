import { rowIds, SLIDE_PHOTO, useLanguage } from './helpers.ts'
import { expect, makeSlide, test } from './mockBackend.ts'

test.describe('priority worklist', () => {
  test('orders by AI risk by default and urgent-first when the toggle is off', async ({ page, backend }) => {
    void backend
    await useLanguage(page, 'en')
    await page.goto('/')

    await expect(page.getByRole('list', { name: 'Worklist' }).getByRole('link')).toHaveCount(3)
    expect(await rowIds(page, 'Worklist')).toEqual([1, 2, 3])
    await expect(page.getByRole('link', { name: /Slide #1/ })).toContainText('High risk')
    await expect(page.getByRole('link', { name: /Slide #1/ })).toContainText('91')
    await expect(page.getByRole('link', { name: /Slide #2/ })).toContainText('Urgent')

    const toggle = page.getByRole('switch', { name: 'Sort by AI risk score' })
    await expect(toggle).toHaveAttribute('aria-checked', 'true')
    await toggle.click()
    expect(await rowIds(page, 'Worklist')).toEqual([2, 3, 1])

    await page.reload()
    await expect(page.getByRole('switch', { name: 'Sort by AI risk score' })).toHaveAttribute('aria-checked', 'false')
  })

  test('a manually prioritised slide goes to the top, marked as such', async ({ page, backend }) => {
    backend.get(3).priority_override = 0.25
    await useLanguage(page, 'en')
    await page.goto('/')
    expect(await rowIds(page, 'Worklist')).toEqual([3, 1, 2])
    await expect(page.getByRole('link', { name: /Slide #3/ })).toContainText('Manual priority')
  })

  test('relative times are Mongolian in Chrome (which has no Mongolian Intl data)', async ({ page, backend }) => {
    void backend
    await page.goto('/')
    const row = page.getByRole('link', { name: /Бэлдмэл #1/ })
    await expect(row).toContainText('өдрийн өмнө')
    await expect(row).not.toContainText('ago')
  })

  test('uploads a photo with its clinical request; it shows as processing', async ({ page, backend }) => {
    await useLanguage(page, 'en')
    await page.goto('/')

    await page.getByLabel('Patient ID (optional)').fill('MRN-0042')
    await page.getByRole('radio', { name: 'Urgent' }).click()
    await page.getByRole('complementary').getByLabel('Organ').selectOption('lymph_node')
    await page.locator('input[type=file]').setInputFiles(SLIDE_PHOTO)
    await expect(page.getByRole('img', { name: 'Selected slide photo' })).toBeVisible()
    await page.getByRole('button', { name: 'Submit for AI triage' }).click()

    await expect(page.getByText('Slide #4 added.')).toBeVisible()
    expect(backend.posts).toEqual([{ path: '/ingest', body: { patient_id: 'MRN-0042', indication: 'Urgent', organ: 'lymph_node' } }])
    await expect(page.getByRole('region', { name: 'Processing and failed' }).getByRole('link', { name: /Slide #4/ })).toContainText(
      'AI model running',
    )
    await expect(page.getByLabel('Patient ID (optional)')).toHaveValue('')
  })

  test('slides under review and archived slides have their own tabs', async ({ page, backend }) => {
    backend.slides.push(makeSlide(5, { state: 'under_review' }), makeSlide(6, { state: 'archived', decision: 'mark_benign' }))
    await useLanguage(page, 'en')
    await page.goto('/')
    await page.getByRole('radio', { name: 'Under review (1)' }).click()
    expect(await rowIds(page, 'Slides under review')).toEqual([5])
    await page.getByRole('radio', { name: 'Archived' }).click()
    await expect(page.getByRole('link', { name: /Slide #6/ })).toContainText('Mark benign')
  })
})
