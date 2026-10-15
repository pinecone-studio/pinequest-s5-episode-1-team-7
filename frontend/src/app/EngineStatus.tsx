import { useTranslation } from 'react-i18next'

import { useHealth } from '../shared/api/queries.ts'
import { cn } from '../shared/lib/cn.ts'

/** Whether the local triage backend answers (GET /health). */
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
          state === 'online' ? 'bg-routine shadow-[0_0_8px_rgb(143_192_166/0.8)]' : state === 'offline' ? 'bg-critical' : 'animate-pulse bg-high',
        )}
      />
      <span className="truncate">{t(`engine.${state}`)}</span>
    </span>
  )
}
