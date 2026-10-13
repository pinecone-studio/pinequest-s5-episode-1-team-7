import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import i18n from '../../i18n/index.ts'
import type { Slide } from '../../shared/api/types.ts'
import { slide } from '../../test/fixtures.ts'
import { mockFetch, renderWithProviders } from '../../test/render.tsx'
import { ReviewPanel } from './ReviewPanel.tsx'

afterEach(() => vi.unstubAllGlobals())

const render = (s: Slide) => renderWithProviders(<ReviewPanel slide={s} />, { route: `/slides/${s.id}`, path: '/slides/:id' })

describe('ReviewPanel', () => {
  it('starts a review on a queued slide', async () => {
    await i18n.changeLanguage('en')
    const fetch = mockFetch(() => slide({ id: 7, state: 'under_review' }))
    render(slide({ id: 7 }))
    await userEvent.click(screen.getByRole('button', { name: 'Start review' }))
    expect(fetch).toHaveBeenCalledWith('/api/slides/7/open', expect.objectContaining({ method: 'POST' }))
  })

  it('asks for confirmation before archiving with a decision', async () => {
    await i18n.changeLanguage('en')
    const fetch = mockFetch(() => slide({ id: 7, state: 'archived', decision: 'confirm_malignancy' }))
    render(slide({ id: 7, state: 'under_review' }))

    await userEvent.click(screen.getByRole('button', { name: 'Confirm malignancy' }))
    expect(fetch).not.toHaveBeenCalled()
    await screen.findByRole('dialog', { name: 'Confirm malignancy?' })
    await userEvent.click(screen.getAllByRole('button', { name: 'Confirm malignancy' }).at(-1)!)

    expect(await screen.findByText('other page')).toBeInTheDocument() // back to the worklist
    const [url, init] = fetch.mock.calls[0]
    expect(url).toBe('/api/slides/7/action')
    expect(JSON.parse(String(init?.body))).toEqual({ action: 'confirm_malignancy' })
  })

  it('cancelling the dialog sends nothing', async () => {
    await i18n.changeLanguage('en')
    const fetch = mockFetch(() => ({}))
    render(slide({ id: 8, state: 'under_review' }))
    await userEvent.click(screen.getByRole('button', { name: 'Mark benign' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('offers a retry for a failed slide, in Mongolian', async () => {
    await i18n.changeLanguage('mn')
    const fetch = mockFetch(() => slide({ id: 9, state: 'new' }))
    render(slide({ id: 9, state: 'failed', error: 'interrupted by restart' }))
    await userEvent.click(screen.getByRole('button', { name: 'Шинжилгээг дахин эхлүүлэх' }))
    expect(fetch).toHaveBeenCalledWith('/api/slides/9/retry', expect.objectContaining({ method: 'POST' }))
  })

  it('shows the recorded decision on an archived slide', async () => {
    await i18n.changeLanguage('en')
    mockFetch(() => ({}))
    render(slide({ id: 10, state: 'archived', decision: 'request_biopsy' }))
    expect(screen.getByText('Request formal biopsy')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
