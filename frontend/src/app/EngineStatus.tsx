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
      className="flex min-w-0 items-center gap-2 rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 dark:border-slate-700 dark:text-slate-300"
    >
      <span
        className={cn(
          'size-2 shrink-0 rounded-full',
          state === 'online' ? 'bg-emerald-500' : state === 'offline' ? 'bg-red-500' : 'animate-pulse bg-amber-400',
        )}
      />
      <span className="truncate">{t(`engine.${state}`)}</span>
    </span>
  )
}
