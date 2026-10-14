import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import i18n from '../../i18n/index.ts'
import { slide } from '../../test/fixtures.ts'
import { mockFetch, renderWithProviders } from '../../test/render.tsx'
import { WorklistPage } from './WorklistPage.tsx'

// Server order from GET /queue?sort=risk: highest AI score first.
const queue = [
  slide({ id: 1, risk_score: 0.91, risk_flag: 'red', created_at: '2026-10-13T09:00:00Z' }),
  slide({ id: 2, risk_score: 0.12, risk_flag: 'green', indication: 'Urgent', created_at: '2026-10-13T09:30:00Z' }),
  slide({ id: 3, risk_score: 0.05, risk_flag: 'green', created_at: '2026-10-12T09:00:00Z' }),
]
const all = [...queue, slide({ id: 4, state: 'ai_running', risk_score: null, risk_flag: null }), slide({ id: 5, state: 'under_review' })]

const backend = () =>
  mockFetch((url) => {
    if (url.startsWith('/api/queue')) return queue
    if (url.startsWith('/api/slides')) return all
    return {}
  })

const rowIds = () =>
  within(screen.getByRole('list', { name: 'Worklist' }))
    .getAllByRole('link')
    .map((a) => a.getAttribute('href'))

afterEach(() => vi.unstubAllGlobals())

describe('WorklistPage', () => {
  it('lists the worklist in AI order with risk flags, and re-sorts urgent-first', async () => {
    await i18n.changeLanguage('en')
    backend()
    renderWithProviders(<WorklistPage />)

    expect(await screen.findByText('Slide #1')).toBeInTheDocument()
    expect(rowIds()).toEqual(['/slides/1', '/slides/2', '/slides/3'])
    expect(screen.getAllByText('High risk').length).toBeGreaterThan(0)
    // A slide still in the pipeline shows in the processing strip, not the worklist.
    expect(screen.getByRole('link', { name: /Slide #4/ })).toHaveTextContent('AI model running')

    await userEvent.click(screen.getByRole('switch', { name: 'Sort by AI risk score' }))
    expect(rowIds()).toEqual(['/slides/2', '/slides/3', '/slides/1'])
  })

  it('shows slides under review in their own tab, in Mongolian', async () => {
    await i18n.changeLanguage('mn')
    backend()
    renderWithProviders(<WorklistPage />)
    await userEvent.click(await screen.findByRole('radio', { name: 'Хянаж байгаа (1)' }))
    expect(within(screen.getByRole('list', { name: 'Хянаж байгаа бэлдмэлүүд' })).getAllByRole('link')).toHaveLength(1)
  })
})
