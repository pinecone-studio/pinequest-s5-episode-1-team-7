import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { defaultNS, isLanguage, type Language, resources } from './resources.ts'

export { LANGUAGES, type Language } from './resources.ts'

/** First visit shows Mongolian; the viewer's choice is remembered in this browser. */
export const DEFAULT_LANGUAGE: Language = 'mn'
const STORAGE_KEY = 'pathtriage.language'

function storedLanguage(): Language {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return isLanguage(value) ? value : DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

function applyLanguage(lng: string) {
  document.documentElement.lang = lng
  try {
    localStorage.setItem(STORAGE_KEY, lng)
  } catch {
    /* storage unavailable (private mode): the choice lasts for this page only */
  }
}

void i18n.use(initReactI18next).init({
  resources,
  lng: storedLanguage(),
  fallbackLng: 'en',
  supportedLngs: [...Object.keys(resources)],
  defaultNS,
  ns: Object.keys(resources.en),
  interpolation: { escapeValue: false }, // React already escapes
  returnNull: false,
})
document.documentElement.lang = i18n.language
i18n.on('languageChanged', applyLanguage)

/** The active UI language, narrowed to the ones the app ships. */
export const currentLanguage = (): Language => (isLanguage(i18n.language) ? i18n.language : DEFAULT_LANGUAGE)

export default i18n
