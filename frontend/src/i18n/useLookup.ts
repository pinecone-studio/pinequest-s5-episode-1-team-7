import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'

import type { Namespace } from './resources.ts'

type LooseT = (key: string, options?: Record<string, unknown>) => string

/**
 * Translates a key built at runtime from a backend code (quality check name, model id, organ…),
 * falling back to the backend's own English text when the code is new to this dashboard.
 */
export function useLookup(ns: Namespace) {
  const { t, i18n } = useTranslation(ns)
  return useCallback(
    (key: string, fallback: string, options?: Record<string, unknown>) =>
      i18n.exists(key, { ns }) ? (t as unknown as LooseT)(key, options) : fallback,
    [t, i18n, ns],
  )
}
