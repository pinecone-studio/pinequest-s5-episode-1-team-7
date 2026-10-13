import { useTranslation } from 'react-i18next'

import type { Indication, RiskFlag, SlideState } from '../../shared/api/types.ts'
import { cn } from '../../shared/lib/cn.ts'
import { Spinner } from '../../shared/ui/Spinner.tsx'
import { RISK_STYLE, scorePoints } from './risk.ts'

/** AI risk flag (red / yellow / green). */
export function RiskBadge({ flag }: { flag: RiskFlag | null }) {
  const { t } = useTranslation()
  if (!flag) return null
  return (
    <span className={cn('inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold whitespace-nowrap', RISK_STYLE[flag].badge)}>
      {t(`risk.${flag}`)}
    </span>
  )
}

/** Shown on slides a pathologist re-prioritised by hand. */
export function ManualPriorityBadge() {
  const { t } = useTranslation()
  return (
    <span
      title={t('priority.manualHint')}
      className="inline-flex items-center gap-1 rounded border border-violet-300 px-1.5 py-0.5 text-[11px] font-semibold text-violet-700 dark:border-violet-800 dark:text-violet-300"
    >
      <svg viewBox="0 0 16 16" className="size-3" fill="currentColor" aria-hidden>
        <path d="M11.3 1.3a1 1 0 0 1 1.4 0l2 2a1 1 0 0 1 0 1.4l-8 8L3 13.5l.8-3.7 7.5-8.5Z" />
      </svg>
      {t('priority.manual')}
    </span>
  )
}

/** AI slide score as a 0–100 bar. */
export function ScoreBar({ score, flag }: { score: number | null; flag: RiskFlag | null }) {
  const { t } = useTranslation()
  const points = scorePoints(score)
  return (
    <div className="flex items-center gap-2" title={t('risk.scoreHint')}>
      <div className="h-2 w-20 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800" aria-hidden>
        {points != null && flag && (
          <div className={cn('h-full rounded-full', RISK_STYLE[flag].bar)} style={{ width: `${Math.max(3, points)}%` }} />
        )}
      </div>
      <span className="w-8 text-right font-mono text-sm tabular-nums">{points ?? '—'}</span>
    </div>
  )
}

const STATE_STYLE: Record<SlideState, string> = {
  new: 'text-slate-500',
  image_processing: 'text-sky-600 dark:text-sky-400',
  ai_running: 'text-sky-600 dark:text-sky-400',
  scored: 'text-sky-600 dark:text-sky-400',
  queued: 'text-slate-700 dark:text-slate-200',
  under_review: 'text-violet-700 dark:text-violet-300',
  archived: 'text-emerald-700 dark:text-emerald-400',
  failed: 'text-red-600 dark:text-red-400',
}

const WORKING: SlideState[] = ['new', 'image_processing', 'ai_running', 'scored']

export function StateLabel({ state }: { state: SlideState }) {
  const { t } = useTranslation()
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', STATE_STYLE[state])}>
      {WORKING.includes(state) && <Spinner />}
      {t(`state.${state}`)}
    </span>
  )
}

/** Clinical indication. Routine is shown quietly so Urgent stands out. */
export function IndicationBadge({ indication }: { indication: Indication }) {
  const { t } = useTranslation()
  return indication === 'Urgent' ? (
    <span className="inline-flex items-center rounded border border-red-300 px-1.5 py-0.5 text-[11px] font-semibold text-red-700 dark:border-red-800 dark:text-red-300">
      {t('indication.Urgent')}
    </span>
  ) : (
    <span className="text-xs text-slate-500">{t('indication.Routine')}</span>
  )
}
