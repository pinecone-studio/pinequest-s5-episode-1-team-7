import enCommon from './locales/en/common.json'
import enSlide from './locales/en/slide.json'
import enUpload from './locales/en/upload.json'
import enViewer from './locales/en/viewer.json'
import enWorklist from './locales/en/worklist.json'
import mnCommon from './locales/mn/common.json'
import mnSlide from './locales/mn/slide.json'
import mnUpload from './locales/mn/upload.json'
import mnViewer from './locales/mn/viewer.json'
import mnWorklist from './locales/mn/worklist.json'

export const LANGUAGES = ['mn', 'en'] as const
export type Language = (typeof LANGUAGES)[number]

export const isLanguage = (value: unknown): value is Language => LANGUAGES.includes(value as Language)

export const defaultNS = 'common'

/** English is the reference: its keys type `t()` and the locale test checks Mongolian against it. */
export const resources = {
  en: {
    common: enCommon,
    worklist: enWorklist,
    upload: enUpload,
    slide: enSlide,
    viewer: enViewer,
  },
  mn: {
    common: mnCommon,
    worklist: mnWorklist,
    upload: mnUpload,
    slide: mnSlide,
    viewer: mnViewer,
  },
} as const

export type Namespace = keyof (typeof resources)['en']
