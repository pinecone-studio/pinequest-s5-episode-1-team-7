import { rowIds, useLanguage } from './helpers.ts'
import { expect, test } from './mockBackend.ts'

test.beforeEach(async ({ page }) => {
  await useLanguage(page, 'en')
})

test.describe('slide page', () => {
  test('shows the photo with a 0–100% heatmap overlay and the AI score', async ({ page, backend }) => {
    void backend
    await page.goto('/slides/1')
    await expect(page.getByRole('heading', { name: 'Slide #1' })).toBeVisible()
    await expect(page.locator('.leaflet-container img')).toHaveCount(2) // photo + heatmap
    await expect(page.getByText('AI risk score')).toBeVisible()
    await expect(page.getByText('91/100')).toBeVisible()

    const opacity = page.getByLabel('Heatmap opacity')
    await opacity.fill('1')
    await expect(page.getByText('100%', { exact: true })).toBeVisible()
    await opacity.fill('0')
    await expect(page.getByText('0%', { exact: true })).toBeVisible()
    await page.getByRole('radio', { name: 'Photo only' }).click()
    await expect(page.locator('.leaflet-container img')).toHaveCount(1)
  })

  test('start review, then confirm malignancy archives the slide', async ({ page, backend }) => {
    await page.goto('/slides/1')
    await page.getByRole('button', { name: 'Start review' }).click()
    await expect(page.getByText('Under review').first()).toBeVisible()

    await page.getByRole('button', { name: 'Confirm malignancy' }).click()
    const dialog = page.getByRole('dialog', { name: 'Confirm malignancy?' })
    await expect(dialog).toContainText('Slide #1')
    await dialog.getByRole('button', { name: 'Confirm malignancy' }).click()

    await expect(page).toHaveURL('/')
    expect(backend.posts).toEqual([
      { path: '/slides/1/open', body: {} },
      { path: '/slides/1/action', body: { action: 'confirm_malignancy' } },
    ])
    expect(backend.get(1)).toMatchObject({ state: 'archived', decision: 'confirm_malignancy' })
    await expect(page.getByRole('link', { name: /Slide #1/ })).toHaveCount(0)
  })

  test('cancelling the dialog keeps the slide under review', async ({ page, backend }) => {
    backend.get(1).state = 'under_review'
    await page.goto('/slides/1')
    await page.getByRole('button', { name: 'Request formal biopsy' }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    expect(backend.posts).toEqual([])
  })

  test('re-assigning priority from review sends the slide back to the top of the worklist', async ({ page, backend }) => {
    backend.get(3).state = 'under_review'
    await page.goto('/slides/3')
    await page.getByRole('button', { name: 'Re-assign priority' }).click()
    await page.getByRole('menuitemradio', { name: /^High\s*75$/ }).click()
    await expect(page.getByText('Manual priority: High')).toBeVisible()
    expect(backend.posts).toEqual([{ path: '/slides/3/action', body: { action: 'reassign_priority', priority: 0.75 } }])

    await page.getByRole('link', { name: 'Worklist' }).click()
    expect(await rowIds(page, 'Worklist')).toEqual([3, 1, 2])
  })

  test('a failed slide can be retried', async ({ page, backend }) => {
    Object.assign(backend.get(2), { state: 'failed', error: 'interrupted by restart', risk_score: null, risk_flag: null })
    await page.goto('/slides/2')
    await expect(page.getByText('Analysis failed')).toBeVisible()
    await page.getByRole('button', { name: 'Retry analysis' }).click()
    await expect.poll(() => backend.posts).toEqual([{ path: '/slides/2/retry', body: {} }])
  })

  test('an unknown slide says so', async ({ page, backend }) => {
    void backend
    await page.goto('/slides/999')
    await expect(page.getByText("This slide doesn't exist.")).toBeVisible()
  })
})
