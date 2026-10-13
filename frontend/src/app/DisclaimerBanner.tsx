import { useTranslation } from 'react-i18next'

/** Always visible: the score orders the queue, it does not diagnose. */
export function DisclaimerBanner() {
  const { t } = useTranslation()
  return (
    <p
      role="note"
      className="border-b border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-100"
    >
      <strong className="font-semibold">{t('disclaimer.title')}</strong> {t('disclaimer.body')}
    </p>
  )
}
