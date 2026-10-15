import { useTranslation } from 'react-i18next'

import { useHealth } from '../shared/api/queries.ts'
import { cn } from '../shared/lib/cn.ts'

/**
 * Whether the local triage backend answers (GET /health).
 * Colour budget: system states are not risk flags — teal for ok, error
 * magenta for offline (never risk red), neutral pulse while connecting.
 */
export function EngineStatus() {
  const { t } = useTranslation()
  const health = useHealth()
  const state = health.isError ? 'offline' : health.data ? 'online' : 'connecting'
  return (
    <span
      role="status"
      className="flex min-w-0 items-center gap-2 rounded-full border border-line-soft bg-surface px-3 py-1 text-xs text-ink-dim"
    >
      <span
        className={cn(
          'size-2 shrink-0 rounded-full',
          state === 'online'
            ? 'bg-[#0b6b5e] dark:bg-[#7fe3d0]'
            : state === 'offline'
              ? 'bg-[#8e2a5b] dark:bg-[#f0a6c8]'
              : 'animate-pulse bg-ink-faint',
        )}
      />
      <span className="truncate">{t(`engine.${state}`)}</span>
    </span>
  )
}
