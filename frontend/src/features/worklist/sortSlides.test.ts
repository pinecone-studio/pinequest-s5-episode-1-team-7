import { describe, expect, it } from 'vitest'

import { slide } from '../../test/fixtures.ts'
import { sortSlides } from './sortSlides.ts'

const slides = [
  slide({ id: 1, risk_score: 0.9, created_at: '2026-10-13T09:00:00Z' }),
  slide({ id: 2, created_at: '2026-10-12T09:00:00Z' }),
  slide({ id: 3, indication: 'Urgent', created_at: '2026-10-13T10:00:00Z' }),
  slide({ id: 4, indication: 'Urgent', created_at: '2026-10-11T10:00:00Z' }),
]

describe('sortSlides', () => {
  it('keeps the server AI order in risk mode', () => {
    expect(sortSlides(slides, 'risk')).toBe(slides)
  })
  it('puts urgent requests first, then oldest first, in arrival mode', () => {
    expect(sortSlides(slides, 'arrival').map((s) => s.id)).toEqual([4, 3, 2, 1])
  })
  it('does not mutate the input', () => {
    sortSlides(slides, 'arrival')
    expect(slides.map((s) => s.id)).toEqual([1, 2, 3, 4])
  })
})
