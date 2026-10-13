import { useTranslation } from 'react-i18next'

import { currentLanguage, LANGUAGES, type Language } from '../i18n/index.ts'
import { SegmentedControl } from '../shared/ui/SegmentedControl.tsx'

/** Short labels in each language's own script, so a reader of either can find theirs. */
const NATIVE_LABEL: Record<Language, { short: string; name: string }> = {
  mn: { short: 'МН', name: 'Монгол' },
  en: { short: 'EN', name: 'English' },
}

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation()
  return (
    <SegmentedControl
      className="shrink-0 text-xs"
      label={t('language.label')}
      value={currentLanguage()}
      onChange={(lng) => void i18n.changeLanguage(lng)}
      options={LANGUAGES.map((lng) => ({ value: lng, label: NATIVE_LABEL[lng].short, title: NATIVE_LABEL[lng].name }))}
    />
  )
}
