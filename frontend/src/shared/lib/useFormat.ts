import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import { elapsed, formatDateTime, formatNumber, formatPercent } from './format.ts'

/** Formatters bound to the current UI language. */
export function useFormat() {
  const { t, i18n } = useTranslation()
  const locale = i18n.language
  return useMemo(
    () => ({
      locale,
      pct: (value: number | null | undefined, digits = 0) => formatPercent(value, locale, digits),
      num: (value: number, digits = 0) => formatNumber(value, locale, digits),
      ago: (iso: string, now?: number) => {
        const { unit, count } = elapsed(iso, now)
        return t(`time.${unit}`, { count })
      },
      dateTime: (iso: string) => formatDateTime(iso, locale),
      seconds: (ms: number, digits = 1) => t('time.seconds', { value: formatNumber(ms / 1000, locale, digits) }),
    }),
    [t, locale],
  )
}
