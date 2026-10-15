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
    <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 font-display text-xs font-bold tracking-[-0.005em] whitespace-nowrap', RISK_STYLE[flag].badge)}>
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
      className="inline-flex items-center gap-1 rounded-md border border-[#c2b8e0] bg-[#ece7f7] px-1.5 py-0.5 text-[11px] font-semibold text-[#4a3f7d] dark:border-[#4a4370] dark:bg-[#2b2740] dark:text-[#c3b8e6]"
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
      <div className="h-2 w-20 overflow-hidden rounded-full bg-canvas ring-1 ring-line-soft" aria-hidden>
        {points != null && flag && (
          <div className={cn('h-full rounded-full opacity-90', RISK_STYLE[flag].bar)} style={{ width: `${Math.max(3, points)}%` }} />
        )}
      </div>
      <span className="tnum w-8 text-right text-sm text-ink-dim">{points ?? '—'}</span>
    </div>
  )
}

const STATE_STYLE: Record<SlideState, string> = {
  new: 'text-ink-faint',
  image_processing: 'text-info',
  ai_running: 'text-info',
  scored: 'text-info',
  queued: 'text-ink-dim',
  under_review: 'text-vio',
  archived: 'text-routine',
  failed: 'text-critical',
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
    <span className="inline-flex items-center rounded-md border border-[#dfb9b9] bg-[#f3e2e2] px-1.5 py-0.5 text-[11px] font-bold text-[#7a3535] dark:border-[#5a3436] dark:bg-[#3a2426] dark:text-[#eec3c3]">
      {t('indication.Urgent')}
    </span>
  ) : (
    <span className="text-xs text-ink-faint">{t('indication.Routine')}</span>
  )
}
