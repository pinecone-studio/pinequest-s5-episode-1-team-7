import '@testing-library/jest-dom/vitest'
import '../i18n/index.ts'

import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  localStorage.clear()
})
