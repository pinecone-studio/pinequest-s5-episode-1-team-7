import { useTranslation } from 'react-i18next'

/** Always visible: the score orders the queue, it does not diagnose. */
export function DisclaimerBanner() {
  const { t } = useTranslation()
  return (
    <p
      role="note"
      className="border-b border-[#d8c49a] bg-[#f4ecd9] px-4 py-1.5 text-center text-xs leading-relaxed text-[#6d5220] dark:border-line-soft dark:bg-[#221f17] dark:text-[#cdbf9c]"
    >
      <strong className="font-display font-semibold text-[#4f3d17] dark:text-[#e2d3a6]">{t('disclaimer.title')}</strong> {t('disclaimer.body')}
    </p>
  )
}
