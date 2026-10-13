import 'i18next'

import type { defaultNS, resources } from './resources.ts'

// Type-checks translation keys against the English resources.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: typeof defaultNS
    resources: (typeof resources)['en']
    returnNull: false
  }
}
