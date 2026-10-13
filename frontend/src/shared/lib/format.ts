/**
 * Locale-aware formatting. Numbers use Intl (Mongolian shares English separators, so Chrome's fallback is
 * correct). Chrome and Electron ship no Mongolian date or relative-time data, so those go through our own
 * translations (common:time.*) or a numeric date instead.
 */

// Server timestamps are UTC; SQLite drops the offset, so add it back when missing.
export function parseDate(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`)
}

const numberFormats = new Map<string, Intl.NumberFormat>()
function numberFormat(locale: string, options: Intl.NumberFormatOptions) {
  const key = `${locale}:${JSON.stringify(options)}`
  if (!numberFormats.has(key)) numberFormats.set(key, new Intl.NumberFormat(locale, options))
  return numberFormats.get(key)!
}

/** 0.4567 -> "46%". Missing values show an em dash. */
export function formatPercent(value: number | null | undefined, locale: string, digits = 0): string {
  if (value == null || Number.isNaN(value)) return '—'
  return numberFormat(locale, { style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
}

export function formatNumber(value: number, locale: string, maximumFractionDigits = 0): string {
  return numberFormat(locale, { maximumFractionDigits }).format(value)
}

export type ElapsedUnit = 'now' | 'minute' | 'hour' | 'day'

/** Time since `iso`, rounded to the largest sensible unit, for a "5 min ago" label. */
export function elapsed(iso: string, now = Date.now()): { unit: ElapsedUnit; count: number } {
  const seconds = Math.max(0, Math.round((now - parseDate(iso).getTime()) / 1000))
  if (seconds < 60) return { unit: 'now', count: 0 }
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return { unit: 'minute', count: minutes }
  const hours = Math.round(minutes / 60)
  if (hours < 24) return { unit: 'hour', count: hours }
  return { unit: 'day', count: Math.round(hours / 24) }
}

const pad = (n: number) => String(n).padStart(2, '0')

/** Local date and time: Intl where the browser has the locale's data, else "2026.10.13 14:05". */
export function formatDateTime(iso: string, locale: string): string {
  const date = parseDate(iso)
  if (Intl.DateTimeFormat.supportedLocalesOf([locale]).length) {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
  }
  return `${date.getFullYear()}.${pad(date.getMonth() + 1)}.${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
