import { afterEach, describe, expect, it, vi } from 'vitest'

import { elapsed, formatDateTime, formatPercent, parseDate } from './format.ts'

afterEach(() => vi.restoreAllMocks())

describe('parseDate', () => {
  it('treats offset-less SQLite timestamps as UTC', () => {
    expect(parseDate('2026-10-13T08:00:00').toISOString()).toBe('2026-10-13T08:00:00.000Z')
    expect(parseDate('2026-10-13T08:00:00+08:00').toISOString()).toBe('2026-10-13T00:00:00.000Z')
  })
})

describe('formatPercent', () => {
  it('formats fractions and shows a dash for missing values', () => {
    expect(formatPercent(0.456, 'en')).toBe('46%')
    expect(formatPercent(0.0456, 'en', 1)).toBe('4.6%')
    expect(formatPercent(null, 'mn')).toBe('—')
  })
})

describe('elapsed', () => {
  const now = Date.parse('2026-10-13T10:00:00Z')
  it('rounds to the largest sensible unit', () => {
    expect(elapsed('2026-10-13T09:59:30', now)).toEqual({ unit: 'now', count: 0 })
    expect(elapsed('2026-10-13T09:55:00', now)).toEqual({ unit: 'minute', count: 5 })
    expect(elapsed('2026-10-13T07:00:00', now)).toEqual({ unit: 'hour', count: 3 })
    expect(elapsed('2026-10-09T10:00:00', now)).toEqual({ unit: 'day', count: 4 })
  })
})

describe('formatDateTime', () => {
  it('falls back to a numeric date when the browser lacks the locale (Chrome has no Mongolian dates)', () => {
    vi.spyOn(Intl.DateTimeFormat, 'supportedLocalesOf').mockReturnValue([])
    const local = new Date(2026, 9, 3, 7, 5)
    expect(formatDateTime(local.toISOString(), 'mn')).toBe('2026.10.03 07:05')
  })
})
